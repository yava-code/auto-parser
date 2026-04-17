import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update, Message
from telegram.ext import ContextTypes
from sqlalchemy import func
from db.session import SessionLocal
from db.models import RawListing
from bot.keyboards import back_to_menu

log = logging.getLogger(__name__)


async def send_stats(msg: Message):
    session = SessionLocal()
    try:
        total = session.query(func.count(RawListing.id)).scalar() or 0

        if total == 0:
            await msg.reply_text(
                "📭 No data yet\\. Run the scraper first\\.",
                parse_mode="MarkdownV2",
                reply_markup=back_to_menu(),
            )
            return

        avg_price = session.query(func.avg(RawListing.price_eur)).scalar() or 0
        min_price = session.query(func.min(RawListing.price_eur)).scalar() or 0
        max_price = session.query(func.max(RawListing.price_eur)).scalar() or 0

        brand_rows = (
            session.query(
                RawListing.brand,
                func.count(RawListing.id).label("cnt"),
                func.avg(RawListing.price_eur).label("avg_p"),
            )
            .filter(RawListing.brand.isnot(None))
            .group_by(RawListing.brand)
            .order_by(func.count(RawListing.id).desc())
            .limit(5)
            .all()
        )

        fuel_rows = (
            session.query(
                RawListing.fuel_type,
                func.count(RawListing.id).label("cnt"),
            )
            .filter(RawListing.fuel_type.isnot(None))
            .group_by(RawListing.fuel_type)
            .order_by(func.count(RawListing.id).desc())
            .limit(4)
            .all()
        )

        lines = [
            "📊 *Database Stats*\n",
            f"Total listings: `{total:,}`",
            f"Avg price: `€{avg_price:,.0f}`",
            f"Range: `€{min_price:,.0f}` — `€{max_price:,.0f}`\n",
            "*Top 5 brands:*",
        ]
        for r in brand_rows:
            lines.append(f"  • {r.brand}: `{r.cnt}` listings, avg `€{r.avg_p:,.0f}`")

        if fuel_rows:
            lines.append("\n*By fuel type:*")
            for r in fuel_rows:
                lines.append(f"  • {r.fuel_type}: `{r.cnt}`")

        log.info("stats requested, total=%d", total)
        await msg.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=back_to_menu(),
        )
    finally:
        session.close()


async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_stats(update.message)
