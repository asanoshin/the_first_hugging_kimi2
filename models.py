import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

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


class HandbookParentRecord(Base):
    """家長紀錄事項 - 發展里程碑勾選（粉紅色頁面）"""
    __tablename__ = "handbook_parent_records"
    __table_args__ = (
        UniqueConstraint('mpersonid', 'visit_number', name='uq_parent_record_person_visit'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    mpersonid = Column(String(20), index=True, nullable=False)
    visit_number = Column(Integer, nullable=False)
    age_stage = Column(String(50))
    record_date = Column(Date, nullable=True)
    checklist_items = Column(JSON)
    parent_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class HandbookHealthEducation(Base):
    """衛教指導紀錄（白色頁面）"""
    __tablename__ = "handbook_health_education"
    __table_args__ = (
        UniqueConstraint('mpersonid', 'visit_number', name='uq_health_edu_person_visit'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    mpersonid = Column(String(20), index=True, nullable=False)
    visit_number = Column(Integer, nullable=False)
    age_stage = Column(String(50))
    guidance_date = Column(Date, nullable=True)
    parent_assessment = Column(JSON)
    doctor_guidance = Column(JSON)
    hospital_code = Column(String(100), nullable=True)
    doctor_name = Column(String(50), nullable=True)
    relationship = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class HandbookScanSession(Base):
    """掃描工作階段"""
    __tablename__ = "handbook_scan_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mpersonid = Column(String(20), nullable=True)
    status = Column(String(20), default='in_progress')
    scanned_by = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    pages = relationship("HandbookScannedPage", back_populates="session",
                         order_by="HandbookScannedPage.page_order")


class HandbookScannedPage(Base):
    """掃描頁面紀錄"""
    __tablename__ = "handbook_scanned_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('handbook_scan_sessions.id'), nullable=False)
    page_order = Column(Integer, default=0)
    page_type = Column(String(30))
    image_data = Column(Text, nullable=True)
    ocr_raw_response = Column(Text, nullable=True)
    ocr_extracted_json = Column(JSON, nullable=True)
    status = Column(String(20), default='pending')
    staff_corrections = Column(JSON, nullable=True)
    confirmed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("HandbookScanSession", back_populates="pages")


def create_tables():
    Base.metadata.create_all(engine)
    print("Tables created successfully.")


if __name__ == "__main__":
    create_tables()
