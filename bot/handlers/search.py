import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
from sqlalchemy import func
from db.session import SessionLocal
from db.models import RawListing
from bot.keyboards import back_to_menu

log = logging.getLogger(__name__)

SEARCH_TYPE, SEARCH_VALUE = range(2)


def _brand_keyboard(brands: list[str]) -> InlineKeyboardMarkup:
    rows = [brands[i:i+3] for i in range(0, len(brands), 3)]
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(b, callback_data=f"sb_{b}") for b in row] for row in rows]
        + [[InlineKeyboardButton("❌ Cancel", callback_data="s_cancel")]]
    )


async def search_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if args:
        # /search BMW — direct brand shortcut
        brand = args[0].strip().title()
        msg = update.message
        await _show_brand_results(msg, brand)
        return ConversationHandler.END

    # show top brands as inline buttons
    session = SessionLocal()
    try:
        rows = (
            session.query(RawListing.brand, func.count(RawListing.id).label("cnt"))
            .filter(RawListing.brand.isnot(None))
            .group_by(RawListing.brand)
            .order_by(func.count(RawListing.id).desc())
            .limit(18)
            .all()
        )
    finally:
        session.close()

    if not rows:
        await update.message.reply_text("📭 No data yet — run the scraper first.")
        return ConversationHandler.END

    brands = [r.brand for r in rows]
    await update.message.reply_text(
        "🔎 *Search Cars*\n\nSelect a brand or type one:",
        parse_mode="Markdown",
        reply_markup=_brand_keyboard(brands),
    )
    return SEARCH_TYPE


async def search_type_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "s_cancel":
        await query.message.edit_text("❌ Search cancelled.", reply_markup=back_to_menu())
        return ConversationHandler.END

    brand = query.data.replace("sb_", "", 1)
    await _show_brand_results(query.message, brand, edit=True)
    return ConversationHandler.END


async def search_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    brand = update.message.text.strip().title()
    await _show_brand_results(update.message, brand)
    return ConversationHandler.END


async def _show_brand_results(msg: Message, brand: str, edit: bool = False):
    session = SessionLocal()
    try:
        brand_filter = RawListing.brand.ilike(f"%{brand}%")

        stats = session.query(
            func.count(RawListing.id),
            func.avg(RawListing.price_eur),
            func.min(RawListing.price_eur),
            func.max(RawListing.price_eur),
            func.avg(RawListing.mileage_km),
        ).filter(brand_filter).first()

        count = stats[0] or 0
        if count == 0:
            text = f"😕 No listings found for *{brand}*."
            if edit:
                await msg.edit_text(text, parse_mode="Markdown", reply_markup=back_to_menu())
            else:
                await msg.reply_text(text, parse_mode="Markdown", reply_markup=back_to_menu())
            return

        avg_p = float(stats[1] or 0)
        min_p = float(stats[2] or 0)
        max_p = float(stats[3] or 0)
        avg_km = float(stats[4] or 0)

        # top 5 cheapest
        top5 = (
            session.query(RawListing)
            .filter(brand_filter, RawListing.price_eur.isnot(None))
            .order_by(RawListing.price_eur)
            .limit(5)
            .all()
        )

        # fuel breakdown
        fuel_rows = (
            session.query(RawListing.fuel_type, func.count(RawListing.id).label("cnt"))
            .filter(brand_filter, RawListing.fuel_type.isnot(None))
            .group_by(RawListing.fuel_type)
            .order_by(func.count(RawListing.id).desc())
            .limit(4)
            .all()
        )

        lines = [
            f"🏷️ *{brand}* — {count:,} listings\n",
            f"💰 Avg price: `€{avg_p:,.0f}`",
            f"📉 Range: `€{min_p:,.0f}` — `€{max_p:,.0f}`",
            f"📏 Avg mileage: `{avg_km:,.0f} km`",
        ]

        if fuel_rows:
            fuel_str = ", ".join(f"{r.fuel_type} ({r.cnt})" for r in fuel_rows)
            lines.append(f"⛽ Fuels: {fuel_str}")

        lines.append("\n*Top 5 cheapest:*")
        for i, r in enumerate(top5, 1):
            km = f"{r.mileage_km:,}" if r.mileage_km else "?"
            yr = r.year or "?"
            mdl = r.model or ""
            fuel = f" {r.fuel_type}" if r.fuel_type else ""
            lines.append(
                f"{i}\\. `{yr}` {mdl}{fuel}, {km} km — `€{r.price_eur:,.0f}`"
            )

        log.info("search '%s': %d results", brand, count)
        text = "\n".join(lines)
        if edit:
            await msg.edit_text(text, parse_mode="MarkdownV2", reply_markup=back_to_menu())
        else:
            await msg.reply_text(text, parse_mode="MarkdownV2", reply_markup=back_to_menu())
    finally:
        session.close()


async def top5_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    brand = " ".join(ctx.args).strip().title() if ctx.args else ""
    if not brand:
        await update.message.reply_text("Usage: /top5 <brand>  e.g. /top5 BMW")
        return
    await _show_brand_results(update.message, brand)


async def search_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=back_to_menu())
    return ConversationHandler.END


def search_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("search", search_start)],
        states={
            SEARCH_TYPE: [
                CallbackQueryHandler(search_type_callback, pattern=r"^(sb_|s_cancel)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_text_input),
            ],
        },
        fallbacks=[CommandHandler("cancel", search_cancel)],
        allow_reentry=True,
    )
