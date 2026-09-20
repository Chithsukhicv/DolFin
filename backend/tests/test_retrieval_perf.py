"""Retrieval latency and scoping at realistic corpus size.

R11.11 puts a 300ms budget on a retrieval across Corpus A plus one learner's
Corpus B at 2000 chunks. That number matters because the chatbot and the
reflection analyzer both sit on interactive paths: retrieval happens *before* the
model call, so it is pure added latency on a page a learner is waiting on.

The lexical ranker is the one under test. It recomputes IDF over the candidate
set on every call, which is the deliberate trade-off that lets a freshly indexed
chunk be searchable immediately — so it is worth proving that choice does not
cost too much at scale.

Timing assertions are loose on purpose. A tight bound would fail on a loaded CI
machine and teach nothing; the point is to catch an accidental quadratic, not to
benchmark the host.
"""

from __future__ import annotations

import time

import pytest

from app.models import KnowledgeChunk
from app.services import ranking, retrieval

# R11.11's stated corpus size.
CORPUS_SIZE = 2000
BUDGET_SECONDS = 0.300

# Vocabulary that produces realistic token overlap. Random strings would make
# every TF-IDF vector nearly orthogonal and the sparse dot products unrealistically
# cheap, which would make the measurement meaningless.
_WORDS = (
    "diversification concentration portfolio sector volatility risk appetite "
    "panic selling crash correction rally dip recovery holding period capital "
    "gains tax demat sebi nifty sensex index fund etf compounding horizon goal "
    "emergency buffer cash allocation loss aversion disposition recency herding "
    "brokerage realised unrealised equity market price quote trade buy sell"
).split()


@pytest.fixture(autouse=True)
def clear_cache():
    retrieval.reset_cache()
    yield
    retrieval.reset_cache()


def _body(seed: int, length: int = 40) -> str:
    """Deterministic pseudo-document built from the shared vocabulary."""
    return " ".join(_WORDS[(seed * 7 + i * 13) % len(_WORDS)] for i in range(length))


@pytest.fixture
def large_corpus(db, user):
    """2000 chunks: mostly Corpus A, with one learner's Corpus B mixed in.

    A second learner's chunks are included so the scoping filter has something
    real to exclude — a candidate set that is already correct proves nothing
    about the filter.
    """
    from app.models import User

    other = User(email="other-perf@example.test")
    db.add(other)
    db.commit()

    rows = []
    for i in range(CORPUS_SIZE - 60):
        rows.append(KnowledgeChunk(
            corpus="A",
            chunk_key=f"perf:a:{i}",
            source_title=f"Curated chunk {i}",
            body=_body(i),
        ))
    # Titles mirror the shape real Corpus B chunks have — distinct subjects, all
    # prefixed "Your" — because the prefix being shared across every chunk is
    # exactly the condition that used to zero out the IDF.
    subjects = (
        "holdings", "trading activity", "recent trades", "warning record",
        "quiz results", "reflections", "portfolio value", "profile and goal",
        "scenario", "heed rate",
    )
    for i in range(30):
        rows.append(KnowledgeChunk(
            corpus="B",
            chunk_key=f"perf:b:mine:{i}",
            owner_user_id=user.id,
            source_title=f"Your {subjects[i % len(subjects)]}",
            body=_body(i + 500),
        ))
    for i in range(30):
        rows.append(KnowledgeChunk(
            corpus="B",
            chunk_key=f"perf:b:theirs:{i}",
            owner_user_id=other.id,
            source_title=f"Your {subjects[i % len(subjects)]}",
            body=_body(i + 900),
        ))

    db.add_all(rows)
    db.commit()
    return {"user": user, "other": other, "total": len(rows)}


def _warm(db, user_id: str) -> None:
    """Pay the one-off costs before timing anything.

    The first retrieval in a process absorbs module import, settings load and
    SQLAlchemy statement compilation — measured at over a second on a cold pytest
    session, against a steady state of well under a hundred milliseconds. R11.11
    is about latency on a running server, where those costs were paid long ago,
    so attributing them to retrieval would make the test assert the wrong thing.
    """
    retrieval.retrieve(db, "warm up the retrieval path", user_id=user_id, corpus="both")
    retrieval.reset_cache()


class TestCorpusSize:
    def test_the_fixture_really_holds_two_thousand_chunks(self, db, large_corpus):
        assert db.query(KnowledgeChunk).count() == CORPUS_SIZE


