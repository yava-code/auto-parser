import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update, Message
from telegram.ext import ContextTypes
from db.session import SessionLocal
from db.models import CleanListing
from ml.predict import model_ready
from bot.keyboards import back_to_menu

log = logging.getLogger(__name__)


async def send_top_deals(msg: Message):
    if not model_ready():
        await msg.reply_text(
            "⚠️ Model not trained yet\\. Run `python ml/train\\.py` first\\.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu(),
        )
        return

    session = SessionLocal()
    try:
        rows = (
            session.query(CleanListing)
            .filter(
                CleanListing.predicted_price.isnot(None),
                CleanListing.price_eur.isnot(None),
                CleanListing.price_eur <= CleanListing.predicted_price * 0.80,
            )
            .order_by((CleanListing.predicted_price - CleanListing.price_eur).desc())
            .limit(10)
            .all()
        )

        if not rows:
            await msg.reply_text(
                "😕 No deals found yet — scrape more listings first.",
                reply_markup=back_to_menu(),
            )
            return

        lines = ["🔥 *Top 10 Underpriced Deals*\n_price ≥20% below predicted_\n"]
        for i, r in enumerate(rows, 1):
            saving = r.predicted_price - r.price_eur
            pct = saving / r.predicted_price * 100
            lines.append(
                f"{i}\\. Year `{r.year}`, {r.mileage_km:,} km\n"
                f"   Listed: `€{r.price_eur:,.0f}` \\| Est: `€{r.predicted_price:,.0f}` \\| "
                f"Save `€{saving:,.0f}` \\({pct:.0f}%\\)"
            )

        log.info("top_deals: found %d deals", len(rows))
        await msg.reply_text(
            "\n".join(lines),
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu(),
        )
    finally:
        session.close()


async def top_deals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_top_deals(update.message)
