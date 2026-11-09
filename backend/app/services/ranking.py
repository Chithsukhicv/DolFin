"""Similarity ranking for retrieval, with two interchangeable strategies.

Why two: the platform must work with no API key (R12) and retrieval must be able
to rank with no network call at all (R11.9). But real embeddings give much better
semantic matching when a key is present. So ranking is pluggable.

Why not sentence-transformers for the local path: it pulls in torch, roughly
800MB installed. That does not fit Vercel's 250MB serverless limit and fights
Render's 512MB free tier. A compact pure-Python TF-IDF costs a few KB, has zero
dependencies, and is entirely adequate for a corpus of a couple of thousand
chunks.

Selection is automatic:
  embeddings configured AND chunks have vectors  -> EmbeddingRanker (semantic)
  otherwise                                      -> LexicalRanker  (offline)
"""

from __future__ import annotations
from functools import lru_cache

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass

from app.config import get_settings

log = logging.getLogger(__name__)

# Words carrying no discriminating signal in a finance corpus.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "to", "of",
    "in", "on", "at", "for", "with", "by", "from", "as", "and", "or", "but", "if",
    "then", "than", "that", "this", "these", "those", "it", "its", "you", "your",
    "i", "my", "me", "we", "our", "they", "their", "he", "she", "his", "her",
    "do", "does", "did", "done", "have", "has", "had", "will", "would", "should",
    "could", "can", "may", "might", "must", "not", "no", "so", "up", "out", "about",
    "what", "which", "who", "how", "when", "where", "why", "all", "any", "some",
    "more", "most", "other", "into", "over", "also", "just", "only", "very",
}

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenise(text: str) -> list[str]:
    """Lowercase word tokens with stopwords removed."""
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


def document_text(chunk: object) -> str:
    """The text a chunk is ranked and embedded against: title, then body.

    The title carries vocabulary the body often does not. A Corpus B chunk titled
    "Your current holdings" has a body reading "This learner currently holds 3
    units of TCS.NS...", so ranking on the body alone misses the obvious question
    "how are my holdings doing". Both ranking strategies use this, so a chunk's
    lexical and semantic representations stay in step.
    """
    title = getattr(chunk, "source_title", "") or ""
    body = getattr(chunk, "body", "") or ""
    return f"{title}\n{body}" if title else body


@dataclass
class Scored:
    """A candidate with its similarity score, in [0, 1]."""

    chunk: object
    score: float



# ---------------------------------------------------------------------------
# Lexical (offline) ranking
# ---------------------------------------------------------------------------

def _tf_idf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """L2-normalised TF-IDF vector as a sparse dict."""
    if not tokens:
        return {}

    counts = Counter(tokens)
    longest = max(counts.values())

    vec = {
        term: (0.5 + 0.5 * (n / longest)) * idf.get(term, 0.0)
        for term, n in counts.items()
    }

    norm = math.sqrt(sum(v * v for v in vec.values()))

    if norm == 0:
        return {}

    return {t: v / norm for t, v in vec.items()}


def _sparse_cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Both vectors are already L2-normalised."""
    if not a or not b:
        return 0.0

    if len(a) > len(b):
        a, b = b, a

    return sum(weight * b.get(term, 0.0) for term, weight in a.items())


@lru_cache(maxsize=4)
def _prepare_lexical_index(
    documents: tuple[str, ...],
) -> tuple[dict[str, float], tuple[dict[str, float], ...]]:
    """Build and cache the TF-IDF index for an exact corpus snapshot."""

    docs = [tokenise(text) for text in documents]
    n = len(docs)

    doc_freq: Counter[str] = Counter()

    for tokens in docs:
        doc_freq.update(set(tokens))

    # Smoothed IDF. The +1 floor preserves universal terms.
    idf = {
        term: math.log((n + 1) / (df + 1)) + 1.0
        for term, df in doc_freq.items()
    }

    vectors = tuple(
        _tf_idf_vector(tokens, idf)
        for tokens in docs
    )

    return idf, vectors


class LexicalRanker:
    """Cached TF-IDF cosine ranking with no external dependencies."""

    name = "lexical"

    def rank(self, query: str, candidates: list) -> list[Scored]:
        if not candidates:
            return []

        # Exact document content makes cache invalidation automatic.
        documents = tuple(
            document_text(chunk)
            for chunk in candidates
        )

        # Reuse the corpus index when its contents have not changed.
        idf, document_vectors = _prepare_lexical_index(documents)

        # Query vector changes for every search.
        q_vec = _tf_idf_vector(tokenise(query), idf)

        out = [
            Scored(
                chunk=chunk,
                score=_sparse_cosine(q_vec, vector),
            )
            for chunk, vector in zip(candidates, document_vectors)
        ]

        out.sort(key=lambda item: item.score, reverse=True)

        return out


# ---------------------------------------------------------------------------
# Embedding (semantic) ranking
# ---------------------------------------------------------------------------
def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Embed a batch via the provider. Returns None when unavailable.

    This is the second network seam in the codebase (the first is
    ``llm_gateway._call_model``). Tests monkeypatch it, so indexing and retrieval
    stay offline and deterministic.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        vectors: list[list[float]] = []
        for text in texts:
            result = genai.embed_content(
                model=settings.gemini_embedding_model,
                content=text,
                task_type="retrieval_document",
            )
            vectors.append(list(result["embedding"]))
        return vectors
    except Exception as e:
        log.warning("Embedding call failed, falling back to lexical ranking: %s", e)
        return None


def _dense_cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    # Map cosine from [-1, 1] into [0, 1] so scores compare with the lexical
    # ranker's range and one relevance floor works for both.
    return max(0.0, min((dot / (na * nb) + 1.0) / 2.0, 1.0))


class EmbeddingRanker:
    """Cosine similarity over stored vectors."""

    name = "embedding"

    def rank(self, query: str, candidates: list) -> list[Scored]:
        if not candidates:
            return []
        vectors = embed_texts([query])
        if not vectors:
            # Provider went away mid-session; degrade rather than fail.
            return LexicalRanker().rank(query, candidates)

        q = vectors[0]
        out = [
            Scored(chunk=c, score=_dense_cosine(q, getattr(c, "embedding", None) or []))
            for c in candidates
        ]
        out.sort(key=lambda s: s.score, reverse=True)
        return out


def select_ranker(candidates: list) -> LexicalRanker | EmbeddingRanker:
    """Pick the best strategy available for this candidate set."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return LexicalRanker()
    if not any(getattr(c, "embedding", None) for c in candidates):
        # Nothing has been embedded yet; lexical is the only usable option.
        return LexicalRanker()
    return EmbeddingRanker()
