import html
import json
import logging

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.config import Config

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("telegram_bot")

TOKEN = Config.TELEGRAM_BOT_TOKEN
AUTHORIZED_CHAT_ID = Config.TELEGRAM_CHAT_ID
API_BASE_URL = "http://server:5000"


def restricted(func):
    """Decorator to restrict access to the authorized user."""

    async def wrapped(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        effective_chat = update.effective_chat
        if not effective_chat:
            return
        user_id = str(effective_chat.id)
        if user_id != AUTHORIZED_CHAT_ID:
            logger.warning(f"Unauthorized access attempt by {user_id}")
            # Silently ignore or send a generic message
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "🤖 <b>YouTube Automation Control Bot</b>\n\n"
        "Available commands:\n"
        "/status - Get engine status\n"
        "/channels - Manage channels (List / Run / Delete)\n"
        "/generate &lt;topic&gt; [en|ru] - Generate video & send to chat\n"
        "/run <i>name</i> - Trigger specific channel\n"
        "/add_channel <i>json</i> - Add new channel configuration\n"
        "/del_channel <i>name</i> - Remove channel from system\n"
        "/run_all - Trigger all channels automation\n"
        "/cleanup - Perform disk cleanup\n"
        "/logs - Get last 50 log lines\n"
        "/disk - View disk usage\n"
        "/help - Show this help"
    )


@restricted
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{API_BASE_URL}/status", timeout=5)
        data = response.json()
        status = data.get("status", "Unknown")
        job = data.get("job", "None")
        duration = data.get("duration_seconds", 0)

        msg = f"⚙️ <b>Status:</b> {status}\n"
        if status == "Running":
            msg += f"🎬 <b>Job:</b> {job}\n"
            msg += f"⏳ <b>Duration:</b> {duration}s"

        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching status: {e}")


@restricted
async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all channels with interactive buttons."""
    try:
        response = requests.get(f"{API_BASE_URL}/channels", timeout=5)
        channels = response.json()

        if not channels:
            await update.message.reply_text("No channels configured.")
            return

        await update.message.reply_html("📺 <b>Configured Channels:</b>")

        for name in channels:
            keyboard = [
                [
                    InlineKeyboardButton("🚀 Run", callback_data=f"run:{name}"),
                    InlineKeyboardButton("🗑 Delete", callback_data=f"del:{name}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"🔹 <b>{name}</b>", reply_markup=reply_markup, parse_mode="HTML"
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching channels: {e}")


@restricted
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks from the /channels menu."""
    query = update.callback_query
    await query.answer()

    data = query.data
    action, name = data.split(":", 1)

    if action == "run":
        try:
            response = requests.post(f"{API_BASE_URL}/run/channel/{name}", timeout=5)
            if response.status_code == 200:
                await query.edit_message_text(
                    f"🚀 <b>{html.escape(name)}</b>: Started successfully!",
                    parse_mode="HTML",
                )
            else:
                err = response.json().get("error", "Unknown error")
                await query.edit_message_text(
                    f"⚠️ <b>{html.escape(name)}</b>: Failed to start ({html.escape(err)})",
                    parse_mode="HTML",
                )
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {html.escape(str(e))}")

    elif action == "del":
        try:
            response = requests.delete(f"{API_BASE_URL}/channel/{name}", timeout=5)
            if response.status_code == 200:
                await query.edit_message_text(
                    f"🗑 <b>{html.escape(name)}</b>: Deleted successfully!",
                    parse_mode="HTML",
                )
            else:
                await query.edit_message_text(
                    f"⚠️ <b>{html.escape(name)}</b>: Failed to delete", parse_mode="HTML"
                )
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {html.escape(str(e))}")


