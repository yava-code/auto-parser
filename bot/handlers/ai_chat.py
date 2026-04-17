import logging
import os
import re
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from groq import AsyncGroq
from sqlalchemy import func
from telegram import Update, Message
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from db.session import SessionLocal
from db.models import RawListing, UserUsage
from bot.keyboards import ai_buy_keyboard, back_to_menu

log = logging.getLogger(__name__)

GROQ_MODEL = "qwen/qwen3-32b"
FREE_USES = 5
STARS_PER_PACK = 50
USES_PER_PACK = 10

AI_QUESTION = 0


def _strip_think(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from model output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _get_or_create_usage(session, telegram_id: int) -> UserUsage:
    usage = session.query(UserUsage).filter_by(telegram_id=telegram_id).first()
    if not usage:
        usage = UserUsage(telegram_id=telegram_id, free_uses_left=FREE_USES)
        session.add(usage)
        session.flush()
        log.info("new user %d: granted %d free AI uses", telegram_id, FREE_USES)
    return usage


def _uses_left(usage: UserUsage) -> int:
    return usage.free_uses_left + usage.paid_uses


async def _build_db_context(question: str) -> str:
    """Query DB for relevant context to inject into the AI prompt."""
    session = SessionLocal()
    try:
        total = session.query(func.count(RawListing.id)).scalar() or 0
        avg_p = session.query(func.avg(RawListing.price_eur)).scalar()
        avg_p = float(avg_p) if avg_p else 0

        lines = [
            f"Car listings database: {total:,} total entries.",
            f"Market average price: €{avg_p:,.0f}.",
        ]

        # detect brand mention in question
        brand_rows = (
            session.query(RawListing.brand)
            .filter(RawListing.brand.isnot(None))
            .distinct()
            .all()
        )
        known_brands = [r.brand for r in brand_rows if r.brand]
        q_lower = question.lower()
        mentioned = next((b for b in known_brands if b.lower() in q_lower), None)

        if mentioned:
            stats = session.query(
                func.count(RawListing.id),
                func.avg(RawListing.price_eur),
                func.min(RawListing.price_eur),
                func.max(RawListing.price_eur),
            ).filter(RawListing.brand == mentioned).first()

            lines.append(
                f"\n{mentioned} in DB: {stats[0]} listings, "
                f"avg €{stats[1]:,.0f}, range €{stats[2]:,.0f}–€{stats[3]:,.0f}."
            )

            top5 = (
                session.query(RawListing)
                .filter(RawListing.brand == mentioned, RawListing.price_eur.isnot(None))
                .order_by(RawListing.price_eur)
                .limit(5)
                .all()
            )
            if top5:
                lines.append(f"Cheapest {mentioned}s currently listed:")
                for r in top5:
                    km = f"{r.mileage_km:,} km" if r.mileage_km else "? km"
                    lines.append(
                        f"  - {r.year or '?'} {r.model or ''}, {km}, "
                        f"€{r.price_eur:,.0f}"
                        + (f", {r.fuel_type}" if r.fuel_type else "")
                    )

        return "\n".join(lines)
    finally:
        session.close()


SYSTEM_PROMPT = (
    "You are a knowledgeable car buying assistant specializing in the used car market. "
    "Answer in the same language the user writes in. "
    "Be concise, practical, and data-driven. "
    "When you have database context, reference the actual numbers. "
    "If asked about prices, always mention that market conditions vary."
)


async def _call_groq_streaming(question: str, context: str, msg: Message):
    """Call Groq with streaming and progressively edit the Telegram message."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        await msg.edit_text("⚠️ GROQ_API_KEY not configured.")
        return

    client = AsyncGroq(api_key=api_key)
    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nDatabase context:\n{context}"},
        {"role": "user", "content": question},
    ]

    try:
        stream = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.6,
            max_completion_tokens=4096,
            top_p=0.95,
            reasoning_effort="default",
            stream=True,
            stop=None,
        )
    except Exception as e:
        log.error("groq api error: %s", e)
        await msg.edit_text(f"⚠️ AI error: {e}")
        return

    full_text = ""
    last_edit = 0

    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        full_text += delta

        now = time.time()
        if now - last_edit >= 1.2:
            visible = _strip_think(full_text)
            if visible:
                try:
                    await msg.edit_text(visible[:4096] + " ▊")
                except Exception:
                    pass
            last_edit = now

    final = _strip_think(full_text) or "No response generated."
    try:
        await msg.edit_text(final[:4096], reply_markup=back_to_menu())
    except Exception:
        await msg.reply_text(final[:4096], reply_markup=back_to_menu())

    log.info("groq response: %d chars → %d visible", len(full_text), len(final))


async def ask_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = SessionLocal()
    try:
        usage = _get_or_create_usage(session, user_id)
        left = _uses_left(usage)
        session.commit()
    finally:
        session.close()

    if left <= 0:
        await update.message.reply_text(
            "❌ You've used all your free AI queries\\.\nBuy more to continue:",
            parse_mode="MarkdownV2",
            reply_markup=ai_buy_keyboard(),
        )
        return ConversationHandler.END

    free_tag = f"🎁 {usage.free_uses_left} free" if usage.free_uses_left > 0 else f"💎 {usage.paid_uses} paid"
    await update.message.reply_text(
        f"🤖 *AI Car Assistant* \\({free_tag} uses left\\)\n\n"
        "Ask me anything about cars, prices, or listings\\.\n"
        "Type /cancel to exit\\.",
        parse_mode="MarkdownV2",
    )
    return AI_QUESTION


async def ask_question(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    question = update.message.text.strip()

    session = SessionLocal()
    try:
        usage = _get_or_create_usage(session, user_id)

        if _uses_left(usage) <= 0:
            await update.message.reply_text(
                "❌ No uses left\\. Buy more:",
                parse_mode="MarkdownV2",
                reply_markup=ai_buy_keyboard(),
            )
            session.commit()
            return ConversationHandler.END

        if usage.free_uses_left > 0:
            usage.free_uses_left -= 1
        else:
            usage.paid_uses -= 1
        usage.total_uses += 1
        session.commit()
        left_after = _uses_left(usage)
    finally:
        session.close()

    log.info("user %d asked AI: %.80s", user_id, question)

    thinking_msg = await update.message.reply_text("💭 Thinking...")
    context = await _build_db_context(question)
    await _call_groq_streaming(question, context, thinking_msg)

    # prompt for follow-up
    if left_after > 0:
        await update.message.reply_text(
            f"_\\({left_after} uses remaining — ask another question or /cancel\\)_",
            parse_mode="MarkdownV2",
        )
        return AI_QUESTION
    else:
        await update.message.reply_text(
            "❌ No uses left\\. Buy more:",
            parse_mode="MarkdownV2",
            reply_markup=ai_buy_keyboard(),
        )
        return ConversationHandler.END


async def ask_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 AI chat closed.", reply_markup=back_to_menu())
    return ConversationHandler.END


def ai_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("ask", ask_start)],
        states={
            AI_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question)],
        },
        fallbacks=[CommandHandler("cancel", ask_cancel)],
        allow_reentry=True,
    )
