import asyncio
import logging
import os

import yt_dlp

logger = logging.getLogger(__name__)


def clean_username(username):
    """Accepts "@name", "name" or a profile URL and returns the bare handle."""
    name = str(username or "").strip()
    if "tiktok.com/" in name:
        name = name.split("tiktok.com/", 1)[1].split("?", 1)[0].strip("/")
    return name.lstrip("@").split("/")[0]


class TikTokDownloader:
    """
    A class to download videos from TikTok channels using yt-dlp.
    This replaces the flaky davidteather/TikTok-Api implementation.
    """

    def __init__(self):
        # We don't need persistent sessions like in TikTokApi
        pass

    def get_user_videos_sync(self, username: str, count: int = 5):
        """
        Fetches metadata for the specified number of videos from a user's profile using yt-dlp.
        """
        username = clean_username(username)
        if not username:
            logger.error("Empty TikTok username.")
            return []
        count = max(1, int(count))
        url = f"https://www.tiktok.com/@{username}"

        # yt-dlp options for metadata extraction
        ydl_opts = {
            "extract_flat": True,  # Just get the list of videos, don't download yet
            "playlist_items": f"1-{count}",  # Limit to first 'count' items
            "quiet": True,
            "no_warnings": True,
        }

        logger.info(f"Fetching latest {count} videos for @{username}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                entries = (info or {}).get("entries") or []
                return [e for e in entries if e]
            except Exception as e:
                logger.error(f"Failed to fetch video list: {e}")
                return []

    async def get_user_videos(
        self, username: str, count: int = 5, headless: bool = False
    ):
        """
        Async wrapper for get_user_videos_sync.
        """
        return await asyncio.to_thread(self.get_user_videos_sync, username, count)

    def download_video_sync(self, video_url: str, output_path: str):
        """
        Downloads a single video using yt-dlp.
        """
        ydl_opts = {
            "format": "best",
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

    async def download_video(self, video_data, output_path: str):
        """
        Async wrapper for download_video_sync.
        Note: video_data is expected to be an entry from get_user_videos.
        """
        # In yt-dlp flat extract, entries have 'url'
        video_url = video_data.get("url")
        if not video_url:
            # Fallback for different entry formats
            video_id = video_data.get("id")
            if video_id:
                video_url = f"https://www.tiktok.com/video/{video_id}"
            else:
                logger.error("No URL found in video data.")
                return False

        logger.info(f"Downloading {video_url}...")
        try:
            await asyncio.to_thread(self.download_video_sync, video_url, output_path)
        except Exception as e:
            logger.error(f"yt-dlp failed for {video_url}: {e}")
            return False
        if os.path.exists(output_path):
            logger.info(f"✅ Video saved to: {output_path}")
            return True
        return False

    async def sync_channel(
        self, username: str, output_folder: str, count: int = 5, headless: bool = False
    ):
        """
        Downloads the latest 'count' videos from a channel.
        """
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        logger.info(f"Syncing channel: @{username}...")
        videos = await self.get_user_videos(username, count)

        if not videos:
            logger.warning(
                f"No videos found for @{username}. Check if account exists or is public."
            )
            return

        for i, video in enumerate(videos):
            video_id = video.get("id")
            if not video_id:
                continue

            output_path = os.path.join(
                output_folder, f"{clean_username(username)}_{video_id}.mp4"
            )

            if os.path.exists(output_path):
                logger.info(f"Video {video_id} already exists, skipping.")
                continue

            logger.info(f"Downloading video {i + 1}/{len(videos)}: {video_id}...")
            try:
                success = await self.download_video(video, output_path)
                if not success:
                    logger.error(f"Failed to download {video_id}")
            except Exception as e:
                logger.error(f"Error downloading {video_id}: {e}")


if __name__ == "__main__":
    # Quick test
    async def test():
        downloader = TikTokDownloader()
        # Using a public profile for testing
        await downloader.sync_channel("khaby.lame", "input_videos", count=1)

    asyncio.run(test())
