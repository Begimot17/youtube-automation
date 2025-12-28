import asyncio
import json
import logging
import os
import time
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv

from src.sources.tiktok_downloader import TikTokDownloader
from src.upload_engine.playwright_uploader import upload_video_via_browser
from src.utils.logging_config import setup_logging
from src.factory import create_content

# Load environment variables
load_dotenv()

# Configure logging
setup_logging()
logger = logging.getLogger("main")

CONFIG_PATH = "config/channels.json"
HISTORY_PATH = "config/upload_history.json"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file not found: {CONFIG_PATH}")
        return []
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history():
    """
    History structure:
    {
        "channel_name": [
            {"id": "video123", "timestamp": 1700000000},
            ...
        ]
    }
    """
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Migration check: if values are list of strings, convert to list of dicts
                for channel in data:
                    if data[channel] and isinstance(data[channel][0], str):
                        data[channel] = [
                            {"id": vid, "timestamp": 0} for vid in data[channel]
                        ]
                return data
        except Exception:
            return {}
    return {}


def save_history(history):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)


def get_channel_uploads_last_24h(history, channel_name):
    uploads = history.get(channel_name, [])
    now = time.time()
    day_ago = now - 86400
    return [u for u in uploads if u.get("timestamp", 0) > day_ago]


def get_last_upload_time(history, channel_name):
    uploads = history.get(channel_name, [])
    if not uploads:
        return 0
    return max(u.get("timestamp", 0) for u in uploads)


def is_item_processed(history, channel_name, item_id):
    uploads = history.get(channel_name, [])
    return any(u.get("id") == item_id for u in uploads)


def mark_item_processed(history, channel_name, item_id):
    if channel_name not in history:
        history[channel_name] = []
    history[channel_name].append({"id": item_id, "timestamp": time.time()})


def can_upload(channel, history):
    channel_name = channel.get("channel_name")
    freq = channel.get("upload_frequency_per_day", 1)
    min_delay = channel.get("min_delay_seconds", 3600)

    # 1. Frequency check
    recent_uploads = get_channel_uploads_last_24h(history, channel_name)
    if len(recent_uploads) >= freq:
        logger.info(
            f"Skipping {channel_name}: Daily limit reached ({len(recent_uploads)}/{freq})"
        )
        return False

    # 2. Delay check
    last_time = get_last_upload_time(history, channel_name)
    now = time.time()
    if now - last_time < min_delay:
        remaining = int(min_delay - (now - last_time))
        logger.info(f"Skipping {channel_name}: Minimum delay active. Wait {remaining}s")
        return False

    return True


async def process_tiktok_channel(channel, downloader, history):
    if not can_upload(channel, history):
        return

    channel_name = channel.get("channel_name")
    tiktok_sources = channel.get("tiktok_sources", [])
    watch_folder = channel.get("watch_folder", "data/tiktok_downloads")
    cookies = channel.get("cookies_path")
    proxy = channel.get("proxy")

    logger.info(f"--- Processing TikTok Channel: {channel_name} ---")

    for tt_user in tiktok_sources:
        logger.info(f"Checking TikTok user: @{tt_user}")
        videos = await downloader.get_user_videos(tt_user, count=5)

        if not videos:
            continue

        for video in videos:
            video_id = video.get("id")
            if not video_id or is_item_processed(history, channel_name, video_id):
                continue

            logger.info(f"Found new TikTok video: {video_id}")

            output_path = os.path.join(watch_folder, f"{tt_user}_{video_id}.mp4")
            os.makedirs(watch_folder, exist_ok=True)

            success = await downloader.download_video(video, output_path)
            if not success:
                continue

            metadata = {
                "title": (video.get("title", "")[:70] + " #shorts #tiktok"),
                "description": f"Original video by @{tt_user} on TikTok. #shorts #tiktok",
                "gmail": channel.get("gmail"),
                "password": channel.get("password"),
            }

            try:
                await asyncio.to_thread(
                    upload_video_via_browser,
                    video_path=os.path.abspath(output_path),
                    metadata=metadata,
                    proxy=proxy,
                    cookies_path=cookies,
                    headless=True,
                )
                mark_item_processed(history, channel_name, video_id)
                save_history(history)
                logger.info(f"TikTok video {video_id} uploaded successfully.")
                return  # Only one per run to respect delays
            except Exception as e:
                logger.error(f"TikTok upload failed: {e}")


async def process_genai_channel(channel, history):
    if not can_upload(channel, history):
        return

    channel_name = channel.get("channel_name")
    topics = channel.get("genai_topics", [])
    lang = channel.get("lang", "ru")
    cookies = channel.get("cookies_path")
    proxy = channel.get("proxy")

    logger.info(f"--- Processing GenAI Channel: {channel_name} ---")

    if not topics:
        return

    # Choose a topic
    topic = random.choice(topics)
    item_id = f"genai_{topic.replace(' ', '_').lower()}_{lang}"

    if is_item_processed(history, channel_name, item_id):
        logger.info(f"Topic already processed: {topic}")
        return

    logger.info(f"Generating video for topic: {topic} ({lang})")

    try:
        video_path = await asyncio.to_thread(
            create_content, topic=topic, channel_name=channel_name, language=lang
        )

        if not video_path or not os.path.exists(video_path):
            return

        metadata = {
            "title": f"{topic} #shorts",
            "description": f"Interesting facts about {topic}. Generated by AI. #shorts #genai",
            "gmail": channel.get("gmail"),
            "password": channel.get("password"),
        }

        await asyncio.to_thread(
            upload_video_via_browser,
            video_path=os.path.abspath(video_path),
            metadata=metadata,
            proxy=proxy,
            cookies_path=cookies,
            headless=True,
        )

        mark_item_processed(history, channel_name, item_id)
        save_history(history)
        logger.info(f"GenAI video for '{topic}' uploaded successfully.")

    except Exception as e:
        logger.error(f"GenAI process failed: {e}")


async def main():
    logger.info("Initializing Unified Automation Engine with Scheduling...")
    downloader = TikTokDownloader()

    while True:
        try:
            channels = load_config()
            history = load_history()

            for channel in channels:
                mode = channel.get("mode", "tiktok").lower()
                if mode == "tiktok":
                    await process_tiktok_channel(channel, downloader, history)
                elif mode == "genai":
                    await process_genai_channel(channel, history)

            logger.info("Cycle complete. Sleeping for 10 minutes...")
            await asyncio.sleep(600)

        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Automation stopped by user.")
