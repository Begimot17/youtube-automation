import logging
import os

from dotenv import load_dotenv

# Load .env file at the very beginning
load_dotenv()

logger = logging.getLogger("config")


class Config:
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
    TIKTOK_DOWNLOAD_COUNT = os.environ.get("TIKTOK_DOWNLOAD_COUNT", 2)
    # Default for local dev if not in docker
    DEFAULT_DB = "mysql+mysqlconnector://user:user_password@localhost:3307/automation"

    if DB_TYPE == "sqlite":
        # Ensure data directory exists for sqlite
        os.makedirs("data", exist_ok=True)
        DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///data/automation.db"
    else:
        DATABASE_URL = os.environ.get("DATABASE_URL") or DEFAULT_DB

    # Server
    PORT = int(os.environ.get("PORT", 5000))

    # Debug mode
    DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

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
