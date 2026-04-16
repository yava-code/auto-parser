import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import func, text
from db.session import SessionLocal
from db.models import RawListing


async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    try:
        total = session.query(func.count(RawListing.id)).scalar() or 0

        if total == 0:
            await update.message.reply_text("📭 No data in database yet. Run the scraper first.")
            return

        avg_price = session.query(func.avg(RawListing.price_eur)).scalar() or 0

        # top 5 brands by count with their avg price
        rows = (
            session.query(
                RawListing.brand,
                func.count(RawListing.id).label("cnt"),
                func.avg(RawListing.price_eur).label("avg_price"),
            )
            .filter(RawListing.brand.isnot(None))
            .group_by(RawListing.brand)
            .order_by(func.count(RawListing.id).desc())
            .limit(5)
            .all()
        )

        lines = [f"📊 *Database Stats*\n"]
        lines.append(f"Total listings: `{total:,}`")
        lines.append(f"Overall avg price: `€{avg_price:,.0f}`\n")
        lines.append("*Top 5 brands:*")
        for r in rows:
            lines.append(f"  • {r.brand}: `{r.cnt}` listings, avg `€{r.avg_price:,.0f}`")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    finally:
        session.close()
