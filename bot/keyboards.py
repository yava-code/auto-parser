from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Estimate Price", callback_data="cmd_predict"),
            InlineKeyboardButton("📊 Statistics", callback_data="cmd_stats"),
        ],
        [
            InlineKeyboardButton("🔥 Top Deals", callback_data="cmd_top_deals"),
            InlineKeyboardButton("📈 Price Chart", callback_data="cmd_chart"),
        ],
        [
            InlineKeyboardButton("🔎 Search Cars", callback_data="cmd_search"),
            InlineKeyboardButton("🤖 AI Assistant", callback_data="cmd_ai"),
        ],
    ])


def ai_buy_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Buy 10 uses (50 ⭐)", callback_data="buy_ai_uses")
    ]])


def search_type_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏷️ By Brand", callback_data="search_brand"),
            InlineKeyboardButton("⛽ By Fuel", callback_data="search_fuel"),
        ],
        [
            InlineKeyboardButton("🏆 Top 5 Cheapest", callback_data="search_top5"),
            InlineKeyboardButton("💰 By Price Range", callback_data="search_price"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")],
    ])


def fuel_keyboard():
    fuels = ["Petrol", "Diesel", "Electric", "Hybrid", "LPG", "Petrol+LPG"]
    rows = [fuels[i:i+2] for i in range(0, len(fuels), 2)]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f, callback_data=f"fuel_{f}") for f in row]
        for row in rows
    ] + [[InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")]])


def back_to_menu():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Main Menu", callback_data="cmd_menu")
    ]])
