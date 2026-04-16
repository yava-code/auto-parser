from telegram import Update
from telegram.ext import ContextTypes

HELP = """
🚗 *Car Price Estimator Bot*

/start — this message
/stats — database stats & average prices
/predict — estimate a car's fair market price
/top\_deals — top 10 underpriced listings
/chart — price vs mileage scatter plot
"""


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP, parse_mode="Markdown")
