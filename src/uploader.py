import json
import os
import time
import shutil
from upload_engine.playwright_uploader import upload_video_via_browser

CONFIG_PATH = "../config/channels.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_video_files(folder):
    """Returns a list of .mp4 files in the folder."""
    if not os.path.exists(folder):
        return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".mp4")]


def move_to_archive(file_path):
    """Moves processed file to an 'archive' subfolder."""
    folder = os.path.dirname(file_path)
    archive_dir = os.path.join(folder, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    shutil.move(file_path, os.path.join(archive_dir, os.path.basename(file_path)))
    print(f"Moved {file_path} to {archive_dir}")


def run_automation():
    print("Running YouTube Automation...")
    channels = load_config()

    for channel in channels:
        name = channel.get("channel_name")
        watch_folder = channel.get("watch_folder")
        cookies = channel.get("cookies_path")

        print(f"Checking channel: {name} in {watch_folder}")

        videos = get_video_files(watch_folder)
        if not videos:
            print("No videos found.")
            continue

        for video in videos:
            print(f"Found video: {video}")
            try:
                # Basic metadata fallback
                metadata = {
                    "title": os.path.splitext(os.path.basename(video))[0],
                    "description": "Auto-uploaded video.",
                }

                # Upload
                upload_video_via_browser(
                    video_path=video,
                    metadata=metadata,
                    proxy=channel.get("proxy"),
                    cookies_path=cookies,
                    headless=False,  # Visible for testing
                )

                # Move to archive on success
                move_to_archive(video)

            except Exception as e:
                print(f"Failed to upload {video}: {e}")


if __name__ == "__main__":
    if not os.path.exists(CONFIG_PATH):
        # Fallback for running from src directory
        CONFIG_PATH = "config/channels.json"

    # In a real scenario, this would loop via 'schedule' library
    run_automation()
