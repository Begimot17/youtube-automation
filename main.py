import asyncio
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone

from src.config import Config
from src.factory import create_content
from src.sources.tiktok_downloader import TikTokDownloader
from src.upload_engine.playwright_uploader import (
    upload_video_via_browser,
    verify_login_status,
)
from src.utils import schedule as schedule_utils
from src.utils.db import Channel, SessionLocal, UploadHistory
from src.utils.logging_config import setup_logging
from src.utils.notifications import send_telegram_message, send_upload_report

# Configure logging
setup_logging()
logger = logging.getLogger("main")
TIKTOK_DOWNLOAD_COUNT = Config.TIKTOK_DOWNLOAD_COUNT


def get_channel_uploads_last_24h(db, channel_id):
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    return (
        db.query(UploadHistory)
        .filter(
            UploadHistory.channel_id == channel_id, UploadHistory.timestamp > day_ago
        )
        .all()
    )


def get_last_upload_time(db, channel_id):
    last_upload = (
        db.query(UploadHistory)
        .filter(UploadHistory.channel_id == channel_id)
        .order_by(UploadHistory.timestamp.desc())
        .first()
    )

    if not last_upload:
        return 0
    # This is the key fix: treat the naive datetime from DB as UTC
    return last_upload.timestamp.replace(tzinfo=timezone.utc).timestamp()


def is_item_processed(db, channel_id, item_id):
    return (
        db.query(UploadHistory)
        .filter(
            UploadHistory.channel_id == channel_id, UploadHistory.item_id == item_id
        )
        .first()
        is not None
    )


def mark_item_processed(db, channel_id, item_id):
    upload = UploadHistory(
        channel_id=channel_id, item_id=item_id, timestamp=datetime.now(timezone.utc)
    )
    db.add(upload)
    db.commit()


def is_within_schedule(channel):
    """Checks if the current time is within the channel's upload schedule."""
    return schedule_utils.is_within_schedule(channel.schedule)


def can_upload(channel, db):
    if not is_within_schedule(channel):
        logger.info(
            f"Skipping {channel.account_name}/{channel.channel_name}: Outside of scheduled upload time."
        )
        return False

    freq = channel.upload_frequency_per_day or 1
    min_delay = channel.min_delay_seconds or 3600

    recent_uploads = get_channel_uploads_last_24h(db, channel.id)
    if len(recent_uploads) >= freq:
        logger.info(
            f"Skipping {channel.account_name}/{channel.channel_name}: Daily limit reached ({len(recent_uploads)}/{freq})"
        )
        return False

    last_time = get_last_upload_time(db, channel.id)
    now = time.time()
    if now - last_time < min_delay:
        remaining = int(min_delay - (now - last_time))
        logger.info(
            f"Skipping {channel.account_name}/{channel.channel_name}: Minimum delay active. Wait {remaining}s"
        )
        return False

    return True


