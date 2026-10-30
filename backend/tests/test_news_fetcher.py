"""Tests for Corpus C — live market news fetcher.

These tests are fully offline. Network fetch functions are monkeypatched at
all fetch boundaries, including the RSS fallback.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import KnowledgeChunk
from app.services import indexer, retrieval
from app.services.news_fetcher import (
    MAX_ARTICLE_AGE_HOURS,
    _parse_gnews,
    _parse_rss,
    _url_hash,
    build_corpus_c_chunks,
    fetch_news,
)


def _gnews_article(
    title="Nifty hits record high",
    url="https://economictimes.com/markets/nifty-record",
    source="Economic Times",
    article_id="et-nifty-001",
    hours_ago=1,
    description="Nifty 50 rose 200 points today on broad-based buying.",
):
    published = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "id": article_id,
        "title": title,
        "url": url,
        "description": description,
        "publishedAt": published,
        "source": {"name": source, "url": "https://economictimes.com"},
    }


def _gnews_response(articles=None):
    # Do not use `articles or [...]`: an explicitly empty list must stay empty.
    return {"articles": [_gnews_article()] if articles is None else articles}


def _rss_item(
    title="Sensex up 500 pts",
    link="https://livemint.com/sensex-up",
    pub_date=None,
    description="Sensex climbs 500 points driven by banking stocks.",
    source_name="Livemint",
):
    if pub_date is None:
        pub_date = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
            "%a, %d %b %Y %H:%M:%S +0000"
        )
    return f"""
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <pubDate>{pub_date}</pubDate>
      <description>{description}</description>
      <source url="https://livemint.com">{source_name}</source>
    </item>"""


def _rss_feed(items=None):
    items_xml = [_rss_item()] if items is None else items
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<rss><channel><title>Google News</title>"
        + "".join(items_xml)
        + "</channel></rss>"
    ).encode()


def _settings_mock(monkeypatch, api_key="test-key"):
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: type("S", (), {"gnews_api_key": api_key})(),
    )


def _mock_rss(monkeypatch, payload=None):
    if payload is None:
        payload = _rss_feed()
    monkeypatch.setattr(
        "app.services.news_fetcher._fetch_rss_raw",
        lambda feed_url: payload,
    )


class TestGNewsFetch:
    def test_gnews_successful_fetch_returns_articles(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda api_key: _gnews_response(),
        )
        articles = fetch_news("test-key")
        assert len(articles) == 1
        assert articles[0]["title"] == "Nifty hits record high"
        assert articles[0]["source_name"] == "Economic Times"

    def test_gnews_chunk_key_uses_source_id(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda api_key: _gnews_response(),
        )
        chunks = build_corpus_c_chunks(fetch_news("test-key"))
        assert chunks[0]["chunk_key"].startswith("news:")
        assert "et-nifty-001" in chunks[0]["chunk_key"]


class TestRSSFallback:
    def test_rss_used_when_no_gnews_key(self, monkeypatch):
        _mock_rss(monkeypatch)
        articles = fetch_news(api_key="")
        assert len(articles) == 1
        assert "Sensex" in articles[0]["title"]

    def test_rss_fallback_when_gnews_fails(self, monkeypatch):
        def fail(_api_key):
            raise ConnectionError("GNews down")

        monkeypatch.setattr("app.services.news_fetcher._fetch_gnews_raw", fail)
        _mock_rss(monkeypatch)
        articles = fetch_news(api_key="some-key")
        assert len(articles) == 1


class TestMalformedArticles:
    def test_gnews_article_missing_url_skipped(self, monkeypatch):
        bad = _gnews_article()
        bad["url"] = ""
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response([bad]),
        )
        # Invalid GNews results trigger fallback; stub it to remain offline.
        _mock_rss(monkeypatch, b"not xml at all <<<")
        assert fetch_news("test-key") == []

    def test_gnews_article_missing_title_skipped(self, monkeypatch):
        bad = _gnews_article()
        bad["title"] = ""
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response([bad]),
        )
        _mock_rss(monkeypatch, b"not xml at all <<<")
        assert fetch_news("test-key") == []

    def test_rss_invalid_xml_returns_empty(self, monkeypatch):
        _mock_rss(monkeypatch, b"not xml at all <<<")
        assert fetch_news(api_key="") == []

    def test_gnews_bad_published_date_still_parsed(self, monkeypatch):
        article = _gnews_article()
        article["publishedAt"] = "not-a-date"
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response([article]),
        )
        articles = fetch_news("test-key")
        assert len(articles) == 1


class TestDeduplication:
    def test_same_url_produces_same_chunk_key(self):
        url = "https://economictimes.com/markets/nifty"
        article1 = _gnews_article(url=url, article_id="")
        article2 = _gnews_article(url=url, article_id="")
        chunks1 = build_corpus_c_chunks(_parse_gnews({"articles": [article1]}))
        chunks2 = build_corpus_c_chunks(_parse_gnews({"articles": [article2]}))
        assert chunks1[0]["chunk_key"] == chunks2[0]["chunk_key"]

    def test_duplicate_articles_in_batch_deduplicated(self):
        article = _gnews_article(url="https://et.com/a1", article_id="dup-001")
        chunks = build_corpus_c_chunks(_parse_gnews({"articles": [article, article]}))
        assert len(chunks) == 1


class TestMetadataPreservation:
    def test_chunk_body_contains_title_and_source(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response(),
        )
        chunks = build_corpus_c_chunks(fetch_news("test-key"))
        body = chunks[0]["body"]
        assert "Nifty hits record high" in body
        assert "Economic Times" in body
        assert "Corpus: C" in body

    def test_chunk_source_reference_is_article_url(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response(),
        )
        chunks = build_corpus_c_chunks(fetch_news("test-key"))
        assert chunks[0]["source_reference"] == "https://economictimes.com/markets/nifty-record"

    def test_chunk_source_title_is_article_headline(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response(),
        )
        chunks = build_corpus_c_chunks(fetch_news("test-key"))
        assert chunks[0]["source_title"] == "Nifty hits record high"


class TestCorpusCFiltering:
    def test_corpus_c_chunks_retrievable_with_c_selector(self, db):
        db.add(KnowledgeChunk(
            corpus="C", chunk_key="news:test:abc123", owner_user_id=None,
            source_title="Nifty rally", source_reference="https://example.com/nifty",
            body="Headline: Nifty hits record\nSummary: Markets surged today.",
        ))
        db.commit()
        result = retrieval.retrieve(db, "nifty record", corpus="C")
        assert any(c.chunk_id == "news:test:abc123" for c in result.chunks)

    def test_corpus_a_query_does_not_return_corpus_c(self, db):
        db.add(KnowledgeChunk(
            corpus="C", chunk_key="news:test:only-c", owner_user_id=None,
            source_title="C-only news", body="Something only in corpus C.",
        ))
        db.commit()
        result = retrieval.retrieve(db, "corpus C only", corpus="A")
        assert "news:test:only-c" not in [c.chunk_id for c in result.chunks]


class TestFreshnessFiltering:
    def test_old_article_excluded_from_gnews(self, monkeypatch):
        old = _gnews_article(hours_ago=MAX_ARTICLE_AGE_HOURS + 2)
        fresh = _gnews_article(
            title="Fresh news", url="https://example.com/fresh",
            article_id="fresh-001", hours_ago=1,
        )
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response([old, fresh]),
        )
        articles = fetch_news("test-key")
        assert len(articles) == 1
        assert articles[0]["title"] == "Fresh news"

    def test_old_article_excluded_from_rss(self, monkeypatch):
        old_date = (
            datetime.now(timezone.utc) - timedelta(hours=MAX_ARTICLE_AGE_HOURS + 3)
        ).strftime("%a, %d %b %Y %H:%M:%S +0000")
        _mock_rss(monkeypatch, _rss_feed([_rss_item(pub_date=old_date)]))
        assert fetch_news(api_key="") == []


class TestIndexingIntegration:
    def test_reindex_corpus_c_inserts_chunks(self, db, monkeypatch):
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response(),
        )
        _settings_mock(monkeypatch)
        result = indexer.reindex_corpus_c(db, embed=False)
        assert result["inserted"] >= 1
        assert result["status"] == "ok"

    def test_reindex_corpus_c_chunks_have_no_owner(self, db, monkeypatch):
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response(),
        )
        _settings_mock(monkeypatch)
        indexer.reindex_corpus_c(db, embed=False)
        rows = db.query(KnowledgeChunk).filter_by(corpus="C").all()
        assert all(row.owner_user_id is None for row in rows)


class TestCorpusCRetrieval:
    def test_all_selector_returns_corpus_c_chunks(self, db):
        db.add(KnowledgeChunk(
            corpus="C", chunk_key="news:livemint:xyz789", owner_user_id=None,
            source_title="RBI holds rates",
            body="Headline: RBI holds rates steady\nSummary: RBI kept repo rate unchanged.",
        ))
        db.commit()
        result = retrieval.retrieve(db, "rbi rates repo", corpus="C")
        assert any(c.chunk_id == "news:livemint:xyz789" for c in result.chunks)

    def test_corpus_c_not_mixed_into_corpus_b(self, db, user):
        db.add(KnowledgeChunk(
            corpus="C", chunk_key="news:test:should-not-appear", owner_user_id=None,
            source_title="Should not appear in B query",
            body="Corpus C article that must not leak into B retrieval.",
        ))
        db.commit()
        result = retrieval.retrieve(
            db, "should not appear", user_id=user.id, corpus="B"
        )
        assert "news:test:should-not-appear" not in [c.chunk_id for c in result.chunks]


class TestBothSourcesFailing:
    def test_fetch_news_returns_empty_when_both_fail(self, monkeypatch):
        def fail_gnews(_api_key):
            raise ConnectionError("GNews down")

        def fail_rss(_feed_url):
            raise ConnectionError("RSS down")

        monkeypatch.setattr("app.services.news_fetcher._fetch_gnews_raw", fail_gnews)
        monkeypatch.setattr("app.services.news_fetcher._fetch_rss_raw", fail_rss)
        assert fetch_news("test-key") == []

    def test_reindex_corpus_c_preserves_existing_index_on_failure(self, db, monkeypatch):
        db.add(KnowledgeChunk(
            corpus="C", chunk_key="news:existing:preserved", owner_user_id=None,
            source_title="Pre-existing news chunk",
            body="This should survive a failed refresh.",
        ))
        db.commit()

        def fail_gnews(_api_key):
            raise ConnectionError("GNews down")

        def fail_rss(_feed_url):
            raise ConnectionError("RSS down")

        monkeypatch.setattr("app.services.news_fetcher._fetch_gnews_raw", fail_gnews)
        monkeypatch.setattr("app.services.news_fetcher._fetch_rss_raw", fail_rss)
        _settings_mock(monkeypatch)
        result = indexer.reindex_corpus_c(db, embed=False)
        assert result["status"] == "no_articles"
        assert db.query(KnowledgeChunk).filter_by(
            chunk_key="news:existing:preserved"
        ).first() is not None


class TestMissingApiKey:
    def test_empty_key_uses_rss_fallback(self, monkeypatch):
        rss_called = []

        def rss(feed_url):
            rss_called.append(feed_url)
            return _rss_feed()

        monkeypatch.setattr("app.services.news_fetcher._fetch_rss_raw", rss)
        articles = fetch_news(api_key="")
        assert rss_called
        assert len(articles) >= 1

    def test_missing_key_does_not_raise(self, monkeypatch):
        _mock_rss(monkeypatch)
        assert isinstance(fetch_news(api_key=""), list)


class TestIdempotency:
    def test_second_reindex_inserts_nothing(self, db, monkeypatch):
        monkeypatch.setattr(
            "app.services.news_fetcher._fetch_gnews_raw",
            lambda _api_key: _gnews_response(),
        )
        _settings_mock(monkeypatch)
        first = indexer.reindex_corpus_c(db, embed=False)
        second = indexer.reindex_corpus_c(db, embed=False)
        assert first["inserted"] >= 1
        assert second["inserted"] == 0
        assert second["updated"] == 0

    def test_chunk_key_stability_across_fetches(self):
        article = _gnews_article()
        articles1 = _parse_gnews({"articles": [article]})
        articles2 = _parse_gnews({"articles": [article]})
        key1 = build_corpus_c_chunks(articles1)[0]["chunk_key"]
        key2 = build_corpus_c_chunks(articles2)[0]["chunk_key"]
        assert key1 == key2
