"""Corpus C — Live market news fetcher.

Fetches India-focused financial/market news from external sources and returns
them as KnowledgeChunk-compatible dicts for indexing via the existing _sync()
pipeline.

Architecture:
  GNews API (primary)
       ↓  fails?
  Google News RSS (fallback, no key required)
       ↓  both fail?
  Return empty list — existing index is preserved, retrieval keeps working.

Design constraints:
- This module is the single network seam for news. Tests monkeypatch
  ``_fetch_gnews_raw`` and ``_fetch_rss_raw`` to stay offline.
- Each article becomes one chunk. The chunk_key is deterministic so repeated
  fetches never create duplicate rows (idempotent via the existing _sync()).
- No model changes needed: body packs title + summary + metadata as readable
  text; source_reference holds the article URL.
- Financial safety: article text is factual context only. The LLM prompt
  (in chatbot.py) already forbids specific buy/sell recommendations.

Deduplication key strategy (stable, no DB column needed):
  1. Use the GNews ``id`` field when present (source-assigned, stable).
  2. Otherwise hash the normalised URL (strip utm_* params, lowercase).
  3. Prefix: ``news:{domain}:{hash_or_id}``

Freshness:
  Handled at ingestion — reindex_corpus_c() only imports articles published
  within MAX_ARTICLE_AGE_HOURS. Stale chunks are deleted by the same pass.
  Retrieval therefore gets freshness for free: if a chunk is in the DB, it
  is recent by construction.
"""

from __future__ import annotations

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import TypedDict
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# GNews free tier: 100 requests/day. Fetching 6 times/day at 10 articles each
# uses 6 requests — well inside the limit.
GNEWS_BASE = "https://gnews.io/api/v4/top-headlines"
GNEWS_PARAMS = {
    "topic": "business",
    "country": "in",        # India
    "lang": "en",
    "max": "10",            # 10 articles per call
}

# Google News RSS — India top headlines (no key required, updated hourly).
# Using the top-headlines feed rather than a search query because search RSS
# returns older/archived articles; the headlines feed is always fresh.
GOOGLE_RSS_URL = (
    "https://news.google.com/rss/headlines/section/geo/IN"
    "?hl=en-IN&gl=IN&ceid=IN:en"
)

# Reliable India financial news RSS feeds used as fallback (no key required).
# Tried in order until one returns at least one article.
FALLBACK_RSS_FEEDS = [
    # Economic Times — Markets section (reliable, updated continuously)
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    # Moneycontrol — Top news
    "https://www.moneycontrol.com/rss/MCtopnews.xml",
    # Google News search (broader; may return older articles)
    (
        "https://news.google.com/rss/search"
        "?q=india+stock+market+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en"
    ),
]

# Only index articles published within this window. 7 days gives a comfortable
# buffer for RSS feeds where pubDate can lag the actual publish time by hours.
# Stale chunks are pruned at reindex time so retrieval always sees useful content.
MAX_ARTICLE_AGE_HOURS = 168  # 7 days

# Params to strip from URLs before hashing (tracking noise).
_UTM_PATTERN = re.compile(r"utm_[^&]+&?")


# ---------------------------------------------------------------------------
# Typed article dict (internal)
# ---------------------------------------------------------------------------
class _Article(TypedDict):
    article_id:   str          # deterministic dedup key (no prefix)
    domain:       str          # source domain for chunk_key prefix
    title:        str
    summary:      str          # may be empty string
    url:          str
    source_name:  str
    published_at: datetime     # timezone-aware UTC


# ---------------------------------------------------------------------------
# URL normalisation for deduplication
# ---------------------------------------------------------------------------
def _normalise_url(url: str) -> str:
    """Strip tracking params and normalise for hashing."""
    parsed = urlparse(url.lower().strip())
    qs = {k: v for k, v in parse_qs(parsed.query).items()
          if not k.startswith("utm_")}
    clean = parsed._replace(query=urlencode(qs, doseq=True), fragment="")
    return urlunparse(clean)


def _url_hash(url: str) -> str:
    """8-char hex digest of the normalised URL — collision risk negligible."""
    return hashlib.sha256(_normalise_url(url).encode()).hexdigest()[:8]


def _domain(url: str) -> str:
    """e.g. 'economictimes.indiatimes.com' → 'economictimes'"""
    host = urlparse(url).netloc.lstrip("www.")
    return host.split(".")[0] if host else "unknown"


def _article_id(raw_id: str | None, url: str) -> tuple[str, str]:
    """Return (domain, stable_id). Prefers the source-assigned id."""
    dom = _domain(url)
    if raw_id and len(raw_id) < 80:
        # Clean the source id: keep only alphanumeric + hyphen
        clean = re.sub(r"[^a-z0-9\-]", "", raw_id.lower())[:40]
        if clean:
            return dom, clean
    return dom, _url_hash(url)


# ---------------------------------------------------------------------------
# Network seams (monkeypatched in tests)
# ---------------------------------------------------------------------------
def _fetch_gnews_raw(api_key: str) -> dict:
    """GET the GNews API and return the parsed JSON. Raises on failure."""
    import urllib.request
    params = dict(GNEWS_PARAMS)
    params["apikey"] = api_key
    url = GNEWS_BASE + "?" + urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as resp:
        import json
        return json.loads(resp.read().decode())