async def process_tiktok_channel(channel, downloader, db):
    if not can_upload(channel, db):
        return

    tiktok_sources = channel.tiktok_sources or []
    watch_folder = channel.watch_folder or "data/tiktok_downloads"
    proxy = channel.proxy
    account_name = channel.account_name or channel.channel_name

    logger.info(
        f"--- Processing TikTok Channel: {account_name}/{channel.channel_name} ---"
    )

    for tt_user in tiktok_sources:
        videos = await downloader.get_user_videos(tt_user, count=TIKTOK_DOWNLOAD_COUNT)
        if not videos:
            continue

        for video in videos:
            video_id = video.get("id")
            if not video_id or is_item_processed(db, channel.id, video_id):
                continue

            logger.info(f"Downloading new TikTok video: {video_id}")
            output_path = os.path.join(watch_folder, f"{tt_user}_{video_id}.mp4")
            os.makedirs(watch_folder, exist_ok=True)

            if await downloader.download_video(video, output_path):
                title = video.get("title", "")[:70] + " #shorts #tiktok"
                password = channel.password or os.environ.get(
                    f"YT_PASSWORD_{account_name.upper()}", ""
                )
                metadata = {
                    "title": title,
                    "description": channel.description or "#shorts #tiktok",
                    "gmail": channel.gmail,
                    "password": password,
                    "channel_name": channel.channel_name,
                }
                try:
                    is_logged_in = await asyncio.to_thread(
                        verify_login_status,
                        gmail=channel.gmail,
                        password=password,
                        headless=False,
                        account_name=account_name,
                    )
                    if not is_logged_in:
                        msg = f"⚠️ <b>[LOGIN FAILED]</b> Account: <code>{account_name}</code>\nCould not verify login status."
                        send_telegram_message(msg)
                        logger.error(
                            f"Login failed for {account_name}/{channel.channel_name}. Skipping."
                        )
                        return
                    video_url = await asyncio.to_thread(
                        upload_video_via_browser,
                        video_path=os.path.abspath(output_path),
                        metadata=metadata,
                        proxy=proxy,
                        headless=False,
                        account_name=account_name,
                    )
                    mark_item_processed(db, channel.id, video_id)

                    send_upload_report(
                        account_name, channel.channel_name, title,
                        status="Success", video_url=video_url,
                    )
                    return  # Respect delay
                except Exception as e:
                    send_upload_report(
                        account_name,
                        channel.channel_name,
                        title,
                        status="Failed",
                        error_msg=str(e),
                    )
                    logger.error(
                        f"TikTok upload failed for {account_name}/{channel.channel_name}: {e}"
                    )


def _pick_unprocessed_topic(channel, db, topics, prefix="genai"):
    """Returns (topic, item_id) for the first unprocessed topic, or (None, None)."""
    lang = channel.lang or "ru"
    shuffled = list(topics)
    random.shuffle(shuffled)
    for t in shuffled:
        item_id = f"{prefix}_{t.replace(' ', '_').lower()}_{lang}"
        if not is_item_processed(db, channel.id, item_id):
            return t, item_id
    return None, None


async def process_genai_channel(channel, db):
    if not can_upload(channel, db):
        return

    account_name = channel.account_name or channel.channel_name
    password = channel.password or os.environ.get(f"YT_PASSWORD_{account_name.upper()}", "")

    is_logged_in = await asyncio.to_thread(
        verify_login_status,
        gmail=channel.gmail,
        password=password,
        headless=False,
        account_name=account_name,
    )
    if not is_logged_in:
        send_telegram_message(
            f"⚠️ <b>[LOGIN FAILED]</b> Account: <code>{account_name}</code>\nCould not verify login status."
        )
        logger.error(f"Login failed for {account_name}/{channel.channel_name}. Skipping.")
        return

    topics = channel.genai_topics or []
    lang = channel.lang or "ru"
    quality = channel.quality or "easy"
    voice = channel.voice
    proxy = channel.proxy

    logger.info(f"--- Processing GenAI Channel: {account_name}/{channel.channel_name} ---")
    if not topics:
        return

    topic, item_id = _pick_unprocessed_topic(channel, db, topics, prefix="genai")
    if not topic:
        logger.info(
            f"All GenAI topics for {account_name}/{channel.channel_name} have been processed."
        )
        return

    try:
        video_path = await asyncio.to_thread(
            create_content,
            topic=topic,
            channel_name=channel.channel_name,
            language=lang,
            quality=quality,
            voice=voice,
        )
        if video_path and os.path.exists(video_path):
            title = f"{topic} #shorts"
            metadata = {
                "title": title,
                "description": channel.description or "#shorts",
                "gmail": channel.gmail,
                "password": password,
                "channel_name": channel.channel_name,
            }
            try:
                video_url = await asyncio.to_thread(
                    upload_video_via_browser,
                    video_path=os.path.abspath(video_path),
                    metadata=metadata,
                    proxy=proxy,
                    headless=False,
                    account_name=account_name,
                )
                mark_item_processed(db, channel.id, item_id)
                send_upload_report(
                    account_name, channel.channel_name, title,
                    status="Success", video_url=video_url,
                )
            except Exception as e:
                send_upload_report(
                    account_name, channel.channel_name, title,
                    status="Failed", error_msg=str(e),
                )
                logger.error(f"Upload failed for {account_name}/{channel.channel_name}: {e}")
    except Exception as e:
        logger.error(f"GenAI failed for {account_name}/{channel.channel_name}: {e}")


