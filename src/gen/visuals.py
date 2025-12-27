import os
import random
from pathlib import Path

import requests

# Headers for Pexels API
# Get key from: https://www.pexels.com/api/
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")


def search_pexels_videos(
    query, orientation="portrait", size="medium", duration_min=3, duration_max=15
):
    """
    Searches Pexels for videos.
    Returns a list of video objects (dict).
    """
    if not PEXELS_API_KEY:
        print("Error: PEXELS_API_KEY not found.")
        return []

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": orientation,
        "size": size,
        "per_page": 5,  # Fetch top 5
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        videos = data.get("videos", [])
        valid_videos = []

        for v in videos:
            if v["duration"] >= duration_min:
                valid_videos.append(v)

        return valid_videos

    except Exception as e:
        print(f"Error searching Pexels: {e}")
        return []


def download_video(video_url, output_path):
    """
    Downloads video from URL to output_path.
    """
    try:
        print(f"Downloading visual: {output_path}...")
        response = requests.get(video_url, stream=True)
        response.raise_for_status()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return str(output_path)

    except Exception as e:
        print(f"Error downloading video: {e}")
        return None


def get_stock_footage(keyword, output_filename):
    """
    High-level function to find and download a stock video for a keyword.
    """
    print(f"Finding footage for: {keyword}")
    videos = search_pexels_videos(keyword)

    if not videos:
        print(f"No videos found for {keyword}, trying fallback...")
        videos = search_pexels_videos("abstract background")

    if videos:
        # Pick a random one from top 5 to vary content
        video = random.choice(videos)

        # Get the best quality link for download (usually HD)
        files = video["video_files"]
        # valid_files = [f for f in files if f['width'] and f['width'] >= 720]
        # video_url = valid_files[0]['link'] if valid_files else files[0]['link']

        # Fallback simpler selection
        video_url = files[0]["link"]

        return download_video(video_url, output_filename)

    return None


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    # Test
    get_stock_footage("space galaxy", "assets/space_test.mp4")