class TestLatency:
    def test_retrieval_across_both_corpora_meets_the_budget(self, db, user, large_corpus):
        _warm(db, user.id)
        start = time.perf_counter()
        result = retrieval.retrieve(
            db, "why did my portfolio drop during the crash",
            user_id=user.id, corpus="both", top_k=6,
        )
        elapsed = time.perf_counter() - start

        assert result.chunks, "retrieval returned nothing, so the timing is meaningless"
        assert elapsed < BUDGET_SECONDS, f"took {elapsed * 1000:.0f}ms over {CORPUS_SIZE} chunks"

    def test_corpus_a_only_meets_the_budget(self, db, user, large_corpus):
        _warm(db, user.id)
        start = time.perf_counter()
        retrieval.retrieve(db, "capital gains tax on equity", user_id=user.id, corpus="A")
        elapsed = time.perf_counter() - start
        assert elapsed < BUDGET_SECONDS, f"took {elapsed * 1000:.0f}ms"

    def test_a_repeat_query_is_served_from_cache(self, db, user, large_corpus):
        """R11.7. The second identical retrieval should be effectively free."""
        query = "diversification across sectors"
        retrieval.retrieve(db, query, user_id=user.id, corpus="both")

        start = time.perf_counter()
        retrieval.retrieve(db, query, user_id=user.id, corpus="both")
        cached_elapsed = time.perf_counter() - start

        assert cached_elapsed < 0.010, f"cache hit took {cached_elapsed * 1000:.1f}ms"

    def test_ranking_is_not_quadratic_in_corpus_size(self, db, user, large_corpus):
        """Guards the shape of the cost, not its absolute value.

        Doubling the candidate set should roughly double the work. Anything
        dramatically worse means a per-candidate loop crept in that walks the
        whole set — the failure mode that would only show up in production.
        """
        candidates = db.query(KnowledgeChunk).filter_by(corpus="A").all()
        ranker = ranking.LexicalRanker()
        half = candidates[: len(candidates) // 2]

        start = time.perf_counter()
        ranker.rank("portfolio risk and diversification", half)
        half_time = time.perf_counter() - start

        start = time.perf_counter()
        ranker.rank("portfolio risk and diversification", candidates)
        full_time = time.perf_counter() - start

        # Linear would be ~2x. Allow 4x for timer noise on small absolute numbers.
        assert full_time < half_time * 4 + 0.05, (
            f"half={half_time * 1000:.1f}ms full={full_time * 1000:.1f}ms"
        )


class TestUniversalTerms:
    """A term present in every candidate must still carry weight.

    IDF used to be floored at zero, so when a term's document frequency equalled
    the candidate count its weight collapsed to ~0 and any query built only from
    such terms scored zero everywhere — every result then fell below the relevance
    floor and the feature reported "no material" with relevant chunks sitting
    unretrieved.

    Corpus B is where this bites, because it is small (around a dozen chunks per
    learner) and formulaic: every body opens "This learner ...", so shared
    vocabulary is the norm rather than the exception.
    """

    def test_a_term_in_every_document_still_carries_weight(self):
        chunks = [
            _Chunk("Your holdings", "This learner holds three units of TCS."),
            _Chunk("Your trades", "This learner has placed four trades."),
            _Chunk("Your quizzes", "This learner passed two quizzes."),
        ]
        # "learner" is in all three bodies, so df == n. "your" would not work as
        # a probe here: it is a stopword and never reaches the vector at all.
        scored = ranking.LexicalRanker().rank("learner", chunks)
        assert scored[0].score > 0.0, "a term in every document scored exactly zero"

    def test_idf_is_never_negative_or_zero(self):
        chunks = [_Chunk("T", "alpha beta"), _Chunk("T", "alpha gamma")]
        scored = ranking.LexicalRanker().rank("alpha", chunks)
        assert all(s.score > 0 for s in scored)

    def test_a_distinctive_term_still_outranks_a_universal_one(self):
        """The fix must not flatten ranking — rarer terms should still win."""
        chunks = [
            _Chunk("Your holdings", "This learner holds three units of TCS."),
            _Chunk("Your quizzes", "This learner passed two quizzes."),
        ]
        by_rare = ranking.LexicalRanker().rank("quizzes", chunks)
        assert by_rare[0].chunk.source_title == "Your quizzes"

    def test_a_shared_prefix_query_reaches_corpus_b(self, db, user, large_corpus):
        """The end-to-end version of the same bug, through the retriever."""
        result = retrieval.retrieve(
            db, "your record", user_id=user.id, corpus="B", top_k=12
        )
        assert result.chunks, "Corpus B returned nothing for a query about the learner"


class _Chunk:
    """Minimal stand-in for a KnowledgeChunk — the ranker only reads two fields."""

    def __init__(self, source_title: str, body: str) -> None:
        self.source_title = source_title
        self.body = body
        self.embedding = None


class TestScopingAtScale:
    def test_no_other_learners_chunk_is_ever_returned(self, db, user, large_corpus):
        """R18.9, at a size where an off-by-one filter would actually surface."""
        other_id = large_corpus["other"].id
        for query in (
            "your record",
            "their record",
            "portfolio risk diversification",
            "panic selling crash recovery",
        ):
            result = retrieval.retrieve(
                db, query, user_id=user.id, corpus="both", top_k=12
            )
            for chunk in result.chunks:
                assert not (chunk.corpus == "B" and chunk.chunk_id.startswith("perf:b:theirs")), (
                    f"leaked {chunk.chunk_id} on query {query!r}"
                )
            owners = {c.chunk_id for c in result.chunks if c.corpus == "B"}
            assert all(o.startswith("perf:b:mine") for o in owners)
            assert other_id not in {c.chunk_id for c in result.chunks}

    def test_corpus_b_alone_returns_only_this_learner(self, db, user, large_corpus):
        result = retrieval.retrieve(
            db, "your holdings and recent trades", user_id=user.id, corpus="B", top_k=12
        )
        assert result.chunks
        assert all(c.chunk_id.startswith("perf:b:mine") for c in result.chunks)

    def test_top_k_is_capped_even_when_asked_for_more(self, db, user, large_corpus):
        """R11.4: a caller cannot widen the prompt past MAX_TOP_K."""
        result = retrieval.retrieve(
            db, "portfolio", user_id=user.id, corpus="both", top_k=500
        )
        assert len(result.chunks) <= retrieval.MAX_TOP_K

    def test_results_are_ordered_by_descending_score(self, db, user, large_corpus):
        """R11.3."""
        result = retrieval.retrieve(
            db, "capital gains tax equity holding period",
            user_id=user.id, corpus="both", top_k=12,
        )
        scores = [c.score for c in result.chunks]
        assert scores == sorted(scores, reverse=True)

    def test_every_result_is_above_the_floor(self, db, user, large_corpus):
        """R11.5."""
        result = retrieval.retrieve(
            db, "diversification", user_id=user.id, corpus="both", top_k=12
        )
        assert all(c.score >= retrieval.RELEVANCE_FLOOR for c in result.chunks)
