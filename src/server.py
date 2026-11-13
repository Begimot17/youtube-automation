import asyncio
import collections
import logging
import os
import shutil
import threading
import time

from flask import Flask, jsonify, request

from main import run_for_channel, run_full_cycle
from src.config import Config
from src.factory import create_content
from src.utils.auth import is_authorized
from src.utils.channel_io import apply_channel_update, serialize_channel
from src.utils.db import Channel, SessionLocal, UploadHistory, init_db
from src.utils.notifications import send_telegram_message, send_telegram_video
from src.utils.schedule import normalize_schedule

app = Flask(__name__)
logger = logging.getLogger("server")

# Global lock to prevent multiple overlapping runs if triggered manually
run_lock = threading.Lock()
job_info = {"status": "Idle", "start_time": None, "current_job": None}


@app.before_request
def require_api_token():
    """If API_TOKEN is set, every endpoint except /health needs it."""
    if request.path == "/health":
        return None
    if not is_authorized(request.headers, Config.API_TOKEN):
        return jsonify({"error": "Unauthorized"}), 401
    return None


def json_body():
    """Request JSON or None when the body is missing/invalid (never raises)."""
    return request.get_json(silent=True)


def start_async_task(coro, job_name="Unknown"):
    """Helper to run async coroutines from Flask routes in a background thread."""

    def _target():
        job_info["status"] = "Running"
        job_info["start_time"] = time.time()
        job_info["current_job"] = job_name
        try:
            asyncio.run(coro)
        finally:
            job_info["status"] = "Idle"
            job_info["start_time"] = None
            job_info["current_job"] = None
            run_lock.release()

    if run_lock.acquire(blocking=False):
        try:
            threading.Thread(target=_target).start()
            return True
        except Exception as e:
            run_lock.release()
            logger.error(f"Failed to start thread: {e}")
            return False
    return False


@app.route("/status", methods=["GET"])
def get_status():
    """Returns the current status of background jobs."""
    duration = 0
    if job_info["start_time"]:
        duration = round(time.time() - job_info["start_time"], 2)

    return jsonify(
        {
            "status": job_info["status"],
            "job": job_info["current_job"],
            "duration_seconds": duration,
        }
    )


@app.route("/channels", methods=["GET"])
def list_channels():
    """Returns a simple list of channel names."""
    db = SessionLocal()
    try:
        channels = db.query(Channel).all()
        return jsonify(
            [
                {"account_name": c.account_name, "channel_name": c.channel_name}
                for c in channels
            ]
        )
    finally:
        db.close()


@app.route("/notify", methods=["POST"])
def notify_custom():
    """Allows sending a custom Telegram message via the API."""
    data = json_body()
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body is required"}), 400
    msg = data.get("message")
    if not msg:
        return jsonify({"error": "Message is required"}), 400

    success = send_telegram_message(msg)
    return jsonify({"success": success})


@app.route("/disk", methods=["GET"])
def get_disk_usage():
    """Returns disk usage for data and logs directories."""
    stats = {}
    for folder in ["data", "logs"]:
        path = os.path.abspath(folder)
        if os.path.exists(path):
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
            stats[folder] = f"{total_size / (1024 * 1024):.2f} MB"
        else:
            stats[folder] = "0 MB"
    return jsonify(stats)


@app.route("/render/test", methods=["POST"])
def render_test():
    """Triggers a test render without uploading."""
    data = json_body()
    if not isinstance(data, dict):
        data = {}
    topic = data.get("topic", "Test Topic")
    channel = data.get("channel", "TestChannel")
    lang = data.get("lang", "ru")

    if start_async_task(
        asyncio.to_thread(create_content, topic, channel, lang),
        f"Test Render: {topic}",
    ):
        return jsonify({"status": "Test render started in background."})
    else:
        return jsonify({"error": "A task is already running."}), 429


