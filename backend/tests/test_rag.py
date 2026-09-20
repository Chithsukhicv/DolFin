"""RAG substrate: indexing, ranking, and per-user retrieval scoping.

The security tests here matter most. DolFin has no authentication — ``user_id``
arrives in a request body — so the Retriever being the single enforcement point
is the only thing standing between one learner's trade history and another
learner's prompt.
"""

from __future__ import annotations

import pytest

from app.models import Goal, InterventionLog, KnowledgeChunk, User
from app.services import indexer, ranking, retrieval
from app.services import portfolio as portfolio_service


@pytest.fixture(autouse=True)
def clear_retrieval_cache():
    retrieval.reset_cache()
    yield
    retrieval.reset_cache()


@pytest.fixture
def corpus_a(db):
    """Index the curated corpus without embeddings (no key in tests)."""
    indexer.reindex_corpus_a(db, embed=False)
    return db


class TestCorpusAConstruction:
    def test_builds_a_substantial_corpus(self):
        chunks = indexer.build_corpus_a()
        assert len(chunks) >= 80, f"only {len(chunks)} chunks built"

    def test_chunk_keys_are_unique(self):
        keys = [c["chunk_key"] for c in indexer.build_corpus_a()]
        assert len(keys) == len(set(keys))

    def test_every_chunk_has_body_and_title(self):
        for c in indexer.build_corpus_a():
            assert c["body"].strip(), c["chunk_key"]
            assert c["source_title"].strip(), c["chunk_key"]

    def test_includes_all_nine_rules(self):
        keys = {c["chunk_key"] for c in indexer.build_corpus_a()}
        for rule in ("concentration", "sector_overlap", "volatility_mismatch", "fomo",
                     "cash_drain", "buy_during_rally", "panic_sell", "loss_lock_in",
                     "short_hold"):
            assert f"rule:{rule}" in keys, f"missing rule chunk for {rule}"

    def test_includes_indian_market_context(self):
        keys = {c["chunk_key"] for c in indexer.build_corpus_a()}
        assert "india:capital_gains" in keys
        assert "india:sebi" in keys
        assert "india:emergency_fund" in keys

    def test_includes_behavioural_finance(self):
        keys = {c["chunk_key"] for c in indexer.build_corpus_a()}
        assert "behaviour:loss_aversion" in keys
        assert "behaviour:disposition_effect" in keys

    def test_concepts_split_by_section(self):
        keys = {c["chunk_key"] for c in indexer.build_corpus_a()}
        assert "concept:panic_selling:section:0" in keys
        assert "concept:panic_selling:misconception" in keys

    def test_corpus_a_chunks_have_no_owner(self, corpus_a, db):
        rows = db.query(KnowledgeChunk).filter_by(corpus="A").all()
        assert rows
        assert all(r.owner_user_id is None for r in rows)


class TestIndexingIdempotency:
    def test_second_run_inserts_nothing(self, db):
        first = indexer.reindex_corpus_a(db, embed=False)
        second = indexer.reindex_corpus_a(db, embed=False)
        assert first["inserted"] > 0
        assert second["inserted"] == 0
        assert second["deleted"] == 0

    def test_chunk_keys_stable_across_runs(self, db):
        indexer.reindex_corpus_a(db, embed=False)
        before = {c.chunk_key for c in db.query(KnowledgeChunk).all()}
        indexer.reindex_corpus_a(db, embed=False)
        after = {c.chunk_key for c in db.query(KnowledgeChunk).all()}
        assert before == after

    def test_removed_source_is_deleted(self, db):
        indexer.reindex_corpus_a(db, embed=False)
        db.add(KnowledgeChunk(
            corpus="A", chunk_key="stale:orphan", source_title="Gone",
            body="content whose source no longer exists",
        ))
        db.commit()

        indexer.reindex_corpus_a(db, embed=False)
        assert db.query(KnowledgeChunk).filter_by(chunk_key="stale:orphan").first() is None

    def test_changed_body_clears_stale_embedding(self, db):
        indexer.reindex_corpus_a(db, embed=False)
        row = db.query(KnowledgeChunk).filter_by(corpus="A").first()
        row.embedding = [0.1, 0.2, 0.3]
        row.body = "something completely different from the source"
        db.commit()

        indexer.reindex_corpus_a(db, embed=False)
        db.refresh(row)
        # Body restored from source, and the vector that described the old body dropped.
        assert row.embedding is None