def _fetch_rss_raw(url: str) -> bytes:
    """GET an RSS feed URL with a browser User-Agent. Raises on failure."""
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def _parse_gnews(data: dict) -> list[_Article]:
    """Parse GNews JSON response into internal _Article dicts."""
    articles: list[_Article] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_ARTICLE_AGE_HOURS)

    for item in data.get("articles", []):
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue

        # Parse published_at
        pub_str = item.get("publishedAt") or ""
        try:
            pub = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pub = datetime.now(timezone.utc)

        if pub < cutoff:
            continue

        dom, aid = _article_id(item.get("id"), url)
        articles.append(_Article(
            article_id=aid,
            domain=dom,
            title=title,
            summary=(item.get("description") or "").strip(),
            url=url,
            source_name=(item.get("source", {}).get("name") or dom).strip(),
            published_at=pub,
        ))

    return articles


def _parse_rss(raw: bytes) -> list[_Article]:
    """Parse Google News RSS bytes into internal _Article dicts."""
    articles: list[_Article] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_ARTICLE_AGE_HOURS)

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log.warning("RSS parse error: %s", e)
        return []

    ns = {"media": "http://search.yahoo.com/mrss/"}
    channel = root.find("channel")
    if channel is None:
        return []

    for item in channel.findall("item"):
        url = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        if not url or not title:
            continue

        pub_str = item.findtext("pubDate") or ""
        try:
            pub = parsedate_to_datetime(pub_str)
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
        except Exception:
            pub = datetime.now(timezone.utc)

        if pub < cutoff:
            continue

        summary = (item.findtext("description") or "").strip()
        # Strip HTML tags from RSS description
        summary = re.sub(r"<[^>]+>", " ", summary).strip()
        summary = re.sub(r"\s+", " ", summary)[:400]

        source_el = item.find("source")
        source_name = (source_el.text if source_el is not None else "") or _domain(url)

        dom, aid = _article_id(None, url)
        articles.append(_Article(
            article_id=aid,
            domain=dom,
            title=title,
            summary=summary,
            url=url,
            source_name=source_name.strip(),
            published_at=pub,
        ))

    return articles


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def fetch_gnews(api_key: str) -> list[_Article]:
    """Fetch from GNews API. Returns empty list on any failure."""
    try:
        data = _fetch_gnews_raw(api_key)
        articles = _parse_gnews(data)
        log.info("GNews: fetched %d usable articles", len(articles))
        return articles
    except Exception as e:
        log.warning("GNews fetch failed: %s", e)
        return []


def fetch_google_rss() -> list[_Article]:
    """Fetch from India financial RSS feeds. Tries FALLBACK_RSS_FEEDS in order.

    Returns articles from the first feed that succeeds. If all fail, returns [].
    """
    for feed_url in FALLBACK_RSS_FEEDS:
        try:
            raw = _fetch_rss_raw(feed_url)
            articles = _parse_rss(raw)
            if articles:
                log.info(
                    "RSS: fetched %d usable articles from %s",
                    len(articles), feed_url.split("/")[2],
                )
                return articles
            log.debug("RSS feed returned 0 usable articles: %s", feed_url)
        except Exception as e:
            log.warning("RSS feed failed (%s): %s", feed_url.split("/")[2], e)

    log.warning("All RSS fallback feeds exhausted with no usable articles.")
    return []


def fetch_news(api_key: str) -> list[_Article]:
    """Fetch news with GNews primary, RSS fallback.

    - GNews first (structured, high quality).
    - If GNews returns nothing (empty key, error, quota exhausted),
      fall back to Google News RSS (no key needed).
    - If both fail, returns [] — the caller should preserve the existing index.
    """
    if api_key:
        articles = fetch_gnews(api_key)
        if articles:
            return articles
        log.info("GNews returned no articles; trying RSS fallback")
    else:
        log.info("No GNews API key configured; using RSS fallback")

    return fetch_google_rss()


def build_corpus_c_chunks(articles: list[_Article]) -> list[dict]:
    """Convert fetched articles into KnowledgeChunk-compatible dicts.

    Each chunk uses the same shape as build_corpus_a() / build_corpus_b():
        chunk_key      — deterministic, used for idempotent upsert
        source_title   — article headline
        source_reference — article URL (existing column)
        body           — structured text: headline + summary + metadata line

    The metadata line makes the chunk self-describing for the LLM and for
    the frontend citation display, without needing any new DB columns.
    """
    chunks: list[dict] = []
    seen_keys: set[str] = set()

    for article in articles:
        chunk_key = f"news:{article['domain']}:{article['article_id']}"

        # Skip true duplicates within one fetch batch (same URL, two sources)
        if chunk_key in seen_keys:
            continue
        seen_keys.add(chunk_key)

        pub_str = article["published_at"].strftime("%d %b %Y %H:%M UTC")
        body_parts = [f"Headline: {article['title']}"]
        if article["summary"]:
            body_parts.append(f"Summary: {article['summary']}")
        body_parts.append(
            f"Source: {article['source_name']} | Published: {pub_str} | "
            f"Corpus: C (live news)"
        )
        body = "\n".join(body_parts)

        chunks.append({
            "chunk_key": chunk_key,
            "source_title": article["title"],
            "source_reference": article["url"],
            "body": body,
        })

    return chunks
