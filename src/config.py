import logging
import os

from dotenv import load_dotenv

# Load .env file at the very beginning
load_dotenv()

logger = logging.getLogger("config")


def env_int(name, default, minimum=None):
    """Reads an int env var; falls back to `default` on missing/invalid/too-small values."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        logger.warning(f"Invalid integer for {name}={raw!r}, using {default}")
        return default
    if minimum is not None and value < minimum:
        logger.warning(f"{name}={value} is below {minimum}, using {default}")
        return default
    return value


def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "t", "yes", "y", "on")


class Config:
    CHANNELS_CONFIG_PATH = os.environ.get(
        "CHANNELS_CONFIG_PATH", "config/channels.json"
    )
    UPLOAD_HISTORY_PATH = os.environ.get(
        "UPLOAD_HISTORY_PATH", "config/upload_history.json"
    )

    # Google Gemini
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get(
        "GEMINI_API_KEY"
    )
    GEMINI_MODEL_ID = os.environ.get("GEMINI_MODEL_ID") or "gemini-2.5-flash-lite"

    # Pexels
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
    API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

    # Database
    DB_TYPE = os.environ.get("DB_TYPE", "mysql").lower()
    TIKTOK_DOWNLOAD_COUNT = env_int("TIKTOK_DOWNLOAD_COUNT", 2, minimum=1)
    # Default for local dev if not in docker
    DEFAULT_DB = "mysql+mysqlconnector://user:user_password@localhost:3307/automation"

    if DB_TYPE == "sqlite":
        # Ensure data directory exists for sqlite
        os.makedirs("data", exist_ok=True)
        DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///data/automation.db"
    else:
        DATABASE_URL = os.environ.get("DATABASE_URL") or DEFAULT_DB

    # Server
    PORT = env_int("PORT", 5000, minimum=1)

    # Debug mode
    DEBUG = env_bool("DEBUG", False)

    @classmethod
    def validate(cls):
        """Simple check to warn about missing critical keys."""
        missing = []
        if not cls.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
        if not cls.PEXELS_API_KEY:
            missing.append("PEXELS_API_KEY")

        if missing:
            logger.warning(f"Missing environment variables: {', '.join(missing)}")
        return len(missing) == 0


# Run validation on import
Config.validate()
