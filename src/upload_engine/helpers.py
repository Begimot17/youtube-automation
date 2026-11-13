"""Pure helpers for the Playwright uploader (no playwright import)."""

import functools
import logging
import re
import time
import traceback
from urllib.parse import unquote, urlsplit

logger = logging.getLogger(__name__)

YOUTUBE_TITLE_LIMIT = 100


def retry_step(max_attempts=3, base_delay=2.0, step_name="step"):
    """Retries the wrapped function with exponential backoff (base_delay ** attempt)."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    wait = base_delay**attempt
                    logger.warning(
                        f"[RETRY] '{step_name}' attempt {attempt}/{max_attempts}: {e}. Wait {wait:.1f}s"
                    )
                    if attempt == max_attempts:
                        logger.error(
                            f"[FAILED] '{step_name}' exhausted all {max_attempts} attempts.\n"
                            f"{traceback.format_exc()}"
                        )
                        raise
                    time.sleep(wait)

        return wrapper

    return decorator


def cookies_path_for(account_name, base_dir="auth"):
    """
    Cookie file for an account. The name is sanitised so it cannot escape
    `base_dir` (path separators, "..") and None/"" gets a stable name.
    """
    safe = re.sub(r"[^\w.@-]+", "_", str(account_name or "").strip()).strip(".")
    return f"{base_dir}/{safe or 'default'}.json"


def parse_proxy(proxy):
    """
    Converts "http://user:pass@host:port" (or "host:port") into Playwright's
    proxy dict. Returns None for an empty value.
    """
    if not proxy or not str(proxy).strip():
        return None
    proxy = str(proxy).strip()
    if "://" not in proxy:
        proxy = "http://" + proxy
    parts = urlsplit(proxy)
    if not parts.hostname:
        return None
    server = f"{parts.scheme}://{parts.hostname}"
    if parts.port:
        server += f":{parts.port}"
    result = {"server": server}
    if parts.username:
        result["username"] = unquote(parts.username)
    if parts.password:
        result["password"] = unquote(parts.password)
    return result


def css_quote(value):
    """Escapes a value for use inside a single-quoted CSS/XPath string literal."""
    return str(value).replace("\\", "\\\\").replace("'", "\'")


def xpath_literal(value):
    """Safe XPath string literal even when the value contains quotes."""
    value = str(value)
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    pieces = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in pieces) + ")"


def clamp_title(title, limit=YOUTUBE_TITLE_LIMIT):
    """Truncates to YouTube's title limit on a word boundary, keeping a trailing hashtag block."""
    title = " ".join(str(title or "").split()) or "New Video"
    if len(title) <= limit:
        return title
    cut = title[:limit].rstrip()
    if " " in cut and title[limit] != " ":
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip()
