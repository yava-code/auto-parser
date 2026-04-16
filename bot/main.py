import os
import sys
import logging

from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import Application, CommandHandler

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import init_db
from bot.handlers.start import start
from bot.handlers.stats import stats
from bot.handlers.top_deals import top_deals
from bot.handlers.chart import chart
from bot.handlers.predict import predict_conv_handler

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN not set in environment")

    # init DB tables
    init_db()

    # pre-load model if available so first /predict is instant
    try:
        from ml.predict import load_model, model_ready
        if model_ready():
            load_model()
            log.info("ML model loaded at startup")
        else:
            log.warning("No trained model found — run `python ml/train.py` first")
    except Exception as e:
        log.warning(f"Could not pre-load model: {e}")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("top_deals", top_deals))
    app.add_handler(CommandHandler("chart", chart))
    app.add_handler(predict_conv_handler())

    log.info("Bot starting — polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
