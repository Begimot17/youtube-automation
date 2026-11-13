"""Channel <-> JSON helpers shared by the API endpoints (no web/DB imports)."""

from src.utils.schedule import normalize_schedule

PUBLIC_FIELDS = (
    "channel_name",
    "account_name",
    "mode",
    "gmail",
    "watch_folder",
    "proxy",
    "upload_frequency_per_day",
    "min_delay_seconds",
    "quality",
    "lang",
    "voice",
    "tiktok_sources",
    "genai_topics",
)

# Fields a client may set on an existing channel through POST /config.
UPDATABLE_FIELDS = (
    "mode",
    "watch_folder",
    "proxy",
    "upload_frequency_per_day",
    "min_delay_seconds",
    "quality",
    "lang",
    "voice",
    "tiktok_sources",
    "genai_topics",
)


def serialize_channel(channel):
    """Public view of a channel; the password is never returned."""
    data = {name: getattr(channel, name) for name in PUBLIC_FIELDS}
    data["password"] = "******"
    data["schedule"] = normalize_schedule_safe(channel.schedule)
    return data


def normalize_schedule_safe(value):
    try:
        return normalize_schedule(value)
    except ValueError:
        return value


def apply_channel_update(channel, data):
    """
    Applies recognised keys from `data` onto `channel`, leaving absent keys
    untouched. Raises ValueError for an invalid schedule (before any change).
    """
    schedule = normalize_schedule(data["schedule"]) if "schedule" in data else None
    for name in UPDATABLE_FIELDS:
        if name in data:
            setattr(channel, name, data[name])
    for name in ("gmail", "password"):
        if name in data:
            setattr(channel, name, data[name])
    if schedule is not None:
        channel.schedule = schedule
