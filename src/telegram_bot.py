"""Telegram control bot for the automation API.

Started on demand (``python src/telegram_bot.py``) and stopped when idle, so it
must reach polling quickly and log every incoming command at INFO: the idle
watchdog reads the log for activity and ignores the getUpdates polling lines.
"""

import os
import sys
import time

_STARTED_AT = time.perf_counter()

if __name__ == "__main__":
    # Run as a script: the script's own folder (src/) must not shadow top-level
    # packages, and the project root must be importable even without PYTHONPATH.
    _SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    _ROOT_DIR = os.path.dirname(_SRC_DIR)
    sys.path[:] = [
        p
        for p in sys.path
        if os.path.normcase(os.path.abspath(p or ".")) != os.path.normcase(_SRC_DIR)
    ]
    if _ROOT_DIR not in sys.path:
        sys.path.insert(0, _ROOT_DIR)
    # Relative paths in Config (data/, .env lookup) resolve against the project.
    os.chdir(_ROOT_DIR)

import html
import json
import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    TypeHandler,
)

from src.config import Config
from src.utils.formatting import format_log_tail

logger = logging.getLogger("telegram_bot")

# Commands whose arguments may carry secrets and must not reach the log.
_REDACTED_ARG_COMMANDS = {"add_channel"}


def configure_logging():
    """INFO to stderr; silence per-request HTTP logs (one getUpdates line per poll)."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        stream=sys.stderr,
    )
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def describe_update(update):
    """Short, secret-free description of an incoming update for the log."""
    chat = getattr(update, "effective_chat", None)
    chat_id = chat.id if chat else None
    query = getattr(update, "callback_query", None)
    if query is not None:
        return f"button {query.data!r} from chat {chat_id}"
    message = getattr(update, "effective_message", None)
    text = (getattr(message, "text", None) or "").strip()
    if text.startswith("/"):
        command, *args = text.split()
        name = command[1:].split("@", 1)[0].lower()
        if args and name in _REDACTED_ARG_COMMANDS:
            shown = "<redacted>"
        else:
            shown = " ".join(args)
            if len(shown) > 200:
                shown = shown[:200] + "..."
        return f"command {command} {shown}".rstrip() + f" from chat {chat_id}"
    if text:
        return f"text message ({len(text)} chars) from chat {chat_id}"
    return f"update {getattr(update, 'update_id', '?')} from chat {chat_id}"


async def log_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Incoming %s", describe_update(update))


TOKEN = Config.TELEGRAM_BOT_TOKEN
AUTHORIZED_CHAT_ID = Config.TELEGRAM_CHAT_ID
API_BASE_URL = Config.API_BASE_URL
CALLBACK_DATA_LIMIT = 64  # bytes, Telegram's limit for inline button data

# All calls to the control API go through one async client that carries the
# shared token; async so a slow API never blocks polling of other updates.
_api = None


def get_api():
    global _api
    if _api is None or _api.is_closed:
        headers = {"X-API-Token": Config.API_TOKEN} if Config.API_TOKEN else {}
        _api = httpx.AsyncClient(base_url=API_BASE_URL, headers=headers, timeout=15)
    return _api


async def close_api(application=None):
    global _api
    if _api is not None:
        await _api.aclose()
        _api = None


class ApiError(Exception):
    """The control API answered with an error status."""


def api_error(response):
    """Error text from an API response, tolerating non-JSON bodies (proxies, 502s)."""
    try:
        data = response.json()
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("error"):
        return str(data["error"])
    return f"HTTP {response.status_code}"


async def api_json(method, path, **kwargs):
    """Calls the API and returns its JSON body; raises ApiError on 4xx/5xx."""
    response = await getattr(get_api(), method)(path, **kwargs)
    if response.status_code >= 400:
        raise ApiError(api_error(response))
    return response.json()


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
        "/run <i>account_name</i> <i>channel_name</i> - Trigger specific channel\n"
        "/add_channel <i>json</i> - Add new channel configuration\n"
        "/del_channel <i>account_name</i> <i>channel_name</i> - Remove channel from system\n"
        "/run_all - Trigger all channels automation\n"
        "/cleanup - Perform disk cleanup\n"
        "/logs - Get last 50 log lines\n"
        "/disk - View disk usage\n"
        "/help - Show this help"
    )


@restricted
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await api_json("get", "/status", timeout=15)
        status = data.get("status", "Unknown")
        job = data.get("job", "None")
        duration = data.get("duration_seconds", 0)

        msg = f"⚙️ <b>Status:</b> {html.escape(str(status))}\n"
        if status == "Running":
            msg += f"🎬 <b>Job:</b> {html.escape(str(job))}\n"
            msg += f"⏳ <b>Duration:</b> {html.escape(str(duration))}s"

        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching status: {e}")


@restricted
async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all channels with interactive buttons."""
    try:
        channels = await api_json("get", "/channels", timeout=15)

        if not channels:
            await update.message.reply_text("No channels configured.")
            return

        await update.message.reply_html("📺 <b>Configured Channels:</b>")

        for channel in channels:
            account_name = channel["account_name"]
            channel_name = channel["channel_name"]
            title = f"🔹 <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>"
            run_data = f"run:{account_name}:{channel_name}"
            del_data = f"del:{account_name}:{channel_name}"
            if (
                max(len(run_data.encode()), len(del_data.encode()))
                > CALLBACK_DATA_LIMIT
            ):
                # Telegram rejects the whole message if callback data is too long.
                await update.message.reply_html(
                    f"{title}\n<i>Name too long for buttons, use /run or /del_channel.</i>"
                )
                continue
            keyboard = [
                [
                    InlineKeyboardButton("🚀 Run", callback_data=run_data),
                    InlineKeyboardButton("🗑 Delete", callback_data=del_data),
                ]
            ]
            await update.message.reply_html(
                title, reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching channels: {e}")


@restricted
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks from the /channels menu."""
    query = update.callback_query
    await query.answer()

    parts = (query.data or "").split(":", 2)
    if len(parts) != 3:
        logger.warning("Ignoring malformed button data %r", query.data)
        return
    action, account_name, channel_name = parts

    if action == "run":
        try:
            response = await get_api().post(
                "/run/channel",
                params={"account_name": account_name, "channel_name": channel_name},
                timeout=15,
            )
            if response.status_code == 200:
                await query.edit_message_text(
                    f"🚀 <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>: Started successfully!",
                    parse_mode="HTML",
                )
            else:
                err = api_error(response)
                await query.edit_message_text(
                    f"⚠️ <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>: Failed to start ({html.escape(err)})",
                    parse_mode="HTML",
                )
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {html.escape(str(e))}")

    elif action == "del":
        try:
            response = await get_api().delete(
                "/channel",
                params={"account_name": account_name, "channel_name": channel_name},
                timeout=15,
            )
            if response.status_code == 200:
                await query.edit_message_text(
                    f"🗑 <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>: Deleted successfully!",
                    parse_mode="HTML",
                )
            else:
                await query.edit_message_text(
                    f"⚠️ <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>: Failed to delete",
                    parse_mode="HTML",
                )
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {html.escape(str(e))}")


@restricted
async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers a run for a specific channel."""
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /run <account_name> <channel_name>")
        return

    account_name, channel_name = context.args
    try:
        response = await get_api().post(
            "/run/channel",
            params={"account_name": account_name, "channel_name": channel_name},
            timeout=15,
        )
        if response.status_code == 200:
            await update.message.reply_html(
                f"🚀 <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>: Started successfully!"
            )
        else:
            err = api_error(response)
            await update.message.reply_html(
                f"⚠️ <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>: {html.escape(err)}"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {html.escape(str(e))}")


@restricted
async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adds a new channel via JSON."""
    if not context.args:
        await update.message.reply_text(
            'Usage: /add_channel {"account_name": "...", "channel_name": "...", ...}'
        )
        return

    json_str = " ".join(context.args)
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            await update.message.reply_text("❌ Expected a JSON object.")
            return
        response = await get_api().post("/channel", json=data, timeout=15)
        if response.status_code == 201:
            await update.message.reply_html(
                f"✅ <b>{html.escape(str(data.get('account_name')))}/{html.escape(str(data.get('channel_name')))}</b>: Created successfully!"
            )
        else:
            await update.message.reply_html(
                f"⚠️ Failed: {html.escape(api_error(response))}"
            )
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Invalid JSON format.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {html.escape(str(e))}")


@restricted
async def del_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes a specific channel."""
    if len(context.args) != 2:
        await update.message.reply_text(
            "Usage: /del_channel <account_name> <channel_name>"
        )
        return

    account_name, channel_name = context.args
    try:
        response = await get_api().delete(
            "/channel",
            params={"account_name": account_name, "channel_name": channel_name},
            timeout=15,
        )
        if response.status_code == 200:
            await update.message.reply_html(
                f"🗑 <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>: Deleted successfully!"
            )
        else:
            await update.message.reply_html(
                f"⚠️ Failed to delete <b>{html.escape(account_name)}/{html.escape(channel_name)}</b>."
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {html.escape(str(e))}")


@restricted
async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers custom video generation."""
    if not context.args:
        await update.message.reply_text("Usage: /generate <Topic> [en|ru]")
        return

    args = context.args
    lang = "ru"
    topic_words = args

    if len(args) > 1 and args[-1].lower() in ["en", "ru"]:
        lang = args[-1].lower()
        topic_words = args[:-1]

    topic = " ".join(topic_words)

    try:
        response = await get_api().post(
            "/render/custom",
            json={"topic": topic, "lang": lang},
            timeout=15,
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
            err = api_error(response)
            await update.message.reply_html(f"⚠️ <b>Failed:</b> {html.escape(err)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


@restricted
async def run_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = await get_api().post("/run/all", timeout=15)
        if response.status_code == 200:
            await update.message.reply_html(
                "🚀 <b>Execution started!</b> Check /status for progress."
            )
        else:
            await update.message.reply_html(
                f"⚠️ <b>Failed:</b> {html.escape(api_error(response))}"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


@restricted
async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await api_json("post", "/cleanup", timeout=30)
        cleaned = data.get("cleaned_directories", [])
        msg = "🧹 <b>Cleanup finished:</b>\n" + "\n".join(
            f"- {html.escape(str(d))}" for d in cleaned
        )
        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error during cleanup: {e}")


@restricted
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        lines = await api_json("get", "/logs", timeout=15)
        if not isinstance(lines, list):
            raise ValueError(str(lines))
        await update.message.reply_html(format_log_tail(lines))
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching logs: {e}")


@restricted
async def disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stats = await api_json("get", "/disk", timeout=15)
        msg = "💾 <b>Disk Usage:</b>\n"
        for folder, size in stats.items():
            msg += f"- <b>{html.escape(str(folder))}:</b> {html.escape(str(size))}\n"
        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching disk stats: {e}")


def build_application(token):
    application = (
        Application.builder()
        .token(token)
        .concurrent_updates(True)
        .post_shutdown(close_api)
        .build()
    )

    # Group -1 runs before the command handlers, for every update.
    application.add_handler(TypeHandler(Update, log_update), group=-1)

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
    return application


def main():
    configure_logging()
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found.")
        return 1

    application = build_application(TOKEN)
    logger.info(
        "Bot started in %.2fs, polling for commands...",
        time.perf_counter() - _STARTED_AT,
    )
    application.run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
