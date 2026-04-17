import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db.session import SessionLocal
from db.models import UserUsage
from bot.keyboards import back_to_menu

log = logging.getLogger(__name__)

STARS_COST = 50
USES_PER_PACK = 10
PAYLOAD = "ai_uses_10"


async def send_invoice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send a Telegram Stars invoice for AI uses."""
    await update.message.reply_invoice(
        title="10 AI Assistant Uses",
        description=f"Get {USES_PER_PACK} more queries to the AI car assistant (powered by Groq).",
        payload=PAYLOAD,
        provider_token="",  # empty = Telegram Stars (XTR)
        currency="XTR",
        prices=[LabeledPrice(label=f"{USES_PER_PACK} AI queries", amount=STARS_COST)],
    )
    log.info("invoice sent to user %d", update.effective_user.id)


async def precheckout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != PAYLOAD:
        await query.answer(ok=False, error_message="Unknown payment payload.")
        return
    await query.answer(ok=True)
    log.info("precheckout ok for user %d", query.from_user.id)


async def successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payment = update.message.successful_payment

    if payment.invoice_payload != PAYLOAD:
        return

    session = SessionLocal()
    try:
        usage = session.query(UserUsage).filter_by(telegram_id=user_id).first()
        if not usage:
            usage = UserUsage(telegram_id=user_id, free_uses_left=0, paid_uses=0)
            session.add(usage)
        usage.paid_uses += USES_PER_PACK
        session.commit()
        log.info("payment success: user %d +%d paid uses (total paid: %d)",
                 user_id, USES_PER_PACK, usage.paid_uses)
    finally:
        session.close()

    await update.message.reply_text(
        f"✅ Payment received\\! *{USES_PER_PACK} AI uses* added to your account\\.\n"
        f"Use /ask to start chatting\\.",
        parse_mode="MarkdownV2",
        reply_markup=back_to_menu(),
    )


async def buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle inline button 'Buy 10 uses' callback."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_invoice(
        title="10 AI Assistant Uses",
        description=f"Get {USES_PER_PACK} more queries to the AI car assistant.",
        payload=PAYLOAD,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{USES_PER_PACK} AI queries", amount=STARS_COST)],
    )