class TestCorpusB:
    def test_built_from_learner_records(self, db, user, seeded_stocks):
        portfolio_service.execute_buy(db, user, "TCS.NS", 3)
        chunks = indexer.build_corpus_b(db, user)
        keys = {c["chunk_key"] for c in chunks}
        assert f"user:{user.id}:profile" in keys
        assert f"user:{user.id}:holdings" in keys
        assert f"user:{user.id}:trade_summary" in keys

    def test_every_chunk_is_owner_tagged(self, db, user, seeded_stocks):
        indexer.refresh_corpus_b(db, user, embed=False)
        rows = db.query(KnowledgeChunk).filter_by(corpus="B").all()
        assert rows
        assert all(r.owner_user_id == user.id for r in rows)

    def test_excludes_pii(self, db, user, seeded_stocks):
        """Email and display name must never enter a prompt."""
        indexer.refresh_corpus_b(db, user, embed=False)
        bodies = " ".join(
            c.body for c in db.query(KnowledgeChunk).filter_by(corpus="B").all()
        )
        assert user.email not in bodies
        assert (user.display_name or "Learner") not in bodies

    def test_records_warning_outcomes_per_concept(self, db, user, seeded_stocks):
        for action in ("ignored", "ignored", "heeded"):
            db.add(InterventionLog(
                user_id=user.id, rule_id="panic_sell", severity="critical",
                title="t", message="m", concept="panic_selling",
                user_action=action, preview_id=None,
            ))
        db.commit()

        chunks = indexer.build_corpus_b(db, user)
        body = next(
            c["body"] for c in chunks
            if c["chunk_key"].endswith("warnings:panic_selling")
        )
        assert "fired 3 times" in body
        assert "heeded it 1" in body
        assert "traded\nthrough it 2" in body or "through it 2" in body

    def test_reflects_goal(self, db, user, seeded_stocks):
        db.add(Goal(user_id=user.id, template_key="college", label="College fund",
                    target_amount=200_000.0, horizon_months=60))
        db.commit()
        chunks = indexer.build_corpus_b(db, user)
        profile = next(c for c in chunks if c["chunk_key"].endswith(":profile"))
        assert "College fund" in profile["body"]
        assert "60 months" in profile["body"]

    def test_refresh_is_idempotent(self, db, user, seeded_stocks):
        indexer.refresh_corpus_b(db, user, embed=False)
        second = indexer.refresh_corpus_b(db, user, embed=False)
        assert second["inserted"] == 0
        assert second["deleted"] == 0

    def test_delete_removes_only_that_learner(self, db, user, seeded_stocks):
        other = User(email="other@example.test", cash=100_000.0)
        db.add(other)
        db.commit()
        indexer.refresh_corpus_b(db, user, embed=False)
        indexer.refresh_corpus_b(db, other, embed=False)

        removed = indexer.delete_corpus_b(db, user.id)
        assert removed > 0
        assert db.query(KnowledgeChunk).filter_by(owner_user_id=user.id).count() == 0
        assert db.query(KnowledgeChunk).filter_by(owner_user_id=other.id).count() > 0


class TestPerUserScoping:
    """The security boundary. These must never regress."""

    def test_corpus_b_never_crosses_users(self, db, user, seeded_stocks):
        other = User(email="other@example.test", cash=100_000.0, persona="woman")
        db.add(other)
        db.commit()

        portfolio_service.execute_buy(db, user, "TCS.NS", 3)
        portfolio_service.execute_buy(db, other, "INFY.NS", 5)
        indexer.refresh_corpus_b(db, user, embed=False)
        indexer.refresh_corpus_b(db, other, embed=False)

        result = retrieval.retrieve(db, "my holdings and trades", user_id=user.id, corpus="B")
        assert result.chunks
        for c in result.chunks:
            assert c.chunk_id.startswith(f"user:{user.id}:"), \
                f"leaked another learner's chunk: {c.chunk_id}"

    def test_every_returned_b_chunk_is_owned_by_requester(self, db, user, seeded_stocks):
        other = User(email="third@example.test", cash=100_000.0)
        db.add(other)
        db.commit()
        indexer.refresh_corpus_b(db, user, embed=False)
        indexer.refresh_corpus_b(db, other, embed=False)

        rows = {
            c.chunk_key: c.owner_user_id
            for c in db.query(KnowledgeChunk).filter_by(corpus="B").all()
        }
        result = retrieval.retrieve(db, "portfolio", user_id=user.id, corpus="both")
        for c in result.chunks:
            if c.corpus == "B":
                assert rows[c.chunk_id] == user.id

    def test_corpus_b_requires_a_user_id(self, db, user, seeded_stocks):
        indexer.refresh_corpus_b(db, user, embed=False)
        result = retrieval.retrieve(db, "holdings", user_id=None, corpus="B")
        assert result.is_empty

    def test_both_falls_back_to_corpus_a_without_a_user(self, db, user, corpus_a):
        indexer.refresh_corpus_b(db, user, embed=False)
        result = retrieval.retrieve(db, "diversification", user_id=None, corpus="both")
        assert all(c.corpus == "A" for c in result.chunks)

    def test_mislabelled_chunk_never_surfaces(self, db, user):
        """A Corpus B chunk with a mismatched owner must not be retrievable."""
        db.add(KnowledgeChunk(
            corpus="B", chunk_key="user:someone-else:secret",
            owner_user_id="someone-else",
            source_title="Leaky", body="another learner's private trade history",
        ))
        db.commit()

        result = retrieval.retrieve(db, "trade history", user_id=user.id, corpus="B")
        assert all("someone-else" not in c.chunk_id for c in result.chunks)

    def test_backstop_catches_a_loosened_query(self, db, user, monkeypatch, caplog):
        """The scoping query is the primary defence; this is the backstop.

        Simulates a future refactor accidentally widening ``_scope_candidates``.
        The post-filter must still discard the chunk and log it as a security
        event rather than passing it into a prompt.
        """
        leaked = KnowledgeChunk(
            corpus="B", chunk_key="user:someone-else:secret",
            owner_user_id="someone-else",
            source_title="Leaky", body="another learner's private trade history",
        )
        db.add(leaked)
        db.commit()

        monkeypatch.setattr(retrieval, "_scope_candidates", lambda *a, **k: [leaked])

        with caplog.at_level("ERROR"):
            result = retrieval.retrieve(db, "trade history", user_id=user.id, corpus="B")

        assert result.is_empty, "backstop failed to discard a cross-user chunk"
        assert any("SECURITY" in r.message for r in caplog.records)