async def process_gen_v2_channel(channel, db):
    if not can_upload(channel, db):
        return

    account_name = channel.account_name or channel.channel_name
    password = channel.password or os.environ.get(f"YT_PASSWORD_{account_name.upper()}", "")

    is_logged_in = await asyncio.to_thread(
        verify_login_status,
        gmail=channel.gmail,
        password=password,
        headless=False,
        account_name=account_name,
    )
    if not is_logged_in:
        send_telegram_message(
            f"⚠️ <b>[LOGIN FAILED]</b> Account: <code>{account_name}</code>\nCould not verify login status."
        )
        logger.error(f"Login failed for {account_name}/{channel.channel_name}. Skipping.")
        return

    topics = channel.genai_topics or []
    proxy = channel.proxy

    logger.info(f"--- Processing gen_v2 Channel: {account_name}/{channel.channel_name} ---")
    if not topics:
        return

    topic, item_id = _pick_unprocessed_topic(channel, db, topics, prefix="gen_v2")
    if not topic:
        logger.info(
            f"All gen_v2 topics for {account_name}/{channel.channel_name} have been processed."
        )
        return

    from src.gen_v2.renderer import generate_video_v2

    output_dir = f"data/output/{channel.channel_name}/{int(time.time())}"
    try:
        video_path = await asyncio.to_thread(
            generate_video_v2,
            action_prompt=topic,
            output_dir=output_dir,
        )
        if video_path and os.path.exists(video_path):
            title = f"{topic[:70]} #shorts"
            metadata = {
                "title": title,
                "description": channel.description or "#shorts",
                "gmail": channel.gmail,
                "password": password,
                "channel_name": channel.channel_name,
            }
            try:
                video_url = await asyncio.to_thread(
                    upload_video_via_browser,
                    video_path=os.path.abspath(video_path),
                    metadata=metadata,
                    proxy=proxy,
                    headless=False,
                    account_name=account_name,
                )
                mark_item_processed(db, channel.id, item_id)
                send_upload_report(
                    account_name, channel.channel_name, title,
                    status="Success", video_url=video_url,
                )
            except Exception as e:
                send_upload_report(
                    account_name, channel.channel_name, title,
                    status="Failed", error_msg=str(e),
                )
                logger.error(f"gen_v2 upload failed for {account_name}/{channel.channel_name}: {e}")
    except Exception as e:
        logger.error(f"gen_v2 generation failed for {account_name}/{channel.channel_name}: {e}")


async def run_full_cycle():
    """Runs a single pass through all channels."""
    logger.info("Starting a single automation cycle...")
    db = SessionLocal()
    downloader = TikTokDownloader()

    try:
        channels = db.query(Channel).all()
        for channel in channels:
            mode = (channel.mode or "tiktok").lower()
            if mode == "tiktok":
                await process_tiktok_channel(channel, downloader, db)
            elif mode == "genai":
                await process_genai_channel(channel, db)
            elif mode == "gen_v2":
                await process_gen_v2_channel(channel, db)
    finally:
        db.close()
    logger.info("Cycle finished.")


async def run_for_channel(account_name, channel_name):
    """Runs automation for a specific channel name."""
    logger.info(f"Triggering manual run for channel: {account_name}/{channel_name}")
    db = SessionLocal()
    downloader = TikTokDownloader()

    try:
        target = (
            db.query(Channel)
            .filter(
                Channel.account_name == account_name,
                Channel.channel_name == channel_name,
            )
            .first()
        )
        if not target:
            logger.error(f"Channel {account_name}/{channel_name} not found in DB.")
            return False

        mode = (target.mode or "tiktok").lower()
        if mode == "tiktok":
            await process_tiktok_channel(target, downloader, db)
        elif mode == "genai":
            await process_genai_channel(target, db)
        elif mode == "gen_v2":
            await process_gen_v2_channel(target, db)
        return True
    finally:
        db.close()


async def main_loop():
    logger.info("Starting Automation Engine (Loop mode)...")
    while True:
        try:
            await run_full_cycle()
            logger.info("Cycle complete. Sleeping 10m...")
            await asyncio.sleep(600)
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Stopped.")
