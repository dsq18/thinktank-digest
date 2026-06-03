from datetime import datetime, timezone
from pathlib import Path

from thinktank_digest import db
from thinktank_digest.models import Analysis, RawArticle


def test_sqlite_prevents_duplicate_urls(tmp_path: Path) -> None:
    db_path = tmp_path / "digest.sqlite"
    db.init_db(db_path)
    article = RawArticle(
        title="China strategy report",
        url="https://example.org/report",
        publish_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        source="Example",
        source_priority=5,
        text="A long enough text about China strategy.",
    )

    assert db.insert_discovered(db_path, article) is True
    assert db.insert_discovered(db_path, article) is False
    assert len(db.pending_articles(db_path)) == 1


def test_save_analysis_removes_article_from_pending(tmp_path: Path) -> None:
    db_path = tmp_path / "digest.sqlite"
    db.init_db(db_path)
    article = RawArticle(
        title="Taiwan security report",
        url="https://example.org/taiwan",
        publish_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        source="Example",
        source_priority=5,
        text="Taiwan security analysis.",
    )
    db.insert_discovered(db_path, article)
    db.save_analysis(
        db_path,
        article.url,
        Analysis(
            relevant=True,
            conclusion="台海安全风险上升。",
            key_points=["威慑议题突出。"],
            china_impact="影响中国周边安全判断。",
            indo_pacific_impact="强化印太安全议程。",
            international_security_impact="提高危机管理重要性。",
            global_economy_impact="供应链风险可能上升。",
            importance=5,
            topic_tags=["Taiwan", "Defense"],
        ),
    )

    assert db.pending_articles(db_path) == []
    analyzed = db.analyzed_since(db_path, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert len(analyzed) == 1
    assert analyzed[0].analysis.conclusion == "台海安全风险上升。"
