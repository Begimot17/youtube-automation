"""Pure decision helpers for the automation loop."""

import random

from src.upload_engine.helpers import clamp_title


def topic_item_id(prefix, topic, lang):
    """History id for a topic. Format is persisted in upload_history: do not change."""
    return f"{prefix}_{str(topic).replace(' ', '_').lower()}_{lang}"


def tiktok_title(raw_title, suffix=" #shorts #tiktok", limit=70):
    """TikTok caption (may be None/empty) -> YouTube title with hashtags."""
    base = " ".join((raw_title or "").split())[:limit].strip()
    return clamp_title((base + suffix) if base else suffix.strip())


def upload_allowed(recent_count, freq, last_upload_ts, now_ts, min_delay):
    """
    Returns (allowed, reason). `freq`/`min_delay` fall back to 1/3600 when falsy,
    `last_upload_ts` of 0/None means "never uploaded".
    """
    freq = freq or 1
    min_delay = min_delay or 3600
    if recent_count >= freq:
        return False, f"Daily limit reached ({recent_count}/{freq})"
    if last_upload_ts:
        elapsed = now_ts - last_upload_ts
        if elapsed < min_delay:
            return False, f"Minimum delay active. Wait {int(min_delay - elapsed)}s"
    return True, ""


def pick_topic(topics, is_processed, prefix, lang, rng=random):
    """Random unprocessed topic -> (topic, item_id) or (None, None)."""
    shuffled = list(topics)
    rng.shuffle(shuffled)
    for t in shuffled:
        item_id = topic_item_id(prefix, t, lang)
        if not is_processed(item_id):
            return t, item_id
    return None, None
