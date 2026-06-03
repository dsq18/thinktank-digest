from datetime import datetime, timezone

from thinktank_digest.analyze import rank_articles
from thinktank_digest.models import Analysis, DigestArticle, DigestReport
from thinktank_digest.report import render_html, render_plain_text


def _item(title: str, importance: int, source_priority: int, tags: list[str]) -> DigestArticle:
    return DigestArticle(
        title=title,
        url=f"https://example.org/{title}",
        publish_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        source="Example",
        source_priority=source_priority,
        analysis=Analysis(
            relevant=True,
            conclusion=f"{title} conclusion",
            key_points=["point"],
            china_impact="china",
            indo_pacific_impact="indo-pacific",
            international_security_impact="security",
            global_economy_impact="economy",
            importance=importance,
            topic_tags=tags,
        ),
    )


def test_ranking_prioritizes_importance_and_source_priority() -> None:
    lower = _item("lower", 3, 5, ["Economics"])
    higher = _item("higher", 5, 3, ["China"])

    assert rank_articles([lower, higher])[0].title == "higher"


def test_report_renders_chinese_sections() -> None:
    item = _item("china-report", 5, 5, ["China", "Defense"])
    report = DigestReport(
        generated_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        top_items=[item],
        all_items=[item],
        synthesis="今日重点集中在中国与安全议题。",
    )

    html = render_html(report)
    plain = render_plain_text(report)

    assert "今日最重要研究" in html
    assert "今日重点观察" in html
    assert "按主题分类" in html
    assert "全部新增研究" in html
    assert "今日重点集中在中国与安全议题。" in plain
