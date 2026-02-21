"""每日情緒分析腳本 - 查詢前一天的 LINE 群組訊息，透過 Gemini 分析情緒，結果存入 DB。"""

import os
import json
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv
import requests

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

from models import LineMessage, SentimentReport

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

SENTIMENT_PROMPT = """你是一位情緒分析專家。請分析以下 LINE 群組的對話內容，產生一份情緒分析報告。

請回傳 JSON 格式，包含以下欄位：
- overall_sentiment: "positive" / "negative" / "neutral" / "mixed"
- sentiment_scores: {"positive": 0-1, "negative": 0-1, "neutral": 0-1}（三者總和為 1）
- summary: 用繁體中文簡要描述今天群組的整體氛圍、主要話題、情緒走向（100-200字）

只回傳 JSON，不要其他文字。

---
以下是今天的對話記錄：

{messages}
"""


def call_gemini(prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }
    resp = requests.post(GEMINI_URL, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def run_analysis(target_date=None):
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    db = SessionLocal()
    try:
        start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)

        messages = (
            db.query(LineMessage)
            .filter(LineMessage.line_timestamp >= start, LineMessage.line_timestamp < end)
            .order_by(LineMessage.line_timestamp)
            .all()
        )

        if not messages:
            print(f"No messages found for {target_date}")
            return

        groups = {}
        for msg in messages:
            gid = msg.group_id or "direct"
            groups.setdefault(gid, []).append(msg)

        for group_id, group_msgs in groups.items():
            formatted = "\n".join(
                f"[{m.line_timestamp.strftime('%H:%M')}] {m.display_name}: {m.content}"
                for m in group_msgs
                if m.content
            )

            if not formatted.strip():
                continue

            prompt = SENTIMENT_PROMPT.format(messages=formatted)
            raw_text = call_gemini(prompt)

            # 移除可能的 markdown code block 包裝
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()

            try:
                result = json.loads(clean)
            except json.JSONDecodeError:
                result = {
                    "overall_sentiment": "unknown",
                    "sentiment_scores": {},
                    "summary": raw_text,
                }

            report = SentimentReport(
                report_date=target_date,
                group_id=group_id,
                message_count=len(group_msgs),
                overall_sentiment=result.get("overall_sentiment", "unknown"),
                sentiment_scores=result.get("sentiment_scores"),
                summary=result.get("summary", ""),
                raw_response=raw_text,
            )
            db.add(report)
            db.commit()
            print(f"Report saved for group {group_id}: {result.get('overall_sentiment')}")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_analysis()
