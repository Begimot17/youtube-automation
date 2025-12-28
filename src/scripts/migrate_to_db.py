import json
import os
import sys
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.utils.db import Channel, SessionLocal, UploadHistory, init_db

CONFIG_PATH = "config/channels.json"
HISTORY_PATH = "config/upload_history.json"


def migrate():
    print("Starting migration from JSON to MySQL...")
    init_db()
    db = SessionLocal()

    try:
        # 1. Migrate Channels
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                channels_data = json.load(f)
                for c_data in channels_data:
                    # Check if channel exists
                    existing = (
                        db.query(Channel)
                        .filter(Channel.channel_name == c_data["channel_name"])
                        .first()
                    )
                    if not existing:
                        channel = Channel(
                            channel_name=c_data["channel_name"],
                            mode=c_data.get("mode", "tiktok"),
                            gmail=c_data.get("gmail"),
                            password=c_data.get("password"),
                            watch_folder=c_data.get("watch_folder"),
                            proxy=c_data.get("proxy"),
                            cookies_path=c_data.get("cookies_path"),
                            upload_frequency_per_day=c_data.get(
                                "upload_frequency_per_day", 1
                            ),
                            min_delay_seconds=c_data.get("min_delay_seconds", 3600),
                            quality=c_data.get("quality", "easy"),
                            lang=c_data.get("lang", "ru"),
                            voice=c_data.get("voice"),
                            tiktok_sources=c_data.get("tiktok_sources", []),
                            genai_topics=c_data.get("genai_topics", []),
                        )
                        db.add(channel)
                        print(f"Added channel: {c_data['channel_name']}")

        db.commit()

        # 2. Migrate Upload History
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                for channel_name, uploads in history_data.items():
                    channel = (
                        db.query(Channel)
                        .filter(Channel.channel_name == channel_name)
                        .first()
                    )
                    if channel:
                        for u_data in uploads:
                            item_id = u_data.get("id")
                            ts = u_data.get("timestamp", 0)
                            dt = (
                                datetime.fromtimestamp(ts)
                                if ts > 0
                                else datetime.utcnow()
                            )

                            # Check if history entry exists
                            existing_upload = (
                                db.query(UploadHistory)
                                .filter(
                                    UploadHistory.channel_id == channel.id,
                                    UploadHistory.item_id == item_id,
                                )
                                .first()
                            )

                            if not existing_upload:
                                upload = UploadHistory(
                                    channel_id=channel.id, item_id=item_id, timestamp=dt
                                )
                                db.add(upload)

        db.commit()
        print("Migration completed successfully.")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