@restricted
async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers a run for a specific channel."""
    if not context.args:
        await update.message.reply_text("Usage: /run <channel_name>")
        return

    name = context.args[0]
    try:
        response = requests.post(f"{API_BASE_URL}/run/channel/{name}", timeout=5)
        if response.status_code == 200:
            await update.message.reply_html(
                f"🚀 <b>{html.escape(name)}</b>: Started successfully!"
            )
        else:
            err = response.json().get("error", "Unknown error")
            await update.message.reply_html(
                f"⚠️ <b>{html.escape(name)}</b>: {html.escape(err)}"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {html.escape(str(e))}")


@restricted
async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adds a new channel via JSON."""
    if not context.args:
        await update.message.reply_text(
            'Usage: /add_channel {"channel_name": "...", ...}'
        )
        return

    json_str = " ".join(context.args)
    try:
        data = json.loads(json_str)
        response = requests.post(f"{API_BASE_URL}/channel", json=data, timeout=5)
        if response.status_code == 201:
            await update.message.reply_html(
                f"✅ <b>{html.escape(data['channel_name'])}</b>: Created successfully!"
            )
        else:
            err = response.json().get("error", "Unknown error")
            await update.message.reply_html(f"⚠️ Failed: {html.escape(err)}")
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Invalid JSON format.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {html.escape(str(e))}")


@restricted
async def del_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes a specific channel."""
    if not context.args:
        await update.message.reply_text("Usage: /del_channel <channel_name>")
        return

    name = context.args[0]
    try:
        response = requests.delete(f"{API_BASE_URL}/channel/{name}", timeout=5)
        if response.status_code == 200:
            await update.message.reply_html(
                f"🗑 <b>{html.escape(name)}</b>: Deleted successfully!"
            )
        else:
            await update.message.reply_html(
                f"⚠️ Failed to delete <b>{html.escape(name)}</b>."
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {html.escape(str(e))}")


@restricted
async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers custom video generation."""
    if not context.args:
        await update.message.reply_text('Usage: /generate <Topic> [en|ru]')
        return

    args = context.args
    lang = "ru"
    topic_words = args

    if len(args) > 1 and args[-1].lower() in ["en", "ru"]:
        lang = args[-1].lower()
        topic_words = args[:-1]

    topic = " ".join(topic_words)

    try:
        response = requests.post(
            f"{API_BASE_URL}/render/custom",
            json={"topic": topic, "lang": lang},
            timeout=5,
        )
        if response.status_code == 200:
            safe_topic = html.escape(topic)
            safe_lang = html.escape(lang)
            await update.message.reply_html(
                f"🎬 <b>Generation started!</b>\n"
                f"Topic: <i>{safe_topic}</i>\n"
                f"Language: <i>{safe_lang}</i>\n\n"
                f"The video will be sent to you automatically when ready."
            )
        else:
            err = response.json().get("error", "Unknown error")
            await update.message.reply_html(f"⚠️ <b>Failed:</b> {err}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


@restricted
async def run_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.post(f"{API_BASE_URL}/run/all", timeout=5)
        data = response.json()
        if response.status_code == 200:
            await update.message.reply_html(
                "🚀 <b>Execution started!</b> Check /status for progress."
            )
        else:
            await update.message.reply_html(
                f"⚠️ <b>Failed:</b> {data.get('error', 'Unknown error')}"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


@restricted
async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.post(f"{API_BASE_URL}/cleanup", timeout=10)
        data = response.json()
        cleaned = data.get("cleaned_directories", [])
        msg = "🧹 <b>Cleanup finished:</b>\n" + "\n".join([f"- {d}" for d in cleaned])
        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error during cleanup: {e}")


@restricted
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{API_BASE_URL}/logs", timeout=5)
        lines = response.json()
        # Take last 50 lines to keep message size reasonable
        log_text = "".join(lines[-50:])
        if not log_text:
            log_text = "No logs available."

        # Split into several messages if too long for Telegram (4096 chars)
        if len(log_text) > 4000:
            log_text = log_text[-4000:]

        await update.message.reply_html(f"📋 <b>Last Logs:</b>\n<pre>{log_text}</pre>")
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching logs: {e}")


@restricted
async def disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{API_BASE_URL}/disk", timeout=5)
        stats = response.json()
        msg = "💾 <b>Disk Usage:</b>\n"
        for folder, size in stats.items():
            msg += f"- <b>{folder}:</b> {size}\n"
        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching disk stats: {e}")


def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found.")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("channels", channels_command))
    application.add_handler(CommandHandler("run", run_command))
    application.add_handler(CommandHandler("add_channel", add_channel_command))
    application.add_handler(CommandHandler("del_channel", del_channel_command))
    application.add_handler(CommandHandler("run_all", run_all_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(CommandHandler("cleanup", cleanup_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("disk", disk_command))

    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot started and waiting for commands...")
    application.run_polling()


if __name__ == "__main__":
    main()
