import json
import os
import sys
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.config import Config
from src.utils.db import Channel, SessionLocal, UploadHistory, init_db


def migrate():
    print("Starting migration from JSON to DB...")
    init_db()  # Ensures tables are created if they don't exist

    db = SessionLocal()

    try:
        # 1. Migrate Channels
        if os.path.exists(Config.CHANNELS_CONFIG_PATH):
            with open(Config.CHANNELS_CONFIG_PATH, "r", encoding="utf-8") as f:
                channels_data = json.load(f)
                for c_data in channels_data:
                    existing = (
                        db.query(Channel)
                        .filter(Channel.channel_name == c_data["channel_name"])
                        .first()
                    )
                    schedule_data = c_data.get("schedule", ["08:00-20:00"])

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
                            description=c_data.get("description", "#shorts #tiktok"),
                            schedule=schedule_data,
                            tiktok_sources=c_data.get("tiktok_sources", []),
                            genai_topics=c_data.get("genai_topics", []),
                        )
                        db.add(channel)
                        print(f"Creating new channel: {c_data['channel_name']}")
                    else:
                        # Update existing channel
                        existing.mode = c_data.get("mode", existing.mode)
                        existing.gmail = c_data.get("gmail", existing.gmail)
                        existing.password = c_data.get("password", existing.password)
                        existing.watch_folder = c_data.get(
                            "watch_folder", existing.watch_folder
                        )
                        existing.proxy = c_data.get("proxy", existing.proxy)
                        existing.cookies_path = c_data.get(
                            "cookies_path", existing.cookies_path
                        )
                        existing.upload_frequency_per_day = c_data.get(
                            "upload_frequency_per_day",
                            existing.upload_frequency_per_day,
                        )
                        existing.min_delay_seconds = c_data.get(
                            "min_delay_seconds", existing.min_delay_seconds
                        )
                        existing.quality = c_data.get("quality", existing.quality)
                        existing.lang = c_data.get("lang", existing.lang)
                        existing.voice = c_data.get("voice", existing.voice)
                        existing.description = c_data.get(
                            "description", existing.description
                        )
                        existing.schedule = schedule_data
                        existing.tiktok_sources = c_data.get(
                            "tiktok_sources", existing.tiktok_sources
                        )
                        existing.genai_topics = c_data.get(
                            "genai_topics", existing.genai_topics
                        )
                        print(f"Updating existing channel: {c_data['channel_name']}")

        db.commit()

        # 2. Migrate Upload History (if needed)
        if os.path.exists(Config.UPLOAD_HISTORY_PATH):
            with open(Config.UPLOAD_HISTORY_PATH, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                for channel_name, uploads in history_data.items():
                    channel = (
                        db.query(Channel)
                        .filter(Channel.channel_name == channel_name)
                        .first()
                    )
                    if channel:
                        for item_id in uploads:
                            if not isinstance(item_id, str):
                                print(f"Skipping unexpected item in history: {item_id}")
                                continue

                            dt = datetime.utcnow()
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
