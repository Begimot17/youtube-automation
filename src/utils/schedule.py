"""Pure helpers for upload schedule windows ("HH:MM-HH:MM")."""

import json
import logging
from datetime import datetime, time

logger = logging.getLogger("schedule")


def parse_window(text):
    """Parses "HH:MM-HH:MM" into (start, end) times. Raises ValueError."""
    start_str, end_str = str(text).split("-")
    start = datetime.strptime(start_str.strip(), "%H:%M").time()
    end = datetime.strptime(end_str.strip(), "%H:%M").time()
    return start, end


def in_window(now, start, end):
    """True if `now` is inside [start, end]. Windows with start > end wrap midnight."""
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def is_within_schedule(schedule, now=None):
    """
    schedule: list of "HH:MM-HH:MM" strings (or a JSON string of such a list).
    Empty/None schedule means "any time". Invalid entries are skipped; if every
    entry is invalid the schedule is ignored rather than blocking uploads forever.
    """
    if not schedule:
        return True
    if isinstance(schedule, str):
        try:
            schedule = json.loads(schedule)
        except ValueError:
            pass  # a bare "HH:MM-HH:MM" string is handled below
    if isinstance(schedule, str):
        schedule = [schedule]

    now = now or datetime.now().time()
    if isinstance(now, datetime):
        now = now.time()

    valid = 0
    for entry in schedule:
        try:
            start, end = parse_window(entry)
        except ValueError:
            logger.warning(f"Invalid schedule window: {entry!r}")
            continue
        valid += 1
        if in_window(now, start, end):
            return True
    return valid == 0


DEFAULT_SCHEDULE = ["08:00-20:00"]


def normalize_schedule(value):
    """
    Validates user input for a channel schedule and returns a list of
    "HH:MM-HH:MM" strings. Accepts a list, a JSON string of a list, or one
    window string. Raises ValueError on any malformed window.
    """
    if value is None:
        return list(DEFAULT_SCHEDULE)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = [value]
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("schedule must be a list of 'HH:MM-HH:MM' strings")
    out = []
    for entry in value:
        start, end = parse_window(entry)
        out.append(f"{start:%H:%M}-{end:%H:%M}")
    return out