class TestRanking:
    def test_lexical_ranker_used_without_a_key(self, db, corpus_a):
        result = retrieval.retrieve(db, "why is panic selling expensive")
        assert result.ranker == "lexical"

    def test_no_network_call_for_lexical_ranking(self, db, corpus_a, monkeypatch):
        """R11.9: ranking must work with zero network access."""
        def explode(*a, **k):
            raise AssertionError("lexical ranking must not touch the network")

        monkeypatch.setattr(ranking, "embed_texts", explode)
        result = retrieval.retrieve(db, "diversification across sectors")
        assert result.chunks

    def test_relevant_chunk_ranks_above_unrelated(self, db, corpus_a):
        result = retrieval.retrieve(db, "panic selling during a crash", top_k=12)
        titles = " ".join(c.source_title.lower() for c in result.chunks)
        assert "panic" in titles

    def test_capital_gains_question_finds_indian_material(self, db, corpus_a):
        result = retrieval.retrieve(db, "tax on selling shares within a year in India")
        keys = [c.chunk_id for c in result.chunks]
        assert any("capital_gains" in k for k in keys), keys

    def test_scores_are_normalised(self, db, corpus_a):
        result = retrieval.retrieve(db, "diversification")
        for c in result.chunks:
            assert 0.0 <= c.score <= 1.0

    def test_results_are_ordered_by_score(self, db, corpus_a):
        result = retrieval.retrieve(db, "risk and volatility", top_k=8)
        scores = [c.score for c in result.chunks]
        assert scores == sorted(scores, reverse=True)


class TestTopKAndFloor:
    def test_respects_top_k(self, db, corpus_a):
        assert len(retrieval.retrieve(db, "investing", top_k=3).chunks) <= 3

    def test_top_k_is_capped(self, db, corpus_a):
        result = retrieval.retrieve(db, "investing", top_k=999)
        assert len(result.chunks) <= retrieval.MAX_TOP_K

    def test_default_top_k(self, db, corpus_a):
        assert len(retrieval.retrieve(db, "investing").chunks) <= retrieval.DEFAULT_TOP_K

    def test_irrelevant_query_returns_nothing_usable(self, db, corpus_a):
        """Grounding: gibberish must not surface confident-looking evidence."""
        result = retrieval.retrieve(db, "zzzqqq wibble frobnicator xyzzy", floor=0.2)
        assert result.is_empty

    def test_floor_drops_are_counted(self, db, corpus_a):
        result = retrieval.retrieve(db, "diversification", floor=0.99)
        assert result.dropped_below_floor > 0
        assert result.is_empty

    def test_empty_corpus_returns_empty(self, db):
        result = retrieval.retrieve(db, "anything at all")
        assert result.is_empty
        assert result.candidates_considered == 0


class TestCitations:
    def test_citation_shape(self, db, corpus_a):
        result = retrieval.retrieve(db, "loss aversion")
        citation = result.chunks[0].citation()
        assert set(citation) == {"chunk_id", "corpus", "source_title", "source_reference"}

    def test_concept_chunks_link_to_their_page(self, db, corpus_a):
        result = retrieval.retrieve(db, "holding through a market crash", top_k=12)
        concept_chunks = [c for c in result.chunks if c.chunk_id.startswith("concept:")]
        assert concept_chunks
        assert any(c.source_reference and c.source_reference.startswith("/learn/")
                   for c in concept_chunks)

    def test_evidence_block_includes_chunk_ids(self, db, corpus_a):
        result = retrieval.retrieve(db, "diversification")
        evidence = result.as_evidence()
        for c in result.chunks:
            assert c.chunk_id in evidence


class TestCorpusStats:
    def test_reports_lexical_when_nothing_embedded(self, db, corpus_a):
        stats = indexer.corpus_stats(db)
        assert stats["corpus_a"] > 0
        assert stats["embedded"] == 0
        assert stats["ranking"] == "lexical"

    def test_counts_both_corpora(self, db, user, seeded_stocks, corpus_a):
        indexer.refresh_corpus_b(db, user, embed=False)
        stats = indexer.corpus_stats(db)
        assert stats["corpus_a"] > 0
        assert stats["corpus_b"] > 0
        assert stats["total_chunks"] == stats["corpus_a"] + stats["corpus_b"]
