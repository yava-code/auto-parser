import logging
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from telegram import Update, Message
from telegram.ext import ContextTypes
from db.session import SessionLocal
from db.models import RawListing
from sqlalchemy import func
from bot.keyboards import back_to_menu

log = logging.getLogger(__name__)


async def send_chart(msg: Message):
    session = SessionLocal()
    try:
        rows = (
            session.query(RawListing.mileage_km, RawListing.price_eur, RawListing.brand)
            .filter(
                RawListing.mileage_km.isnot(None),
                RawListing.price_eur.isnot(None),
                RawListing.mileage_km > 0,
                RawListing.price_eur > 0,
            )
            .limit(2000)
            .all()
        )
    finally:
        session.close()

    if not rows:
        await msg.reply_text("📭 No data to chart yet.", reply_markup=back_to_menu())
        return

    km = [r.mileage_km for r in rows]
    price = [r.price_eur for r in rows]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    sc = ax.scatter(km, price, alpha=0.55, s=14, c=price, cmap="plasma", edgecolors="none")
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("Price (€)", color="#e0e0e0", fontsize=10)
    cbar.ax.yaxis.set_tick_params(color="#e0e0e0")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#e0e0e0")

    ax.set_xlabel("Mileage (km)", color="#e0e0e0", fontsize=12)
    ax.set_ylabel("Price (€)", color="#e0e0e0", fontsize=12)
    ax.set_title("Price vs Mileage", color="#ffffff", fontsize=15, fontweight="bold", pad=15)
    ax.tick_params(colors="#c0c0c0")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k"))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x/1000:.0f}k"))
    for spine in ax.spines.values():
        spine.set_edgecolor("#444466")

    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)

    log.info("chart generated: %d points", len(rows))
    await msg.reply_photo(
        photo=buf,
        caption=f"📈 Price vs Mileage — {len(rows):,} listings",
        reply_markup=back_to_menu(),
    )


async def chart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_chart(update.message)
