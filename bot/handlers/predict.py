import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters,
)
from sqlalchemy import func
from db.session import SessionLocal
from db.models import RawListing
from ml.predict import predict_price, model_ready
from bot.keyboards import back_to_menu, main_menu

log = logging.getLogger(__name__)

YEAR, MILEAGE, ENGINE, FUEL, TRANS, BRAND = range(6)

FUEL_OPTIONS = [["Petrol", "Diesel"], ["Electric", "Hybrid"], ["LPG", "Petrol+LPG"], ["Skip"]]
TRANS_OPTIONS = [["Manual", "Automatic"], ["Semi-automatic"], ["Skip"]]


def _escape_md(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    chars = r"_[]()~>#+-=|{}.!"
    for c in chars:
        text = text.replace(c, f"\\{c}")
    return text


async def predict_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not model_ready():
        await update.message.reply_text(
            "⚠️ Model not trained yet\\. Run `python ml/train\\.py` first\\.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu(),
        )
        return ConversationHandler.END

    ctx.user_data.clear()
    log.info("user %d started /predict", update.effective_user.id)
    await update.message.reply_text(
        "🔍 *Car Price Estimator*\n\nStep 1/6 — What year was the car made? \\(e\\.g\\. `2019`\\)",
        parse_mode="MarkdownV2",
        reply_markup=ReplyKeyboardRemove(),
    )
    return YEAR


async def get_year(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "skip":
        ctx.user_data["year"] = 2020  # default
        await update.message.reply_text("Step 2/6 — 📏 Mileage in km? \(e\.g\. `85000`\) or _skip_",
                                        parse_mode="MarkdownV2")
        return MILEAGE
    try:
        year = int(text)
        assert 1990 <= year <= 2025
    except (ValueError, AssertionError):
        await update.message.reply_text("❌ Enter a valid year between 1990 and 2025, or type _skip_")
        return YEAR
    ctx.user_data["year"] = year
    await update.message.reply_text("Step 2/6 — 📏 Mileage in km? \(e\.g\. `85000`\) or _skip_",
                                    parse_mode="MarkdownV2")
    return MILEAGE


async def get_mileage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "skip":
        ctx.user_data["mileage_km"] = 100000  # default
        await update.message.reply_text(
            "Step 3/6 — ⚡ Engine power in kW? \(e\.g\. `110` for \\~150 hp\\) or _skip_",
            parse_mode="MarkdownV2",
        )
        return ENGINE
    try:
        km = int(text.replace(",", "").replace(".", ""))
        assert 0 <= km <= 1_500_000
    except (ValueError, AssertionError):
        await update.message.reply_text("❌ Enter a valid mileage (0 – 1,500,000 km), or type _skip_")
        return MILEAGE
    ctx.user_data["mileage_km"] = km
    await update.message.reply_text(
        "Step 3/6 — ⚡ Engine power in kW? \(e\.g\. `110` for \\~150 hp\\) or _skip_",
        parse_mode="MarkdownV2",
    )
    return ENGINE


async def get_engine(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "skip":
        ctx.user_data["power_kw"] = 100.0  # default ~136 hp
        await update.message.reply_text(
            "Step 4/6 — ⛽ Fuel type?",
            reply_markup=ReplyKeyboardMarkup(FUEL_OPTIONS, one_time_keyboard=True, resize_keyboard=True),
        )
        return FUEL
    try:
        kw = float(text.replace(",", "."))
        assert 10.0 <= kw <= 1000.0
    except (ValueError, AssertionError):
        await update.message.reply_text("❌ Enter engine power between 10 and 1000 kW, or type _skip_")
        return ENGINE
    ctx.user_data["power_kw"] = kw
    await update.message.reply_text(
        "Step 4/6 — ⛽ Fuel type?",
        reply_markup=ReplyKeyboardMarkup(FUEL_OPTIONS, one_time_keyboard=True, resize_keyboard=True),
    )
    return FUEL


async def get_fuel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fuel = update.message.text.strip()
    if fuel.lower() == "skip":
        fuel = "Petrol"  # default
    ctx.user_data["fuel_type"] = fuel
    await update.message.reply_text(
        "Step 5/6 — 🔧 Transmission?",
        reply_markup=ReplyKeyboardMarkup(TRANS_OPTIONS, one_time_keyboard=True, resize_keyboard=True),
    )
    return TRANS


async def get_transmission(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    trans = update.message.text.strip()
    if trans.lower() == "skip":
        trans = "Manual"  # default
    ctx.user_data["transmission"] = trans
    await update.message.reply_text(
        "Step 6/6 — 🚗 Brand and model? \(e\.g\. `BMW 3 Series`\)",
        parse_mode="MarkdownV2",
        reply_markup=ReplyKeyboardRemove(),
    )
    return BRAND


async def get_brand(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    parts = raw.split(None, 1)
    ctx.user_data["brand"] = parts[0]
    ctx.user_data["model"] = parts[1] if len(parts) > 1 else parts[0]

    d = ctx.user_data
    try:
        price = predict_price(
            d["brand"], d["model"], d["year"],
            d["mileage_km"], d["power_kw"], d["fuel_type"], d["transmission"],
        )
    except Exception as e:
        log.error("predict failed for user %d: %s", update.effective_user.id, e)
        await update.message.reply_text(f"⚠️ Prediction failed: {e}", reply_markup=back_to_menu())
        return ConversationHandler.END

    session = SessionLocal()
    try:
        avg_price = session.query(func.avg(RawListing.price_eur)).scalar()
        avg_price = float(avg_price) if avg_price else None

        brand_avg = session.query(func.avg(RawListing.price_eur)).filter(
            RawListing.brand.ilike(f"%{d['brand']}%")
        ).scalar()
        brand_avg = float(brand_avg) if brand_avg else None
    finally:
        session.close()

    market_line = ""
    if avg_price:
        diff = price - avg_price
        sign = "\\+" if diff >= 0 else "\\-"
        market_line = f"\n📊 vs market avg: `{sign}€{abs(diff):,.0f}`"

    brand_line = ""
    if brand_avg:
        diff2 = price - brand_avg
        sign2 = "\\+" if diff2 >= 0 else "\\-"
        brand_line = f"\n🏷️ vs {d['brand']} avg: `{sign2}€{abs(diff2):,.0f}`"

    _mk = f"{d['mileage_km']:,}"
    _pw = f"{d['power_kw']}kW"
    msg = (
        f"✅ *Estimated fair price: €{_escape_md(f'{price:,.0f}')}*\n\n"
        f"_{_escape_md(d['brand'])} {_escape_md(d['model'])} · {_escape_md(str(d['year']))} · "
        f"{_escape_md(_mk)} km · {_escape_md(_pw)} {_escape_md(d['fuel_type'])} · {_escape_md(d['transmission'])}_"
        f"{market_line}{brand_line}"
    )
    log.info("predict: user %d → €%.0f for %s %s %d",
             update.effective_user.id, price, d["brand"], d["model"], d["year"])
    await update.message.reply_text(msg, parse_mode="MarkdownV2", reply_markup=back_to_menu())
    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def predict_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("predict", predict_start)],
        states={
            YEAR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            MILEAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mileage)],
            ENGINE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_engine)],
            FUEL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fuel)],
            TRANS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_transmission)],
            BRAND:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
