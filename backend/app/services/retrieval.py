"""The single audited path to any knowledge chunk.

Every AI feature retrieves through ``retrieve()``. Nothing queries
``knowledge_chunks`` directly. That constraint is the whole security design:
DolFin has no authentication (``user_id`` arrives in a request body), so
single-point enforcement is the only defence available against one learner's
record reaching another learner's prompt.

Ordering matters and is deliberate: **scope first, then rank.** Ranking across
all chunks and filtering afterwards would apply top-K before the owner filter,
so another learner's chunks could crowd out relevant ones — silently degrading
retrieval quality and, in the worst case, producing a false "no grounded
material" answer with relevant evidence sitting unretrieved.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk
from app.services import ranking

log = logging.getLogger(__name__)

DEFAULT_TOP_K = 6
MAX_TOP_K = 12

# Minimum similarity for a chunk to count as usable evidence. Tuned for the
# lexical ranker, whose scores are lower than an embedding model's; both rankers
# normalise into [0, 1] so one floor serves both.
RELEVANCE_FLOOR = 0.05

CorpusSelector = Literal["A", "B", "both"]

# Short-lived cache so repeated identical retrievals on one page load do not
# re-rank. Keyed on query + user + corpus.
_CACHE_TTL_SECONDS = 60
_cache: dict[tuple, tuple[float, list]] = {}


@dataclass
class RetrievedChunk:
    """A chunk plus the score that selected it."""

    chunk_id: str
    corpus: str
    source_title: str
    source_reference: str | None
    body: str
    score: float

    def citation(self) -> dict:
        """Machine-readable citation for an AI response."""
        return {
            "chunk_id": self.chunk_id,
            "corpus": self.corpus,
            "source_title": self.source_title,
            "source_reference": self.source_reference,
        }


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    ranker: str = "none"
    candidates_considered: int = 0
    dropped_below_floor: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.chunks

    @property
    def top_score(self) -> float:
        return self.chunks[0].score if self.chunks else 0.0

    def as_evidence(self) -> str:
        """Render retrieved chunks as a prompt section body."""
        return "\n\n".join(
            f"[{c.chunk_id}] {c.source_title}\n{c.body}" for c in self.chunks
        )

    def citations(self) -> list[dict]:
        return [c.citation() for c in self.chunks]


def reset_cache() -> None:
    _cache.clear()


def _scope_candidates(
    db: Session, user_id: str | None, corpus: CorpusSelector
) -> list[KnowledgeChunk]:
    """Build the candidate set BEFORE any ranking happens.

    This is the enforcement point. A Corpus B chunk can only enter the candidate
    set if its owner matches the requesting learner.
    """
    query = db.query(KnowledgeChunk)

    if corpus == "A":
        query = query.filter(KnowledgeChunk.corpus == "A")
    elif corpus == "B":
        if not user_id:
            return []
        query = query.filter(
            KnowledgeChunk.corpus == "B",
            KnowledgeChunk.owner_user_id == user_id,
        )
    else:  # both
        if user_id:
            query = query.filter(
                or_(
                    KnowledgeChunk.corpus == "A",
                    (KnowledgeChunk.corpus == "B")
                    & (KnowledgeChunk.owner_user_id == user_id),
                )
            )
        else:
            query = query.filter(KnowledgeChunk.corpus == "A")

    return query.all()


def retrieve(
    db: Session,
    query: str,
    *,
    user_id: str | None = None,
    corpus: CorpusSelector = "both",
    top_k: int = DEFAULT_TOP_K,
    floor: float = RELEVANCE_FLOOR,
) -> RetrievalResult:
    """Scope, rank, apply the floor, return at most ``top_k`` chunks."""
    top_k = max(1, min(top_k, MAX_TOP_K))

    cache_key = (query.strip().lower(), user_id, corpus, top_k, floor)
    hit = _cache.get(cache_key)
    if hit and hit[0] > time.time():
        return hit[1]

    # 1. SCOPE — access control, before anything is ranked.
    candidates = _scope_candidates(db, user_id, corpus)

    # Defence in depth: even though the query filtered by owner, verify it. A
    # future refactor that loosens the filter should fail loudly here.
    safe: list[KnowledgeChunk] = []
    for chunk in candidates:
        if chunk.corpus == "B" and chunk.owner_user_id != user_id:
            log.error(
                "SECURITY: cross-user chunk reached the candidate set and was "
                "discarded. chunk=%s owner=%s requester=%s",
                chunk.chunk_key, chunk.owner_user_id, user_id,
            )
            continue
        safe.append(chunk)

    if not safe:
        result = RetrievalResult(candidates_considered=0)
        _cache[cache_key] = (time.time() + _CACHE_TTL_SECONDS, result)
        return result

    # 2. RANK
    ranker = ranking.select_ranker(safe)
    scored = ranker.rank(query, safe)

    # 3. FLOOR, then truncate to top_k
    above = [s for s in scored if s.score >= floor]
    dropped = len(scored) - len(above)
    selected = above[:top_k]

    result = RetrievalResult(
        chunks=[
            RetrievedChunk(
                chunk_id=s.chunk.chunk_key,
                corpus=s.chunk.corpus,
                source_title=s.chunk.source_title,
                source_reference=s.chunk.source_reference,
                body=s.chunk.body,
                score=round(s.score, 4),
            )
            for s in selected
        ],
        ranker=ranker.name,
        candidates_considered=len(safe),
        dropped_below_floor=dropped,
    )

    _audit(query, user_id, corpus, ranker.name, len(safe), result)

    _cache[cache_key] = (time.time() + _CACHE_TTL_SECONDS, result)
    return result


def _audit(
    query: str,
    user_id: str | None,
    corpus: str,
    ranker_name: str,
    candidates: int,
    result: RetrievalResult,
) -> None:
    """Record what was retrieved, for whom, and how well it scored.

    The chunk ids and scores are the point (R11.10). Logging only a count tells
    you retrieval ran; logging what came back is what lets you answer "why did
    the chatbot say that?" after the fact, and lets a reviewer verify the
    per-user scoping actually held on real traffic rather than only in tests.

    Kept at INFO for Corpus B reads and DEBUG otherwise: Corpus B is the
    per-user data, so its access record is the one worth having by default.
    """
    selected = " ".join(f"{c.chunk_id}@{c.score:.4f}" for c in result.chunks) or "(none)"
    touched_b = any(c.corpus == "B" for c in result.chunks)
    message = (
        "retrieval user=%s corpus=%s ranker=%s candidates=%d returned=%d "
        "dropped_below_floor=%d query=%r chunks=[%s]"
    )
    args = (
        user_id, corpus, ranker_name, candidates, len(result.chunks),
        result.dropped_below_floor, query[:120], selected,
    )
    if touched_b:
        log.info(message, *args)
    else:
        log.debug(message, *args)
