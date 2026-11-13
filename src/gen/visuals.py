import logging
import random
from pathlib import Path

import requests

from src.config import Config

logger = logging.getLogger(__name__)

# Headers for Pexels API
PEXELS_API_KEY = Config.PEXELS_API_KEY


REQUEST_TIMEOUT = 30


def pick_video_link(files):
    """
    Chooses a download link from Pexels `video_files`. Prefers a 1080-wide /
    1920-tall rendition, otherwise the first file that has a link. None if empty.
    """
    links = [f for f in (files or []) if isinstance(f, dict) and f.get("link")]
    if not links:
        return None
    for f in links:
        if f.get("width") == 1080 or f.get("height") == 1920:
            return f["link"]
    return links[0]["link"]


def filter_videos(videos, duration_min=3, duration_max=None):
    """Keeps videos whose duration is within [duration_min, duration_max]."""
    out = []
    for v in videos or []:
        dur = v.get("duration")
        if not isinstance(dur, (int, float)) or dur < duration_min:
            continue
        if duration_max is not None and dur > duration_max:
            continue
        out.append(v)
    return out


def search_pexels_videos(
    query, orientation="portrait", size="medium", duration_min=3, duration_max=15
):
    """
    Searches Pexels for videos.
    Returns a list of video objects (dict).
    """
    if not PEXELS_API_KEY:
        logger.error("PEXELS_API_KEY not found.")
        return []

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": orientation,
        "size": size,
        "per_page": 15,  # Increased for more variety
    }

    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        videos = data.get("videos", [])
        # duration_max is accepted for API compatibility but not enforced (clips are cropped later)
        return filter_videos(videos, duration_min)

    except Exception as e:
        logger.error(f"Error searching Pexels: {e}")
        return []


def download_video(video_url, output_path):
    """
    Downloads video from URL to output_path.
    """
    try:
        logger.info(f"Downloading visual: {output_path}...")
        response = requests.get(video_url, stream=True, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return str(output_path)

    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return None


def get_stock_footage(keyword, output_filename, used_urls=None):
    """
    High-level function to find and download a stock video for a keyword.
    Prevents using duplicate videos via used_urls set.
    """
    used_urls = used_urls or set()
    logger.info(f"Finding footage for: {keyword}")
    videos = search_pexels_videos(keyword)

    # Fallback 1: Try a simpler version of the keyword if it's multiple words
    if not videos and " " in keyword:
        simple_query = keyword.split()[-1]
        logger.info(f"No results for '{keyword}', trying fallback: {simple_query}")
        videos = search_pexels_videos(simple_query)

    # Fallback 2: General abstract background
    if not videos:
        logger.info(f"No videos found for {keyword}, trying abstract fallback...")
        videos = search_pexels_videos("abstract background")

    if videos:
        # Filter out already used videos
        available_videos = [v for v in videos if v.get("url") not in used_urls]

        if not available_videos:
            logger.warning("All fetched videos were already used. Re-using one.")
            available_videos = videos

        # Pick a random one from available results
        video = random.choice(available_videos)

        # Get the best quality link
        video_url = pick_video_link(video.get("video_files"))
        if not video_url:
            return None, None

        path = download_video(video_url, output_filename)
        return path, video.get("url")

    return None, None


if __name__ == "__main__":
    # Test
    get_stock_footage("space galaxy", "assets/space_test.mp4")
