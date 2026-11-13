"""Scene/visual selection logic for the content pipeline (no heavy imports)."""

import logging
import os

logger = logging.getLogger(__name__)


def collect_visuals(scenes, topic, base_dir, fetch, per_scene=1, max_keywords=2):
    """
    Downloads up to `per_scene` unique clips per scene.

    `fetch(query, out_path, used_urls)` returns (path_or_None, source_url).
    Keywords are tried in order (at most `max_keywords`); a scene without
    keywords falls back to the topic. Returns the list of downloaded paths.
    """
    paths = []
    used_urls = set()
    for i, scene in enumerate(scenes or []):
        keywords = [k for k in (scene.get("keywords") or []) if k] or [topic]
        got = 0
        for k, query in enumerate(keywords[:max_keywords]):
            if got >= per_scene:
                break
            out_path = os.path.join(base_dir, f"scene_{i}_v{k}.mp4")
            downloaded, url = fetch(query, out_path, used_urls)
            if downloaded:
                paths.append(downloaded)
                if url:
                    used_urls.add(url)
                got += 1
                logger.info(f"Downloaded unique visual for: {query}")
            else:
                logger.warning(f"Could not download visual for {query}")
    return paths
