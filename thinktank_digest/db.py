from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import Analysis, DigestArticle, RawArticle


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    source_priority INTEGER NOT NULL,
    publish_date TEXT,
    discovered_at TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    analysis_json TEXT,
    importance INTEGER,
    topics_json TEXT,
    summarized_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);

CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    success INTEGER NOT NULL,
    error TEXT
);
"""


def _dt_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _dt_from_str(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def has_url(db_path: Path, url: str) -> bool:
    with connect(db_path) as conn:
        row = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone()
        return row is not None


def insert_discovered(db_path: Path, article: RawArticle) -> bool:
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO articles (
                url, title, source, source_priority, publish_date, discovered_at, text, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.url,
                article.title,
                article.source,
                article.source_priority,
                _dt_to_str(article.publish_date),
                _dt_to_str(datetime.now(timezone.utc)),
                article.text,
                "discovered",
            ),
        )
        return cursor.rowcount > 0


def mark_skipped(db_path: Path, url: str, reason: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE articles SET status = ?, analysis_json = ? WHERE url = ?",
            ("skipped", json.dumps({"reason": reason}, ensure_ascii=False), url),
        )


def save_analysis(db_path: Path, url: str, analysis: Analysis) -> None:
    payload = {
        "relevant": analysis.relevant,
        "一句话结论": analysis.conclusion,
        "核心观点": analysis.key_points,
        "对中国的影响": analysis.china_impact,
        "对印太的影响": analysis.indo_pacific_impact,
        "对国际安全的影响": analysis.international_security_impact,
        "对全球经济的影响": analysis.global_economy_impact,
        "重要性评分": analysis.importance,
        "主题标签": analysis.topic_tags,
    }
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE articles
            SET status = ?, analysis_json = ?, importance = ?, topics_json = ?, summarized_at = ?
            WHERE url = ?
            """,
            (
                "analyzed" if analysis.relevant else "skipped",
                json.dumps(payload, ensure_ascii=False),
                analysis.importance,
                json.dumps(analysis.topic_tags, ensure_ascii=False),
                _dt_to_str(datetime.now(timezone.utc)),
                url,
            ),
        )


def pending_articles(db_path: Path) -> list[RawArticle]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT title, url, publish_date, source, source_priority, text
            FROM articles
            WHERE status = 'discovered'
            ORDER BY publish_date DESC NULLS LAST, discovered_at DESC
            """
        ).fetchall()
    return [
        RawArticle(
            title=row["title"],
            url=row["url"],
            publish_date=_dt_from_str(row["publish_date"]),
            source=row["source"],
            source_priority=int(row["source_priority"]),
            text=row["text"],
        )
        for row in rows
    ]


def analyzed_since(db_path: Path, since: datetime) -> list[DigestArticle]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT title, url, publish_date, source, source_priority, analysis_json, discovered_at
            FROM articles
            WHERE status = 'analyzed' AND summarized_at >= ?
            """,
            (_dt_to_str(since),),
        ).fetchall()
    items: list[DigestArticle] = []
    for row in rows:
        payload = json.loads(row["analysis_json"] or "{}")
        items.append(
            DigestArticle(
                title=row["title"],
                url=row["url"],
                publish_date=_dt_from_str(row["publish_date"]),
                source=row["source"],
                source_priority=int(row["source_priority"]),
                analysis=Analysis(
                    relevant=bool(payload.get("relevant", True)),
                    conclusion=payload.get("一句话结论", ""),
                    key_points=list(payload.get("核心观点") or []),
                    china_impact=payload.get("对中国的影响", ""),
                    indo_pacific_impact=payload.get("对印太的影响", ""),
                    international_security_impact=payload.get("对国际安全的影响", ""),
                    global_economy_impact=payload.get("对全球经济的影响", ""),
                    importance=int(payload.get("重要性评分", 1)),
                    topic_tags=list(payload.get("主题标签") or []),
                ),
                discovered_at=_dt_from_str(row["discovered_at"]) or datetime.now(timezone.utc),
            )
        )
    return items


def analyzed_by_urls(db_path: Path, urls: list[str]) -> list[DigestArticle]:
    if not urls:
        return []
    placeholders = ",".join("?" for _ in urls)
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT title, url, publish_date, source, source_priority, analysis_json, discovered_at
            FROM articles
            WHERE status = 'analyzed' AND url IN ({placeholders})
            """,
            urls,
        ).fetchall()
    items: list[DigestArticle] = []
    for row in rows:
        payload = json.loads(row["analysis_json"] or "{}")
        items.append(
            DigestArticle(
                title=row["title"],
                url=row["url"],
                publish_date=_dt_from_str(row["publish_date"]),
                source=row["source"],
                source_priority=int(row["source_priority"]),
                analysis=Analysis(
                    relevant=bool(payload.get("relevant", True)),
                    conclusion=payload.get("一句话结论", ""),
                    key_points=list(payload.get("核心观点") or []),
                    china_impact=payload.get("对中国的影响", ""),
                    indo_pacific_impact=payload.get("对印太的影响", ""),
                    international_security_impact=payload.get("对国际安全的影响", ""),
                    global_economy_impact=payload.get("对全球经济的影响", ""),
                    importance=int(payload.get("重要性评分", 1)),
                    topic_tags=list(payload.get("主题标签") or []),
                ),
                discovered_at=_dt_from_str(row["discovered_at"]) or datetime.now(timezone.utc),
            )
        )
    return items


def log_email(db_path: Path, recipient: str, subject: str, success: bool, error: str | None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO email_logs (sent_at, recipient, subject, success, error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (_dt_to_str(datetime.now(timezone.utc)), recipient, subject, int(success), error),
        )
