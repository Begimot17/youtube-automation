import json
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.utils.db import Channel, SessionLocal

CONFIG_PATH = "config/channels.json"


def sync_voices():
    print("Syncing voices from JSON to DB...")
    db = SessionLocal()
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                channels_data = json.load(f)
                for c_data in channels_data:
                    name = c_data["channel_name"]
                    voice = c_data.get("voice")
                    if voice:
                        channel = (
                            db.query(Channel)
                            .filter(Channel.channel_name == name)
                            .first()
                        )
                        if channel:
                            channel.voice = voice
                            print(f"Updated voice for {name}: {voice}")
            db.commit()
            print("Sync completed.")
        else:
            print("Config file not found.")
    except Exception as e:
        db.rollback()
        print(f"Sync failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    sync_voices()
