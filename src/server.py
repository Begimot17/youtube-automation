import asyncio
import logging
import os
import shutil
import threading
import time

from flask import Flask, jsonify, request

from main import run_for_channel, run_full_cycle
from src.config import Config
from src.factory import create_content
from src.utils.db import Channel, SessionLocal, UploadHistory, init_db
from src.utils.notifications import send_telegram_message, send_telegram_video

app = Flask(__name__)
logger = logging.getLogger("server")

# Global lock to prevent multiple overlapping runs if triggered manually
run_lock = threading.Lock()
job_info = {"status": "Idle", "start_time": None, "current_job": None}


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
        return jsonify([c.channel_name for c in channels])
    finally:
        db.close()


@app.route("/notify", methods=["POST"])
def notify_custom():
    """Allows sending a custom Telegram message via the API."""
    data = request.json
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
    data = request.json
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
    data = request.json
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
            c_name = h.channel.channel_name
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


@app.route("/channel/<string:name>", methods=["GET"])
def get_channel(name):
    """Returns details for a single channel."""
    db = SessionLocal()
    try:
        c = db.query(Channel).filter(Channel.channel_name == name).first()
        if not c:
            return jsonify({"error": "Channel not found"}), 404
        return jsonify(
            {
                "channel_name": c.channel_name,
                "mode": c.mode,
                "gmail": c.gmail,
                "password": "******",
                "watch_folder": c.watch_folder,
                "proxy": c.proxy,
                "cookies_path": c.cookies_path,
                "upload_frequency_per_day": c.upload_frequency_per_day,
                "min_delay_seconds": c.min_delay_seconds,
                "quality": c.quality,
                "lang": c.lang,
                "voice": c.voice,
                "tiktok_sources": c.tiktok_sources,
                "genai_topics": c.genai_topics,
            }
        )
    finally:
        db.close()


@app.route("/channel", methods=["POST"])
def create_channel():
    """Creates a new channel."""
    db = SessionLocal()
    try:
        data = request.json
        if not data or "channel_name" not in data:
            return jsonify({"error": "channel_name is required"}), 400

        existing = (
            db.query(Channel)
            .filter(Channel.channel_name == data["channel_name"])
            .first()
        )
        if existing:
            return jsonify({"error": "Channel already exists"}), 409

        channel = Channel(
            channel_name=data["channel_name"],
            mode=data.get("mode", "genai"),
            gmail=data.get("gmail", ""),
            password=data.get("password", ""),
            watch_folder=data.get("watch_folder", "data/tiktok_downloads"),
            proxy=data.get("proxy", ""),
            cookies_path=data.get(
                "cookies_path", f"auth/cookies_{data['channel_name']}.json"
            ),
            upload_frequency_per_day=data.get("upload_frequency_per_day", 1),
            min_delay_seconds=data.get("min_delay_seconds", 3600),
            quality=data.get("quality", "easy"),
            lang=data.get("lang", "ru"),
            voice=data.get("voice", "ru-RU-SvetlanaNeural"),
            tiktok_sources=data.get("tiktok_sources", []),
            genai_topics=data.get("genai_topics", []),
        )
        db.add(channel)
        db.commit()
        return jsonify(
            {"status": "Channel created", "channel": data["channel_name"]}
        ), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/channel/<string:name>", methods=["DELETE"])
def delete_channel(name):
    """Deletes a channel."""
    db = SessionLocal()
    try:
        channel = db.query(Channel).filter(Channel.channel_name == name).first()
        if not channel:
            return jsonify({"error": "Channel not found"}), 404

        db.delete(channel)
        db.commit()
        return jsonify({"status": "Channel deleted", "channel": name})
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
            new_config = request.json
            if not isinstance(new_config, list):
                return jsonify(
                    {"error": "Config must be a list of channel objects"}
                ), 400

            for c_data in new_config:
                channel = (
                    db.query(Channel)
                    .filter(Channel.channel_name == c_data["channel_name"])
                    .first()
                )
                if not channel:
                    channel = Channel(channel_name=c_data["channel_name"])
                    db.add(channel)

                channel.mode = c_data.get("mode", channel.mode)
                if "gmail" in c_data:
                    channel.gmail = c_data["gmail"]
                if "password" in c_data:
                    channel.password = c_data["password"]
                channel.watch_folder = c_data.get("watch_folder", channel.watch_folder)
                channel.proxy = c_data.get("proxy", channel.proxy)
                channel.cookies_path = c_data.get("cookies_path", channel.cookies_path)
                channel.upload_frequency_per_day = c_data.get(
                    "upload_frequency_per_day", channel.upload_frequency_per_day
                )
                channel.min_delay_seconds = c_data.get(
                    "min_delay_seconds", channel.min_delay_seconds
                )
                channel.quality = c_data.get("quality", channel.quality)
                channel.lang = c_data.get("lang", channel.lang)
                channel.voice = c_data.get("voice", channel.voice)
                channel.tiktok_sources = c_data.get(
                    "tiktok_sources", channel.tiktok_sources
                )
                channel.genai_topics = c_data.get("genai_topics", channel.genai_topics)

            db.commit()
            return jsonify({"status": "Database config updated successfully"})

        channels = db.query(Channel).all()
        safe_config = []
        for c in channels:
            safe_config.append(
                {
                    "channel_name": c.channel_name,
                    "mode": c.mode,
                    "gmail": c.gmail,
                    "password": "******",
                    "watch_folder": c.watch_folder,
                    "proxy": c.proxy,
                    "cookies_path": c.cookies_path,
                    "upload_frequency_per_day": c.upload_frequency_per_day,
                    "min_delay_seconds": c.min_delay_seconds,
                    "quality": c.quality,
                    "lang": c.lang,
                    "voice": c.voice,
                    "tiktok_sources": c.tiktok_sources,
                    "genai_topics": c.genai_topics,
                }
            )
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


@app.route("/run/channel/<string:channel_name>", methods=["POST"])
def run_channel(channel_name):
    """Triggers automation for a specific channel."""
    if start_async_task(run_for_channel(channel_name), f"Channel Run: {channel_name}"):
        return jsonify({"status": f"Job for {channel_name} started in background."})
    else:
        return jsonify({"error": "A task is already running."}), 429


@app.route("/logs", methods=["GET"])
def get_logs():
    """Returns the last 100 lines of the application log."""
    log_file = "logs/app.log"
    if not os.path.exists(log_file):
        return jsonify({"error": "Log file not found"}), 404
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return jsonify(lines[-100:])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/history/reset", methods=["POST"])
def reset_history():
    """Clears history for a specific channel or all channels in DB."""
    channel_name = request.args.get("channel")
    db = SessionLocal()
    try:
        if channel_name:
            channel = (
                db.query(Channel).filter(Channel.channel_name == channel_name).first()
            )
            if channel:
                db.query(UploadHistory).filter(
                    UploadHistory.channel_id == channel.id
                ).delete()
                db.commit()
                return jsonify({"status": f"History cleared for {channel_name}"})
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
    app.run(host="0.0.0.0", port=port)
