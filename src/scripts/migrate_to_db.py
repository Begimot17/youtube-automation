import json
import os
import sys
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.config import Config
from src.utils.channel_io import CREATE_DEFAULTS, fields_from_json
from src.utils.db import Channel, SessionLocal, UploadHistory, init_db
from src.utils.schedule import normalize_schedule


def sync_channel(db, c_data):
    """Creates or updates one channel from a channels.json entry."""
    channel_name = c_data["channel_name"]
    account_name = c_data.get("account_name") or channel_name
    fields = fields_from_json(c_data)

    existing = (
        db.query(Channel)
        .filter(
            Channel.account_name == account_name,
            Channel.channel_name == channel_name,
        )
        .first()
    )
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        print(f"Updating existing channel: {account_name}/{channel_name}")
        return existing

    values = {**CREATE_DEFAULTS, **fields}
    values.setdefault("schedule", normalize_schedule(None))
    channel = Channel(channel_name=channel_name, account_name=account_name, **values)
    db.add(channel)
    print(f"Creating new channel: {account_name}/{channel_name}")
    return channel


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
                    try:
                        sync_channel(db, c_data)
                    except (KeyError, ValueError, TypeError) as e:
                        print(f"Skipping invalid channel entry {c_data!r}: {e}")

        db.commit()

        # 2. Migrate Upload History (if needed)
        if os.path.exists(Config.UPLOAD_HISTORY_PATH):
            with open(Config.UPLOAD_HISTORY_PATH, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                for channel_name, uploads in history_data.items():
                    # This part is tricky as we don't have account_name in old history.
                    # We'll assume the first channel found with that name is the correct one.
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
