import logging
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from src.config import Config

logger = logging.getLogger("db")

DATABASE_URL = Config.DATABASE_URL

Base = declarative_base()
engine_args = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_name = Column(String(100), unique=True, index=True)
    mode = Column(String(20), default="tiktok")  # 'tiktok' or 'genai'
    gmail = Column(String(100))
    password = Column(String(100))
    watch_folder = Column(String(255))
    proxy = Column(String(255))
    cookies_path = Column(String(255))
    upload_frequency_per_day = Column(Integer, default=1)
    min_delay_seconds = Column(Integer, default=3600)
    quality = Column(String(20), default="easy")
    lang = Column(String(10), default="ru")
    voice = Column(String(100))
    description = Column(String(1000), default="#shorts")

    # Mode-specific data
    tiktok_sources = Column(JSON)  # List of strings
    genai_topics = Column(JSON)  # List of strings

    uploads = relationship(
        "UploadHistory", back_populates="channel", cascade="all, delete-orphan"
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
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
