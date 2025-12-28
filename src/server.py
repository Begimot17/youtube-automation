import asyncio
import logging
import os
import threading

from flask import Flask, jsonify

from main import load_config, load_history, run_for_channel, run_full_cycle

app = Flask(__name__)
logger = logging.getLogger("server")

# Global lock to prevent multiple overlapping runs if triggered manually
run_lock = threading.Lock()


def start_async_task(coro):
    """Helper to run async coroutines from Flask routes in a background thread."""

    def _target():
        asyncio.run(coro)

    if run_lock.acquire(blocking=False):
        try:
            threading.Thread(target=_target).start()
            return True
        finally:
            run_lock.release()
    return False


@app.route("/stats", methods=["GET"])
def get_stats():
    """Returns the current upload history."""
    try:
        history = load_history()
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/config", methods=["GET"])
def get_config():
    """Returns the current channel configuration."""
    try:
        config = load_config()
        # Strip passwords for security in API response
        safe_config = []
        for c in config:
            c_copy = c.copy()
            if "password" in c_copy:
                c_copy["password"] = "******"
            safe_config.append(c_copy)
        return jsonify(safe_config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/run/all", methods=["POST"])
def run_all():
    """Triggers a full automation cycle for all channels."""
    if start_async_task(run_full_cycle()):
        return jsonify({"status": "Cycle started in background."})
    else:
        return jsonify({"error": "A task is already running."}), 429


@app.route("/run/channel/<string:channel_name>", methods=["POST"])
def run_channel(channel_name):
    """Triggers automation for a specific channel."""
    if start_async_task(run_for_channel(channel_name)):
        return jsonify({"status": f"Job for {channel_name} started in background."})
    else:
        return jsonify({"error": "A task is already running."}), 429


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    from src.utils.logging_config import setup_logging

    setup_logging()

    # Run server on 0.0.0.0 for Docker/n8n access
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
