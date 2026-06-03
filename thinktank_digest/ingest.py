from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
import trafilatura
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import RawArticle, Source

LOGGER = logging.getLogger(__name__)

USER_AGENT = "ThinkTank-Digest/0.1 (+https://github.com/actions)"


def _clean_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed._replace(fragment="").geturl()


def _parse_date(value: object) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, str):
            if "," in value and any(token in value for token in ["GMT", "UTC", "+", "-"]):
                try:
                    return parsedate_to_datetime(value).astimezone(timezone.utc)
                except (TypeError, ValueError):
                    pass
            parsed = date_parser.parse(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def fetch_url(client: httpx.Client, url: str) -> str:
    response = client.get(url, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def extract_article_text(html: str, url: str) -> str:
    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if extracted:
        return extracted.strip()
    soup = BeautifulSoup(html, "html.parser")
    for unwanted in soup(["script", "style", "nav", "footer", "header", "aside"]):
        unwanted.decompose()
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return "\n".join(paragraph for paragraph in paragraphs if paragraph).strip()


def _discover_from_feed(source: Source, client: httpx.Client) -> list[RawArticle]:
    if not source.rss:
        return []
    LOGGER.info("Reading RSS for %s: %s", source.name, source.rss)
    try:
        feed_text = fetch_url(client, source.rss)
    except Exception as exc:
        LOGGER.warning("RSS failed for %s, will crawl website: %s", source.name, exc)
        return []

    feed = feedparser.parse(feed_text)
    if feed.bozo and not feed.entries:
        LOGGER.warning("RSS parse failed for %s, will crawl website", source.name)
        return []

    articles: list[RawArticle] = []
    for entry in feed.entries[:40]:
        url = _clean_url(getattr(entry, "link", "") or "")
        title = (getattr(entry, "title", "") or "").strip()
        if not url or not title:
            continue
        published = (
            getattr(entry, "published", None)
            or getattr(entry, "updated", None)
            or getattr(entry, "created", None)
        )
        articles.append(
            RawArticle(
                title=title,
                url=url,
                publish_date=_parse_date(published),
                source=source.name,
                source_priority=source.priority,
            )
        )
    return articles


def _discover_from_website(source: Source, client: httpx.Client) -> list[RawArticle]:
    LOGGER.info("Crawling website for %s: %s", source.name, source.website)
    try:
        html = fetch_url(client, source.website)
    except Exception as exc:
        LOGGER.error("Website crawl failed for %s: %s", source.name, exc)
        return []

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlparse(source.website).netloc
    seen: set[str] = set()
    articles: list[RawArticle] = []
    keywords = (
        "china",
        "taiwan",
        "indo-pacific",
        "security",
        "defence",
        "defense",
        "technology",
        "ai",
        "economy",
        "trade",
        "russia",
        "middle-east",
        "military",
    )
    for anchor in soup.find_all("a", href=True):
        title = anchor.get_text(" ", strip=True)
        if len(title) < 20:
            continue
        url = _clean_url(urljoin(source.website, anchor["href"]))
        parsed = urlparse(url)
        if parsed.netloc and parsed.netloc != source_host:
            continue
        haystack = f"{title} {parsed.path}".casefold()
        if not any(keyword in haystack for keyword in keywords):
            continue
        if url in seen:
            continue
        seen.add(url)
        articles.append(
            RawArticle(
                title=title,
                url=url,
                publish_date=None,
                source=source.name,
                source_priority=source.priority,
            )
        )
        if len(articles) >= 25:
            break
    return articles


def discover_articles(sources: list[Source], timeout: float = 20.0) -> list[RawArticle]:
    enabled_sources = [source for source in sources if source.enabled]
    discovered: list[RawArticle] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for source in enabled_sources:
            articles = _discover_from_feed(source, client)
            if not articles:
                articles = _discover_from_website(source, client)
            discovered.extend(articles)
    return discovered


def hydrate_article_text(article: RawArticle, timeout: float = 20.0) -> RawArticle:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        try:
            html = fetch_url(client, article.url)
            text = extract_article_text(html, article.url)
        except Exception as exc:
            LOGGER.warning("Article extraction failed for %s: %s", article.url, exc)
            text = ""
    return RawArticle(
        title=article.title,
        url=article.url,
        publish_date=article.publish_date,
        source=article.source,
        source_priority=article.source_priority,
        text=text,
    )
