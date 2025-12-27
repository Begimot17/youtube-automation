import asyncio
import json
import os

from src.sources.tiktok_downloader import TikTokDownloader
from src.upload_engine.playwright_uploader import upload_video_via_browser

CONFIG_PATH = "config/channels.json"
HISTORY_PATH = "config/upload_history.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history():
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)


def is_video_processed(history, channel_name, video_id):
    return video_id in history.get(channel_name, [])


def mark_video_processed(history, channel_name, video_id):
    if channel_name not in history:
        history[channel_name] = []
    if video_id not in history[channel_name]:
        history[channel_name].append(video_id)


async def process_channel(channel, downloader, history):
    channel_name = channel.get("channel_name")
    tiktok_sources = channel.get("tiktok_sources", [])
    watch_folder = channel.get("watch_folder", "input_videos")
    cookies = channel.get("cookies_path")
    proxy = channel.get("proxy")

    if not tiktok_sources:
        print(f"ℹ️ No TikTok sources for {channel_name}")
        return

    print(f"\n🚀 Processing channel: {channel_name}")

    for tt_user in tiktok_sources:
        print(f"--- Checking TikTok: @{tt_user} ---")
        videos = await downloader.get_user_videos(tt_user, count=3)

        if not videos:
            print(f"⚠️ No videos found for @{tt_user}")
            continue

        for video in videos:
            video_id = video.get("id")
            if not video_id:
                continue

            if is_video_processed(history, channel_name, video_id):
                # print(f"⏩ Video {video_id} already processed, skipping.")
                continue

            print(f"🌟 New video found: {video_id}")

            # 1. Download
            output_path = os.path.join(watch_folder, f"{tt_user}_{video_id}.mp4")
            success = await downloader.download_video(video, output_path)

            if not success:
                print(f"❌ Failed to download {video_id}")
                continue

            # 2. Upload to YouTube
            # Use TikTok caption as title, add common hashtags
            tt_title = video.get("title", f"TikTok by @{tt_user}")
            # Limit title to 100 chars
            yt_title = (
                (tt_title[:90] + " #shorts #tiktok")
                if len(tt_title) < 90
                else (tt_title[:70] + "... #shorts")
            )

            metadata = {
                "title": yt_title,
                "description": f"Original video by @{tt_user} on TikTok. #shorts #tiktok #trending",
            }

            print(f"📤 Uploading to YouTube: {yt_title}")
            try:
                # Playwright sync API cannot be called directly inside an asyncio loop.
                # We wrap it in to_thread to run it in a separate thread.
                await asyncio.to_thread(
                    upload_video_via_browser,
                    video_path=os.path.abspath(output_path),
                    metadata=metadata,
                    proxy=proxy,
                    cookies_path=cookies,
                    headless=False,  # Set to True once verified
                )

                # 3. Mark as processed
                mark_video_processed(history, channel_name, video_id)
                save_history(history)
                print(f"✅ Successfully processed {video_id}")

            except Exception as e:
                print(f"❌ Error uploading {video_id}: {e}")


async def main():
    print("🤖 Starting TikTok to YouTube Sync Automation (Verification Run)")
    downloader = TikTokDownloader()

    # while True:
    try:
        channels = load_config()
        history = load_history()

        for channel in channels:
            await process_channel(channel, downloader, history)

        print("\n✅ Verification cycle complete.")
        # await asyncio.sleep(3600)  # Check every hour

    except Exception as e:
        print(f"❌ Global error in main loop: {e}")
        # await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
