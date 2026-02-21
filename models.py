import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class LineMessage(Base):
    __tablename__ = "line_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String(255), index=True)
    user_id = Column(String(255))
    display_name = Column(String(255))
    message_type = Column(String(50))
    content = Column(Text)
    line_timestamp = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SentimentReport(Base):
    __tablename__ = "sentiment_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(Date, index=True)
    group_id = Column(String(255), index=True)
    message_count = Column(Integer)
    overall_sentiment = Column(String(50))
    sentiment_scores = Column(JSON)
    summary = Column(Text)
    raw_response = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def create_tables():
    Base.metadata.create_all(engine)
    print("Tables created successfully.")


if __name__ == "__main__":
    create_tables()
