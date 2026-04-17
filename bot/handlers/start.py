import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards import main_menu

log = logging.getLogger(__name__)

WELCOME = (
    "🚗 *Car Price Bot*\n\n"
    "AI\\-powered assistant for finding and pricing used cars\\.\n\n"
    "📦 Source: Otomoto\\.pl\n"
    "🤖 AI: Groq \\(Qwen3\\-32B\\)\n"
    "🎁 Free AI queries: *5* per user\n\n"
    "Choose an action:"
)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log.info("user %d (%s) started bot", user.id, user.username or "?")
    await update.message.reply_text(
        WELCOME,
        parse_mode="MarkdownV2",
        reply_markup=main_menu(),
    )
