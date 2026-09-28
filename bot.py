#!/usr/bin/env python3
"""
Garrett Assistant Bot — Telegram interface to Hermes/Garrett.
Provides business data, reminders, and conversational assistance.
"""

import os
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("garrett-assistant")

# ── Environment ──────────────────────────────────────────────────────────────
GARRETT_BOT_TOKEN = os.environ.get("GARRETT_BOT_TOKEN", "")
LOLO_BUDS_API_KEY = os.environ.get("LOLO_BUDS_FULL_READ_API_KEY", "")
LOLO_BUDS_BASE = "https://lolobuds.vip/api"
BREN_CHAT_ID = int(os.environ.get("BREN_TELEGRAM_CHAT_ID", "1608993620"))

# ── Allowed users (Bren only for now) ────────────────────────────────────────
ALLOWED_USERS = {1608993620}  # Bren's Telegram user ID


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized."""
    return user_id in ALLOWED_USERS


# ── Lolo Buds API helpers ────────────────────────────────────────────────────
def api_get(resource: str, params: dict = None) -> dict:
    """Make a GET request to Lolo Buds API."""
    url = f"{LOLO_BUDS_BASE}/query?resource={resource}"
    if params:
        for k, v in params.items():
            if v is not None:
                url += f"&{k}={urllib.parse.quote(str(v))}"
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {LOLO_BUDS_API_KEY}")
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.error(f"API error: {e}")
        return {"error": str(e)}


def get_today_str() -> str:
    """Get today's date string in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def get_week_range() -> tuple:
    """Get this week's date range (Monday to today)."""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


# ── Command handlers ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized. This bot is private.")
        return
    
    welcome = (
        "🤖 **Garrett Assistant**\n\n"
        "Hey Bren! I'm Garrett, your digital chief of staff.\n\n"
        "📋 **Available Commands:**\n"
        "/sales — Today's sales across all branches\n"
        "/branches — List all branches\n"
        "/expenses — Recent expenses\n"
        "/status — System status check\n"
        "/help — Show this message\n\n"
        "Or just chat with me — I'll do my best to help!"
    )
    
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("/sales"), KeyboardButton("/branches")],
            [KeyboardButton("/expenses"), KeyboardButton("/status")],
        ],
        resize_keyboard=True,
    )
    
    await update.message.reply_text(welcome, reply_markup=keyboard, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not is_authorized(update.effective_user.id):
        return
    await start(update, context)


async def sales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sales command — fetch today's sales."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    await update.message.reply_text("📊 Fetching today's sales...")
    
    today = get_today_str()
    data = api_get("sales", {"from": today, "to": today})
    
    if "error" in data:
        await update.message.reply_text(f"❌ API Error: {data['error']}")
        return
    
    rows = data.get("rows", [])
    total = data.get("total_count", 0)
    
    if not rows:
        await update.message.reply_text("📭 No sales recorded today.")
        return
    
    # Group sales by branch
    branch_sales = {}
    for sale in rows:
        branch = sale.get("branch_name", "Unknown")
        amount = sale.get("total_amount", 0)
        if branch not in branch_sales:
            branch_sales[branch] = {"count": 0, "total": 0}
        branch_sales[branch]["count"] += 1
        branch_sales[branch]["total"] += amount
    
    # Format response
    lines = [f"📊 **Sales Today ({today})**\n"]
    grand_total = 0
    for branch, stats in sorted(branch_sales.items()):
        grand_total += stats["total"]
        lines.append(
            f"• **{branch}**: {stats['count']} orders — ₱{stats['total']:,.2f}"
        )
    
    lines.append(f"\n**Grand Total: ₱{grand_total:,.2f}** ({total} orders)")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def branches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /branches command — list all branches."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    data = api_get("branches")
    
    if "error" in data:
        await update.message.reply_text(f"❌ API Error: {data['error']}")
        return
    
    rows = data.get("rows", [])
    
    if not rows:
        await update.message.reply_text("📭 No branches found.")
        return
    
    lines = [f"🏪 **Lolo Buds Branches** ({len(rows)} total)\n"]
    for branch in rows:
        name = branch.get("name", "Unknown")
        branch_id = branch.get("id", "N/A")
        status = "🟢" if branch.get("is_active", True) else "🔴"
        lines.append(f"{status} **{name}** (ID: {branch_id})")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /expenses command — recent expenses."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    await update.message.reply_text("💰 Fetching recent expenses...")
    
    data = api_get("expenses", {"limit": 10})
    
    if "error" in data:
        await update.message.reply_text(f"❌ API Error: {data['error']}")
        return
    
    rows = data.get("rows", [])
    
    if not rows:
        await update.message.reply_text("📭 No expenses found.")
        return
    
    lines = [f"💰 **Recent Expenses** (showing {len(rows)})\n"]
    for exp in rows:
        branch = exp.get("branch_name", "Unknown")
        amount = exp.get("amount", 0)
        desc = exp.get("description", "No description")
        date = exp.get("created_at", "")[:10]
        lines.append(f"• **{branch}** — ₱{amount:,.2f}\n  {desc} ({date})")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command — system status check."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    # Check Lolo Buds API
    api_status = "🟢 Online"
    try:
        data = api_get("branches")
        if "error" in data:
            api_status = f"🔴 Error: {data['error'][:50]}"
    except Exception as e:
        api_status = f"🔴 Offline: {str(e)[:50]}"
    
    status_msg = (
        "🔧 **System Status**\n\n"
        f"• **Garrett Bot**: 🟢 Running\n"
        f"• **Lolo Buds API**: {api_status}\n"
        f"• **Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"• **Uptime**: Active since last deploy\n"
    )
    
    await update.message.reply_text(status_msg, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    text = update.message.text.lower()
    
    # Simple keyword-based responses
    if any(word in text for word in ["hello", "hi", "hey", "kumusta"]):
        response = "Hey Bren! 👋 How can I help you today?"
    elif any(word in text for word in ["sales", "kita", "benta"]):
        await sales(update, context)
        return
    elif any(word in text for word in ["branch", "store", "tindahan"]):
        await branches(update, context)
        return
    elif any(word in text for word in ["expense", "gastos", "bayad"]):
        await expenses(update, context)
        return
    elif any(word in text for word in ["status", "kumusta system"]):
        await status(update, context)
        return
    elif any(word in text for word in ["thank", "salamat"]):
        response = "You're welcome, Bren! Always here to help. 💪"
    else:
        response = (
            "I'm still learning! For now, I can help with:\n"
            "• /sales — Check today's sales\n"
            "• /branches — List branches\n"
            "• /expenses — Recent expenses\n"
            "• /status — System check\n\n"
            "Or ask me about sales, branches, or expenses!"
        )
    
    await update.message.reply_text(response)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ Something went wrong. Please try again.")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    """Start the bot."""
    if not GARRETT_BOT_TOKEN:
        logger.error("GARRETT_BOT_TOKEN not set!")
        return
    
    logger.info("Starting Garrett Assistant Bot...")
    
    app = Application.builder().token(GARRETT_BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("sales", sales))
    app.add_handler(CommandHandler("branches", branches))
    app.add_handler(CommandHandler("expenses", expenses))
    app.add_handler(CommandHandler("status", status))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()