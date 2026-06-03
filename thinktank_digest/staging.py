from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import Analysis, RawArticle
from .pipeline import run_daily_digest
from .report import render_html, render_plain_text

LOGGER = logging.getLogger(__name__)

STAGING_TEXT = """
This staging report assesses China, Taiwan, and Indo-Pacific security dynamics in a
period of intensified great-power competition. It reviews military deterrence,
economic coercion, semiconductor supply-chain exposure, artificial intelligence
governance, and the implications for regional allies and partners. The analysis
argues that policymakers should treat technology controls, defense posture, and
crisis communication as connected instruments rather than isolated policy tracks.
It also notes that trade fragmentation and energy security pressures can amplify
security risks when strategic rivalry hardens. This synthetic text is intentionally
long enough to exercise article extraction, database insertion, summarization,
ranking, report generation, and email delivery code paths during staging tests.
The staging workflow does not represent a real publication and should never be
included in production source discovery.
""" * 3


def staging_discover(_sources: list) -> list[RawArticle]:
    return [
        RawArticle(
            title="Staging: China, Taiwan and Indo-Pacific Security Test",
            url="https://staging.thinktank-digest.local/china-taiwan-indo-pacific",
            publish_date=datetime(2026, 6, 2, tzinfo=timezone.utc),
            source="Staging Source",
            source_priority=5,
        )
    ]


def staging_hydrate(article: RawArticle) -> RawArticle:
    return RawArticle(
        title=article.title,
        url=article.url,
        publish_date=article.publish_date,
        source=article.source,
        source_priority=article.source_priority,
        text=STAGING_TEXT,
    )


def staging_analyze(_article: RawArticle) -> Analysis:
    return Analysis(
        relevant=True,
        conclusion="模拟研究显示，台海安全、技术管制与印太威慑正在相互强化。",
        key_points=[
            "大国竞争正在把安全、科技和经济政策压缩到同一战略议程中。",
            "台海风险对印太联盟协调、危机沟通和供应链稳定具有放大效应。",
            "AI 与半导体政策会影响军民两用技术扩散和长期竞争优势。",
        ],
        china_impact="对中国而言，该议题会影响周边安全压力、科技获取路径与对外政策空间。",
        indo_pacific_impact="对印太而言，区域国家会更重视威慑、韧性供应链和危机管控机制。",
        international_security_impact="对国际安全而言，误判风险、军备竞争和技术扩散治理的重要性上升。",
        global_economy_impact="对全球经济而言，半导体、贸易限制和供应链重组可能推高企业合规与运营成本。",
        importance=5,
        topic_tags=["China", "Taiwan", "Indo-Pacific", "AI", "Semiconductors", "Defense"],
    )


class StagingMailer:
    def __init__(self, outbox_path: Path) -> None:
        self.outbox_path = outbox_path
        self.messages: list[dict] = []

    def send(self, subject: str, html: str, plain_text: str) -> str:
        self.messages.append(
            {
                "subject": subject,
                "html_length": len(html),
                "plain_text_length": len(plain_text),
                "contains_article": "Staging: China, Taiwan" in html,
            }
        )
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        self.outbox_path.write_text(
            json.dumps(self.messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        LOGGER.info("Staging email captured at %s", self.outbox_path)
        return "staging-recipient@example.test"


def run_staging_workflow(*, sources_path: Path, db_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    mailer = StagingMailer(out_dir / "staging_outbox.json")
    first = run_daily_digest(
        sources_path=sources_path,
        db_path=db_path,
        send=True,
        max_articles=5,
        discover_fn=staging_discover,
        hydrate_fn=staging_hydrate,
        analyze_fn=staging_analyze,
        send_fn=mailer.send,
        synthesize_fn=lambda _items: "模拟重点观察：台海、科技和印太安全议题形成共同战略信号。",
    )
    (out_dir / "staging_report.html").write_text(render_html(first), encoding="utf-8")
    (out_dir / "staging_report.txt").write_text(render_plain_text(first), encoding="utf-8")

    second = run_daily_digest(
        sources_path=sources_path,
        db_path=db_path,
        send=True,
        max_articles=5,
        discover_fn=staging_discover,
        hydrate_fn=staging_hydrate,
        analyze_fn=staging_analyze,
        send_fn=mailer.send,
        synthesize_fn=lambda _items: "第二次运行未发现新的待分析研究。",
    )

    result = {
        "first_run_articles": len(first.all_items),
        "second_run_articles": len(second.all_items),
        "emails_captured": len(mailer.messages),
        "html_report": str(out_dir / "staging_report.html"),
        "outbox": str(mailer.outbox_path),
        "duplicate_prevention_ok": len(first.all_items) == 1 and len(second.all_items) == 0,
    }
    (out_dir / "staging_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not result["duplicate_prevention_ok"]:
        raise RuntimeError("staging duplicate-prevention check failed")
    return result