@app.route("/render/custom", methods=["POST"])
def render_custom():
    """Triggers a custom video generation and sends to Telegram."""
    data = json_body()
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body is required"}), 400
    topic = data.get("topic")
    lang = data.get("lang", "ru")

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    def _task():
        try:
            logger.info(f"Custom render started for topic: {topic}")
            video_path = create_content(
                topic, channel_name="CustomOrder", language=lang
            )
            if video_path and os.path.exists(video_path):
                send_telegram_video(
                    video_path,
                    caption=f"🎬 <b>Custom Video Ready!</b>\nTopic: {topic}\nLang: {lang}",
                )
                logger.info(f"Custom video sent to Telegram: {video_path}")
            else:
                send_telegram_message(
                    f"❌ <b>Generation Failed</b>\nTopic: {topic}\nCould not create video."
                )
        except Exception as e:
            logger.error(f"Error in custom render task: {e}")
            send_telegram_message(
                f"❌ <b>Error</b>\nTopic: {topic}\nError: <code>{str(e)}</code>"
            )

    # We use a standard thread for this specific one since it's not a standard job
    # But we still want to ensure we don't block the API
    threading.Thread(target=_task).start()
    return jsonify(
        {"status": "Custom generation started. Video will be sent to Telegram."}
    )


@app.route("/stats", methods=["GET"])
def get_stats():
    """Returns the current upload history from DB."""
    db = SessionLocal()
    try:
        history = db.query(UploadHistory).all()
        result = {}
        for h in history:
            c_name = f"{h.channel.account_name}/{h.channel.channel_name}"
            if c_name not in result:
                result[c_name] = []
            result[c_name].append(
                {"id": h.item_id, "timestamp": h.timestamp.timestamp()}
            )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/channel", methods=["GET"])
def get_channel():
    """Returns details for a single channel."""
    account_name = request.args.get("account_name")
    channel_name = request.args.get("channel_name")
    if not account_name or not channel_name:
        return jsonify({"error": "account_name and channel_name are required"}), 400

    db = SessionLocal()
    try:
        c = (
            db.query(Channel)
            .filter(
                Channel.account_name == account_name,
                Channel.channel_name == channel_name,
            )
            .first()
        )
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        return jsonify(serialize_channel(c))
    finally:
        db.close()


