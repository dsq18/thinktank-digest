from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


TOPICS = [
    "China",
    "Taiwan",
    "Indo-Pacific",
    "US-China Relations",
    "Technology",
    "AI",
    "Semiconductors",
    "Defense",
    "Military",
    "Economics",
    "Trade",
    "Energy",
    "Europe",
    "Russia",
    "Middle East",
]

PRIORITY_TOPICS = {
    "china",
    "taiwan",
    "indo-pacific",
    "great power competition",
    "national security",
    "defense",
    "emerging technology",
    "ai",
    "geoeconomics",
}


@dataclass(frozen=True)
class Source:
    name: str
    website: str
    rss: str | None
    enabled: bool
    priority: int
    topics: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RawArticle:
    title: str
    url: str
    publish_date: datetime | None
    source: str
    source_priority: int
    text: str = ""


@dataclass(frozen=True)
class Analysis:
    relevant: bool
    conclusion: str
    key_points: list[str]
    china_impact: str
    indo_pacific_impact: str
    international_security_impact: str
    global_economy_impact: str
    importance: int
    topic_tags: list[str]

    @classmethod
    def irrelevant(cls, reason: str = "主题相关性不足") -> "Analysis":
        return cls(
            relevant=False,
            conclusion=reason,
            key_points=[],
            china_impact="",
            indo_pacific_impact="",
            international_security_impact="",
            global_economy_impact="",
            importance=1,
            topic_tags=[],
        )


@dataclass(frozen=True)
class DigestArticle:
    title: str
    url: str
    publish_date: datetime | None
    source: str
    source_priority: int
    analysis: Analysis
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class DigestReport:
    generated_at: datetime
    top_items: list[DigestArticle]
    all_items: list[DigestArticle]
    synthesis: str
