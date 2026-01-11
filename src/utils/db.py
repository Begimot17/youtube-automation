import logging
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from alembic import command
from alembic.config import Config as AlembicConfig
from src.config import Config

logger = logging.getLogger("db")

DATABASE_URL = Config.DATABASE_URL

Base = declarative_base()
engine_args = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_migrations():
    """Applies any pending Alembic migrations."""
    logger.info("Checking for and applying database migrations...")
    alembic_cfg = AlembicConfig("alembic.ini")
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully.")
    except Exception as e:
        logger.error(f"Error applying database migrations: {e}")
        raise


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_name = Column(String(100), index=True)
    account_name = Column(String(100), index=True)
    mode = Column(String(20), default="tiktok")  # 'tiktok' or 'genai'
    gmail = Column(String(100))
    password = Column(String(100))
    watch_folder = Column(String(255))
    proxy = Column(String(255))
    upload_frequency_per_day = Column(Integer, default=1)
    min_delay_seconds = Column(Integer, default=3600)
    quality = Column(String(20), default="easy")
    lang = Column(String(10), default="ru")
    voice = Column(String(100))
    description = Column(String(1000), default="#shorts")
    schedule = Column(JSON, default='["08:00-20:00"]')

    # Mode-specific data
    tiktok_sources = Column(JSON)  # List of strings
    genai_topics = Column(JSON)  # List of strings

    uploads = relationship(
        "UploadHistory", back_populates="channel", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("account_name", "channel_name", name="_account_channel_uc"),
    )


class UploadHistory(Base):
    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"))
    item_id = Column(String(255), index=True)  # TikTok ID or GenAI topic hash
    timestamp = Column(DateTime, default=datetime.utcnow)

    channel = relationship("Channel", back_populates="uploads")


def init_db():
    try:
        # We now use Alembic to manage the schema, so create_all is less critical
        # but can be kept for initial setup in environments without Alembic.
        # For a pure Alembic approach, this could be removed.
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created.")
    except Exception as e:
        logger.error(f"Error during table check/creation: {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
