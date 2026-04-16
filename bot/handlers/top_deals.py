import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update
from telegram.ext import ContextTypes
from db.session import SessionLocal
from db.models import CleanListing
from ml.predict import model_ready


async def top_deals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not model_ready():
        await update.message.reply_text("⚠️ Model not trained yet. Run `python ml/train.py` first.")
        return

    session = SessionLocal()
    try:
        rows = (
            session.query(CleanListing)
            .filter(
                CleanListing.predicted_price.isnot(None),
                CleanListing.price_eur.isnot(None),
                # real price at least 20% below predicted
                CleanListing.price_eur <= CleanListing.predicted_price * 0.80,
            )
            .order_by(
                (CleanListing.predicted_price - CleanListing.price_eur).desc()
            )
            .limit(10)
            .all()
        )

        if not rows:
            await update.message.reply_text("😕 No deals found yet — try scraping more listings.")
            return

        lines = ["🔥 *Top 10 Underpriced Deals*\n_(real price ≥20% below predicted)_\n"]
        for i, r in enumerate(rows, 1):
            saving = r.predicted_price - r.price_eur
            pct = saving / r.predicted_price * 100
            lines.append(
                f"{i}. Year `{r.year}`, {r.mileage_km:,} km\n"
                f"   Listed: `€{r.price_eur:,.0f}` | Est: `€{r.predicted_price:,.0f}` | Save `€{saving:,.0f}` ({pct:.0f}%)"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    finally:
        session.close()
