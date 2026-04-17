import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update, Message
from telegram.ext import ContextTypes
from sqlalchemy import func, join
from db.session import SessionLocal
from db.models import CleanListing, RawListing
from ml.anomaly import anomaly_ready
from bot.keyboards import back_to_menu

log = logging.getLogger(__name__)


async def send_anomalies(msg: Message):
    if not anomaly_ready():
        await msg.reply_text(
            "⚠️ Anomaly model not trained yet. Run <code>python ml/train.py</code> first.",
            parse_mode="HTML",
            reply_markup=back_to_menu(),
        )
        return

    session = SessionLocal()
    try:
        # join clean → raw to get human-readable fields
        rows = (
            session.query(CleanListing, RawListing)
            .join(RawListing, CleanListing.raw_id == RawListing.id)
            .filter(
                CleanListing.anomaly_score.isnot(None),
                RawListing.price_eur.isnot(None),
            )
            # lowest anomaly_score = most anomalous
            .order_by(CleanListing.anomaly_score)
            .limit(10)
            .all()
        )
    finally:
        session.close()

    if not rows:
        await msg.reply_text(
            "😕 No anomaly data yet — retrain the model first.",
            reply_markup=back_to_menu(),
        )
        return

    lines = [
        "🔬 <b>Top 10 Market Anomalies</b>",
        "<i>Listings whose feature combination is statistically unusual.</i>",
        "<i>Could be exceptional deals — or suspicious listings.</i>\n",
    ]
    for i, (cl, raw) in enumerate(rows, 1):
        brand = raw.brand or "?"
        model = raw.model or ""
        yr = raw.year or "?"
        km = f"{raw.mileage_km:,}" if raw.mileage_km else "?"
        price = f"€{raw.price_eur:,.0f}" if raw.price_eur else "?"
        pred = f"€{cl.predicted_price:,.0f}" if cl.predicted_price else "?"
        score = f"{cl.anomaly_score:.3f}"

        # show how far price deviates from prediction
        deviation = ""
        if cl.predicted_price and raw.price_eur:
            diff = raw.price_eur - cl.predicted_price
            pct = diff / cl.predicted_price * 100
            sign = "+" if diff >= 0 else ""
            deviation = f" | {sign}{pct:.0f}% vs model"

        lines.append(
            f"{i}. <b>{brand} {model}</b> ({yr})\n"
            f"   {km} km · Listed: <code>{price}</code> · Est: <code>{pred}</code>{deviation}\n"
            f"   Anomaly score: <code>{score}</code>"
        )

    log.info("anomalies: returned %d records", len(rows))
    await msg.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=back_to_menu())


async def anomalies(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_anomalies(update.message)
