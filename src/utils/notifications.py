import html
import logging

import requests

from src.config import Config

logger = logging.getLogger("notifications")

TELEGRAM_BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = Config.TELEGRAM_CHAT_ID


TELEGRAM_MAX_LEN = 4096
TELEGRAM_CAPTION_MAX_LEN = 1024


def _redact(error):
    """Error text without the bot token (request errors embed the API URL)."""
    text = str(error)
    if TELEGRAM_BOT_TOKEN:
        text = text.replace(TELEGRAM_BOT_TOKEN, "<token>")
    return text


def truncate_message(message, limit=TELEGRAM_MAX_LEN):
    """Telegram rejects text over 4096 chars; cut with an ellipsis instead of failing."""
    message = str(message)
    if len(message) <= limit:
        return message
    return message[: limit - 1] + "…"


def send_telegram_message(message, parse_mode="HTML"):
    """
    Sends a message via Telegram Bot API with HTML support.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(
            "Telegram notification skipped: Token or Chat ID not configured."
        )
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": truncate_message(message), "parse_mode": parse_mode}

    try:
        response = requests.post(url, json=payload, timeout=30)
        if getattr(response, "status_code", None) == 400 and parse_mode:
            # Usually broken markup (e.g. a tag cut by truncation): resend as
            # plain text rather than lose the notification.
            logger.warning("Telegram rejected formatted message, resending as plain text")
            payload.pop("parse_mode")
            response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {_redact(e)}")
        return False


def send_upload_report(
    account_name, channel_name, title, status="Success", error_msg=None, video_url=None
):
    """
    Sends a formatted upload report to Telegram.
    """
    safe_account = html.escape(str(account_name))
    safe_channel = html.escape(str(channel_name))
    safe_title = html.escape(str(title))
    emoji = "✅" if status == "Success" else "❌"
    message = f"<b>{emoji} YouTube Upload Report</b>\n\n"
    message += f"<b>Account:</b> {safe_account}\n"
    message += f"<b>Channel:</b> {safe_channel}\n"
    message += f"<b>Title:</b> {safe_title}\n"
    message += f"<b>Status:</b> {status}\n"

    if video_url:
        message += f"<b>URL:</b> {html.escape(str(video_url))}\n"

    if error_msg:
        safe_error = html.escape(str(error_msg)[:1500])
        message += f"\n<b>Error:</b> <code>{safe_error}</code>"

    return send_telegram_message(message)


def send_telegram_video(video_path, caption=None, parse_mode=None):
    """
    Sends a video file via Telegram Bot API.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram video skipped: Token or Chat ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"

    try:
        with open(video_path, "rb") as video:
            files = {"video": video}
            data = {"chat_id": TELEGRAM_CHAT_ID}
            if caption:
                data["caption"] = truncate_message(caption, TELEGRAM_CAPTION_MAX_LEN)
                if parse_mode:
                    data["parse_mode"] = parse_mode

            response = requests.post(url, data=data, files=files, timeout=180)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to send Telegram video: {_redact(e)}")
        return False
