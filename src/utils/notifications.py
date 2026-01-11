import html
import logging

import requests

from src.config import Config

logger = logging.getLogger("notifications")

TELEGRAM_BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = Config.TELEGRAM_CHAT_ID


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
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": parse_mode}

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def send_upload_report(
    account_name, channel_name, title, status="Success", error_msg=None
):
    """
    Sends a formatted upload report to Telegram.
    """
    safe_account = html.escape(account_name)
    safe_channel = html.escape(channel_name)
    safe_title = html.escape(title)
    emoji = "✅" if status == "Success" else "❌"
    message = f"<b>{emoji} YouTube Upload Report</b>\n\n"
    message += f"<b>Account:</b> {safe_account}\n"
    message += f"<b>Channel:</b> {safe_channel}\n"
    message += f"<b>Title:</b> {safe_title}\n"
    message += f"<b>Status:</b> {status}\n"

    if error_msg:
        safe_error = html.escape(error_msg)
        message += f"\n<b>Error:</b> <code>{safe_error}</code>"

    return send_telegram_message(message)


def send_telegram_video(video_path, caption=None):
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
                data["caption"] = caption

            response = requests.post(url, data=data, files=files, timeout=180)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to send Telegram video: {e}")
        return False
