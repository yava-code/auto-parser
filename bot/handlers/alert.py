import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
from sqlalchemy import func
from db.session import SessionLocal
from db.models import RawListing, UserAlert
from bot.keyboards import back_to_menu

log = logging.getLogger(__name__)

ALERT_BRAND, ALERT_PRICE, ALERT_YEAR = range(3)

MAX_ALERTS_PER_USER = 5


def _alert_summary(a: UserAlert) -> str:
    parts = [f"🏷️ {a.brand or 'Any brand'}"]
    if a.max_price_eur:
        parts.append(f"💰 max €{a.max_price_eur:,.0f}")
    if a.min_year:
        parts.append(f"📅 from {a.min_year}")
    if a.max_mileage_km:
        parts.append(f"📏 max {a.max_mileage_km:,} km")
    if a.fuel_type:
        parts.append(f"⛽ {a.fuel_type}")
    return " | ".join(parts)


async def alert_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = SessionLocal()
    try:
        count = session.query(func.count(UserAlert.id)).filter(
            UserAlert.telegram_id == user_id, UserAlert.active == True
        ).scalar()
    finally:
        session.close()

    if count >= MAX_ALERTS_PER_USER:
        await update.message.reply_text(
            f"⚠️ You have {count} active alerts \\(max {MAX_ALERTS_PER_USER}\\)\\. "
            f"Use /myalerts to manage them\\.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu(),
        )
        return ConversationHandler.END

    ctx.user_data.clear()
    await update.message.reply_text(
        "🔔 *New Price Alert*\n\n"
        "I'll notify you when a matching car appears on the market\\.\n\n"
        "Step 1/3 — What brand? \\(e\\.g\\. `BMW`\\) or type `any` to skip\\.",
        parse_mode="MarkdownV2",
    )
    return ALERT_BRAND


async def alert_brand(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    ctx.user_data["brand"] = None if val.lower() == "any" else val.title()
    await update.message.reply_text(
        "Step 2/3 — 💰 Max price in EUR? \\(e\\.g\\. `15000`\\) or `skip`",
        parse_mode="MarkdownV2",
    )
    return ALERT_PRICE


async def alert_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    if val.lower() == "skip":
        ctx.user_data["max_price_eur"] = None
    else:
        try:
            ctx.user_data["max_price_eur"] = float(val.replace(",", "").replace(".", ""))
        except ValueError:
            await update.message.reply_text("❌ Enter a number (e.g. `15000`) or `skip`.")
            return ALERT_PRICE

    await update.message.reply_text(
        "Step 3/3 — 📅 Minimum year? \\(e\\.g\\. `2018`\\) or `skip`",
        parse_mode="MarkdownV2",
    )
    return ALERT_YEAR


async def alert_year(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    if val.lower() == "skip":
        ctx.user_data["min_year"] = None
    else:
        try:
            yr = int(val)
            assert 1990 <= yr <= 2025
            ctx.user_data["min_year"] = yr
        except (ValueError, AssertionError):
            await update.message.reply_text("❌ Enter a valid year (1990–2025) or `skip`.")
            return ALERT_YEAR

    d = ctx.user_data
    user_id = update.effective_user.id

    session = SessionLocal()
    try:
        alert = UserAlert(
            telegram_id=user_id,
            brand=d.get("brand"),
            max_price_eur=d.get("max_price_eur"),
            min_year=d.get("min_year"),
        )
        session.add(alert)
        session.commit()
        log.info("alert created: user %d → %s", user_id, _alert_summary(alert))
    finally:
        session.close()

    summary = _alert_summary(alert)
    await update.message.reply_text(
        f"✅ *Alert created\\!*\n\n{summary}\n\n"
        "_I'll notify you when a matching listing appears\\._",
        parse_mode="MarkdownV2",
        reply_markup=back_to_menu(),
    )
    return ConversationHandler.END


async def my_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = SessionLocal()
    try:
        alerts = (
            session.query(UserAlert)
            .filter(UserAlert.telegram_id == user_id, UserAlert.active == True)
            .order_by(UserAlert.created_at.desc())
            .all()
        )
    finally:
        session.close()

    if not alerts:
        await update.message.reply_text(
            "You have no active alerts\\. Use /alert to create one\\.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_menu(),
        )
        return

    lines = ["🔔 *Your Active Alerts*\n"]
    buttons = []
    for a in alerts:
        lines.append(f"`#{a.id}` {_alert_summary(a)}")
        buttons.append([InlineKeyboardButton(f"❌ Cancel #{a.id}", callback_data=f"del_alert_{a.id}")])

    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="cmd_menu")])
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def delete_alert_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    alert_id = int(query.data.replace("del_alert_", ""))
    user_id = update.effective_user.id

    session = SessionLocal()
    try:
        alert = session.query(UserAlert).filter(
            UserAlert.id == alert_id,
            UserAlert.telegram_id == user_id,
        ).first()
        if alert:
            alert.active = False
            session.commit()
            log.info("alert #%d cancelled by user %d", alert_id, user_id)
            await query.message.edit_text(
                f"✅ Alert \\#`{alert_id}` cancelled\\.",
                parse_mode="MarkdownV2",
                reply_markup=back_to_menu(),
            )
        else:
            await query.message.edit_text("Alert not found.", reply_markup=back_to_menu())
    finally:
        session.close()


async def alert_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=back_to_menu())
    return ConversationHandler.END


def alert_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("alert", alert_start)],
        states={
            ALERT_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, alert_brand)],
            ALERT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, alert_price)],
            ALERT_YEAR:  [MessageHandler(filters.TEXT & ~filters.COMMAND, alert_year)],
        },
        fallbacks=[CommandHandler("cancel", alert_cancel)],
        allow_reentry=True,
    )
