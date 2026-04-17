import logging
import os
from dotenv import load_dotenv
from celery import Celery
from celery.schedules import crontab

load_dotenv()

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery("car_price_bot", broker=REDIS_URL, backend=REDIS_URL)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

app.conf.beat_schedule = {
    "scrape-daily": {
        "task": "tasks.celery_app.run_scraper",
        "schedule": crontab(hour=1, minute=0),
    },
    "retrain-daily": {
        "task": "tasks.celery_app.train_model",
        "schedule": crontab(hour=2, minute=0),
    },
    "check-alerts-hourly": {
        "task": "tasks.celery_app.check_alerts",
        "schedule": crontab(minute=0),  # top of every hour
    },
}


@app.task(name="tasks.celery_app.train_model")
def train_model():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from ml.train import run_training
    result = run_training()
    return result


@app.task(name="tasks.celery_app.run_scraper")
def run_scraper(pages=None):
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from scraper.run import run
    return run(n_pages=pages)


@app.task(name="tasks.celery_app.check_alerts")
def check_alerts():
    """Find new listings that match active user alerts and notify via Telegram."""
    import sys, os, asyncio
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from datetime import datetime, timedelta
    from sqlalchemy import and_
    from db.session import SessionLocal
    from db.models import UserAlert, RawListing, CleanListing

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        log.warning("check_alerts: TELEGRAM_TOKEN not set, skipping")
        return 0

    session = SessionLocal()
    notified = 0
    try:
        alerts = session.query(UserAlert).filter(UserAlert.active == True).all()
        log.info("check_alerts: %d active alerts", len(alerts))

        for alert in alerts:
            # look at listings from the last 2 hours (generously overlapping)
            since = (alert.last_notified_at or datetime.utcnow() - timedelta(hours=2))
            filters = [RawListing.scraped_at >= since, RawListing.price_eur.isnot(None)]

            if alert.brand:
                filters.append(RawListing.brand.ilike(f"%{alert.brand}%"))
            if alert.max_price_eur:
                filters.append(RawListing.price_eur <= alert.max_price_eur)
            if alert.min_year:
                filters.append(RawListing.year >= alert.min_year)
            if alert.max_mileage_km:
                filters.append(RawListing.mileage_km <= alert.max_mileage_km)
            if alert.fuel_type:
                filters.append(RawListing.fuel_type == alert.fuel_type)

            matches = (
                session.query(RawListing)
                .filter(and_(*filters))
                .order_by(RawListing.price_eur)
                .limit(3)
                .all()
            )

            if not matches:
                continue

            lines = [f"🔔 *Alert \\#{alert.id} matched {len(matches)} new listing(s)\\!*\n"]
            for r in matches:
                km = f"{r.mileage_km:,}" if r.mileage_km else "?"
                yr = r.year or "?"
                fuel = f" {r.fuel_type}" if r.fuel_type else ""
                lines.append(
                    f"  • `{yr}` {r.brand} {r.model or ''}{fuel}, "
                    f"{km} km — `€{r.price_eur:,.0f}`"
                )

            text = "\n".join(lines)

            asyncio.run(_send_telegram(token, alert.telegram_id, text))
            alert.last_notified_at = datetime.utcnow()
            notified += 1

        session.commit()
    except Exception as e:
        log.error("check_alerts error: %s", e)
        session.rollback()
    finally:
        session.close()

    log.info("check_alerts done: %d notifications sent", notified)
    return notified


async def _send_telegram(token: str, chat_id: int, text: str):
    from telegram import Bot
    try:
        async with Bot(token=token) as bot:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="MarkdownV2")
    except Exception as e:
        log.warning("telegram notify failed for %d: %s", chat_id, e)
