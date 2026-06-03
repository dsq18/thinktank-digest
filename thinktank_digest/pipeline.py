from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .analyze import analyze_article, rank_articles, synthesize_observations
from .emailer import send_email
from .ingest import discover_articles, hydrate_article_text
from .models import DigestReport
from .report import render_html, render_plain_text
from .sources import load_sources

LOGGER = logging.getLogger(__name__)

DiscoverFn = Callable[[list], list]
HydrateFn = Callable[[object], object]
AnalyzeFn = Callable[[object], object]
SendFn = Callable[[str, str, str], str]
SynthesizeFn = Callable[[list], str]


def run_daily_digest(
    *,
    sources_path: Path,
    db_path: Path,
    send: bool = True,
    max_articles: int = 60,
    discover_fn: DiscoverFn = discover_articles,
    hydrate_fn: HydrateFn = hydrate_article_text,
    analyze_fn: AnalyzeFn = analyze_article,
    send_fn: SendFn = send_email,
    synthesize_fn: SynthesizeFn = synthesize_observations,
) -> DigestReport:
    db.init_db(db_path)
    sources = load_sources(sources_path)
    LOGGER.info("Loaded %s sources (%s enabled)", len(sources), len([s for s in sources if s.enabled]))

    discovered = discover_fn(sources)
    LOGGER.info("Discovered %s candidate articles", len(discovered))

    inserted = 0
    for candidate in discovered[:max_articles]:
        if db.has_url(db_path, candidate.url):
            continue
        hydrated = hydrate_fn(candidate)
        if len(hydrated.text) < 500:
            LOGGER.info("Skipping low-text article: %s", hydrated.url)
            db.insert_discovered(db_path, hydrated)
            db.mark_skipped(db_path, hydrated.url, "正文过短或无法提取")
            continue
        if db.insert_discovered(db_path, hydrated):
            inserted += 1
    LOGGER.info("Inserted %s new articles", inserted)

    pending = db.pending_articles(db_path)
    LOGGER.info("Analyzing %s pending articles", len(pending))
    newly_analyzed_urls: list[str] = []
    for article in pending:
        try:
            analysis = analyze_fn(article)
            db.save_analysis(db_path, article.url, analysis)
            if analysis.relevant:
                newly_analyzed_urls.append(article.url)
        except Exception as exc:
            LOGGER.exception("Analysis failed for %s: %s", article.url, exc)
            db.mark_skipped(db_path, article.url, f"分析失败：{exc}")

    ranked = rank_articles(db.analyzed_by_urls(db_path, newly_analyzed_urls))
    synthesis = synthesize_fn(ranked)
    report = DigestReport(
        generated_at=datetime.now(timezone.utc),
        top_items=ranked[:5],
        all_items=ranked,
        synthesis=synthesis,
    )

    if send:
        html = render_html(report)
        plain = render_plain_text(report)
        subject = f"ThinkTank-Digest 每日地缘政治简报 {report.generated_at.strftime('%Y-%m-%d')}"
        try:
            recipient = send_fn(subject, html, plain)
            db.log_email(db_path, recipient, subject, True, None)
        except Exception as exc:
            LOGGER.exception("Email delivery failed: %s", exc)
            db.log_email(db_path, "unknown", subject, False, str(exc))
            raise
    return report
