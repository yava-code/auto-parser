import os
import sys
import logging

from dotenv import load_dotenv
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    PreCheckoutQueryHandler, MessageHandler, filters,
)

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import init_db
from bot.handlers.start import start
from bot.handlers.stats import stats, send_stats
from bot.handlers.top_deals import top_deals, send_top_deals
from bot.handlers.chart import chart, send_chart
from bot.handlers.predict import predict_conv_handler
from bot.handlers.search import search_conv_handler, top5_command
from bot.handlers.ai_chat import ai_conv_handler
from bot.handlers.alert import alert_conv_handler, my_alerts, delete_alert_callback
from bot.handlers.anomalies import anomalies, send_anomalies
from bot.handlers.buy_stars import send_invoice, precheckout, successful_payment, buy_callback
from bot.keyboards import main_menu

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")          # e.g. https://yourdomain.com
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))


async def menu_callback(update, ctx):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cmd_menu":
        await query.message.reply_text("🏠 Main Menu", reply_markup=main_menu())
    elif data == "cmd_stats":
        await send_stats(query.message)
    elif data == "cmd_chart":
        await send_chart(query.message)
    elif data == "cmd_top_deals":
        await send_top_deals(query.message)
    elif data == "cmd_predict":
        await query.message.reply_text(
            "Use /predict to start the price estimator.",
        )
    elif data == "cmd_search":
        await query.message.reply_text(
            "Use /search <brand> — e.g. /search BMW\n"
            "or /top5 <brand> for a quick top-5 view."
        )
    elif data == "cmd_ai":
        await query.message.reply_text("Use /ask to chat with the AI assistant.")
    elif data == "cmd_anomalies":
        await send_anomalies(query.message)


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN not set in environment")

    init_db()

    try:
        from ml.predict import load_model, model_ready
        if model_ready():
            load_model()
            log.info("ML model loaded at startup")
        else:
            log.warning("No trained model found — run `python ml/train.py` first")
    except Exception as e:
        log.warning("Could not pre-load model: %s", e)

    app = Application.builder().token(TOKEN).build()

    # conversation handlers first (priority over plain commands)
    app.add_handler(predict_conv_handler())
    app.add_handler(search_conv_handler())
    app.add_handler(ai_conv_handler())
    app.add_handler(alert_conv_handler())

    # simple commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("top_deals", top_deals))
    app.add_handler(CommandHandler("chart", chart))
    app.add_handler(CommandHandler("top5", top5_command))
    app.add_handler(CommandHandler("buy", send_invoice))
    app.add_handler(CommandHandler("myalerts", my_alerts))
    app.add_handler(CommandHandler("anomalies", anomalies))

    # inline button callbacks
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^cmd_"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_ai_uses$"))
    app.add_handler(CallbackQueryHandler(delete_alert_callback, pattern=r"^del_alert_\d+$"))

    # payment
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    if WEBHOOK_URL:
        log.info("Starting in webhook mode: %s", WEBHOOK_URL)
        app.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
            drop_pending_updates=True,
        )
    else:
        log.info("Starting in polling mode")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