@app.route("/channel", methods=["POST"])
def create_channel():
    """Creates a new channel."""
    db = SessionLocal()
    try:
        data = json_body()
        if (
            not isinstance(data, dict)
            or not data.get("channel_name")
            or not data.get("account_name")
        ):
            return jsonify({"error": "account_name and channel_name are required"}), 400
        try:
            schedule = normalize_schedule(data.get("schedule"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        existing = (
            db.query(Channel)
            .filter(
                Channel.account_name == data["account_name"],
                Channel.channel_name == data["channel_name"],
            )
            .first()
        )
        if existing:
            return jsonify(
                {
                    "error": "Channel with this account_name and channel_name already exists"
                }
            ), 409

        channel = Channel(
            channel_name=data["channel_name"],
            account_name=data["account_name"],
            mode=data.get("mode", "genai"),
            gmail=data.get("gmail", ""),
            password=data.get("password", ""),
            watch_folder=data.get("watch_folder", "data/tiktok_downloads"),
            proxy=data.get("proxy", ""),
            upload_frequency_per_day=data.get("upload_frequency_per_day", 1),
            min_delay_seconds=data.get("min_delay_seconds", 3600),
            quality=data.get("quality", "easy"),
            lang=data.get("lang", "ru"),
            voice=data.get("voice", "ru-RU-SvetlanaNeural"),
            schedule=schedule,
            tiktok_sources=data.get("tiktok_sources", []),
            genai_topics=data.get("genai_topics", []),
        )
        db.add(channel)
        db.commit()
        return jsonify(
            {
                "status": "Channel created",
                "account_name": data["account_name"],
                "channel_name": data["channel_name"],
            }
        ), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/channel", methods=["DELETE"])
def delete_channel():
    """Deletes a channel."""
    account_name = request.args.get("account_name")
    channel_name = request.args.get("channel_name")
    if not account_name or not channel_name:
        return jsonify({"error": "account_name and channel_name are required"}), 400

    db = SessionLocal()
    try:
        channel = (
            db.query(Channel)
            .filter(
                Channel.account_name == account_name,
                Channel.channel_name == channel_name,
            )
            .first()
        )
        if not channel:
            return jsonify({"error": "Channel not found"}), 404

        db.delete(channel)
        db.commit()
        return jsonify(
            {
                "status": "Channel deleted",
                "account_name": account_name,
                "channel_name": channel_name,
            }
        )
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/config", methods=["GET", "POST"])
def manage_config():
    """Returns or updates the current channel configuration in DB."""
    db = SessionLocal()
    try:
        if request.method == "POST":
            new_config = json_body()
            if not isinstance(new_config, list):
                return jsonify(
                    {"error": "Config must be a list of channel objects"}
                ), 400

            for c_data in new_config:
                if not isinstance(c_data, dict):
                    continue
                account_name = c_data.get("account_name")
                channel_name = c_data.get("channel_name")
                if not account_name or not channel_name:
                    continue

                channel = (
                    db.query(Channel)
                    .filter(
                        Channel.account_name == account_name,
                        Channel.channel_name == channel_name,
                    )
                    .first()
                )
                if not channel:
                    channel = Channel(
                        account_name=account_name, channel_name=channel_name
                    )
                    db.add(channel)

                try:
                    apply_channel_update(channel, c_data)
                except ValueError as e:
                    db.rollback()
                    return jsonify(
                        {"error": f"{account_name}/{channel_name}: {e}"}
                    ), 400

            db.commit()
            return jsonify({"status": "Database config updated successfully"})

        safe_config = [serialize_channel(c) for c in db.query(Channel).all()]
        return jsonify(safe_config)
    except Exception as e:
        logger.error(f"Config API Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/run/all", methods=["POST"])
def run_all():
    """Triggers a full automation cycle for all channels."""
    if start_async_task(run_full_cycle(), "Full Cycle"):
        return jsonify({"status": "Cycle started in background."})
    else:
        return jsonify({"error": "A task is already running."}), 429


@app.route("/run/channel", methods=["POST"])
def run_channel_route():
    """Triggers automation for a specific channel."""
    account_name = request.args.get("account_name")
    channel_name = request.args.get("channel_name")
    if not account_name or not channel_name:
        return jsonify({"error": "account_name and channel_name are required"}), 400

    if start_async_task(
        run_for_channel(account_name, channel_name),
        f"Channel Run: {account_name}/{channel_name}",
    ):
        return jsonify(
            {"status": f"Job for {account_name}/{channel_name} started in background."}
        )
    else:
        return jsonify({"error": "A task is already running."}), 429


@app.route("/logs", methods=["GET"])
def get_logs():
    """Returns the last 100 lines of the application log."""
    log_file = "logs/app.log"
    if not os.path.exists(log_file):
        return jsonify({"error": "Log file not found"}), 404
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            return jsonify(list(collections.deque(f, maxlen=100)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/history/reset", methods=["POST"])
def reset_history():
    """Clears history for a specific channel or all channels in DB."""
    account_name = request.args.get("account_name")
    channel_name = request.args.get("channel_name")
    db = SessionLocal()
    try:
        if account_name and channel_name:
            channel = (
                db.query(Channel)
                .filter(
                    Channel.account_name == account_name,
                    Channel.channel_name == channel_name,
                )
                .first()
            )
            if channel:
                db.query(UploadHistory).filter(
                    UploadHistory.channel_id == channel.id
                ).delete()
                db.commit()
                return jsonify(
                    {"status": f"History cleared for {account_name}/{channel_name}"}
                )
            return jsonify({"error": "Channel not found"}), 404
        else:
            db.query(UploadHistory).delete()
            db.commit()
            return jsonify({"status": "All history cleared"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/cleanup", methods=["POST"])
def disk_cleanup():
    """Removes temporary downloads and generated videos."""
    dirs_to_clean = ["data/tiktok_downloads", "data/output", "data/temp_audio"]
    cleaned = []
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d)
            os.makedirs(d)
            cleaned.append(d)
    return jsonify({"status": "Cleanup finished", "cleaned_directories": cleaned})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    from src.utils.logging_config import setup_logging

    setup_logging()
    init_db()

    # Run server on 0.0.0.0 for Docker/n8n access
    port = Config.PORT
    if not Config.API_TOKEN:
        logger.warning(
            "API_TOKEN is not set: the control API is open to anyone who can reach it."
        )
    app.run(host="0.0.0.0", port=port)
