from datetime import timezone

from thinktank_digest.ingest import _discover_from_feed
from thinktank_digest.models import Source


class FakeClient:
    pass


def test_rss_ingestion_extracts_metadata(monkeypatch) -> None:
    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel>
      <title>Example</title>
      <item>
        <title>China strategy and Indo-Pacific security report</title>
        <link>https://example.org/report#section</link>
        <pubDate>Mon, 01 Jun 2026 00:00:00 GMT</pubDate>
      </item>
    </channel></rss>
    """
    monkeypatch.setattr("thinktank_digest.ingest.fetch_url", lambda _client, _url: rss)
    source = Source(
        name="Example",
        website="https://example.org",
        rss="https://example.org/feed",
        enabled=True,
        priority=5,
        topics=["China"],
        tags=["test"],
    )

    articles = _discover_from_feed(source, FakeClient())

    assert len(articles) == 1
    assert articles[0].title == "China strategy and Indo-Pacific security report"
    assert articles[0].url == "https://example.org/report"
    assert articles[0].publish_date is not None
    assert articles[0].publish_date.tzinfo == timezone.utc
    assert articles[0].source_priority == 5
