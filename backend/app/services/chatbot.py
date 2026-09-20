"""The grounded chatbot.

A general-purpose model asked "why did DolFin warn me about that trade?" will
invent a plausible answer, because it has never seen DolFin's rules or this
learner's record. That is the failure this module exists to prevent: every answer
is assembled from material that was retrieved first, and the citations travel
with the answer so any claim can be traced back to the chunk it came from.

Three grounding sources, in order of how hard they are to fake:

- **Corpus A** — DolFin's own concept articles, glossary, quiz explanations and
  the nine rule definitions. This is what makes "why were you warned" answerable
  from the actual threshold rather than a guess.
- **Corpus B** — this learner's trades, warning outcomes, quizzes and
  reflections. Exists in no model's training data, which is precisely why it
  produces answers no general chatbot can.
- **Live market data** — fetched at question time for price questions, and cited
  with its retrieval timestamp so a stale number is visibly stale.

When retrieval finds nothing above the relevance floor, the honest answer is "I
don't have material on that" plus what DolFin *does* cover. No model call is made
in that case: generating from nothing is how a grounded system quietly stops
being grounded.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, Stock, User
from app.services import llm_gateway, retrieval
from app.services.llm_gateway import PromptSection

log = logging.getLogger(__name__)

# R7.7 — the preceding turns kept as context. Six is three exchanges, enough for
# "why?" to refer back to the previous answer without the prompt growing without
# bound.
CONTEXT_MESSAGES = 6

MAX_QUESTION_CHARS = 500
CORPUS_A_TOP_K = 5
CORPUS_B_TOP_K = 4

# Words that mean the question is about the learner rather than about finance in
# general. Their presence widens retrieval into Corpus B (R7.3).
_PERSONAL_CUES = re.compile(
    r"\b(my|mine|i|i'm|i've|me|we|our|myself)\b", re.I
)
_PERSONAL_TOPICS = re.compile(
    r"\b(portfolio|holding|holdings|trade|trades|traded|warning|warnings|score|"
    r"readiness|reflection|quiz|quizzes|loss|profit|p&l|pnl|goal|cash|sold|bought)\b",
    re.I,
)

# Words that mean the answer needs a live number rather than an explanation.
_PRICE_CUES = re.compile(
    r"\b(price|quote|trading at|worth|value|cost|how much|current|today|"
    r"up or down|gained|dropped|fell|rose)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Question classification
# ---------------------------------------------------------------------------
def is_personal(question: str) -> bool:
    """True when the question is about this learner's own record."""
    return bool(_PERSONAL_CUES.search(question) and _PERSONAL_TOPICS.search(question))


def find_symbols(db: Session, question: str) -> list[str]:
    """Catalogue symbols named in the question.

    Matched against the catalogue rather than by pattern, so "IT sector" does not
    become a ticker and a company's common name ("Reliance") resolves as well as
    its symbol ("RELIANCE.NS").
    """
    words = set(re.findall(r"[A-Za-z&]+", question.lower()))
    if not words:
        return []

    found: list[str] = []
    for stock in db.query(Stock).all():
        base = stock.symbol.split(".")[0].lower()
        first = stock.name.split()[0].lower()
        if base in words or (len(first) > 3 and first in words):
            found.append(stock.symbol)
    return found[:3]


def _market_context(symbols: list[str]) -> tuple[str, list[dict]]:
    """Live quotes for the named symbols, plus citations carrying the timestamp.

    R7.4 requires the retrieval timestamp to be cited. A price with no timestamp
    is the kind of claim that looks authoritative and ages badly.
    """
    from app.services import market as market_service

    lines: list[str] = []
    citations: list[dict] = []

    for symbol in symbols:
        try:
            quote = market_service.get_quote(symbol)
        except Exception as e:
            log.debug("Chatbot could not fetch %s: %s", symbol, e)
            continue

        fetched = datetime.fromtimestamp(quote.fetched_at, tz=timezone.utc)
        lines.append(
            f"- {quote.symbol}: Rs {quote.price:,.2f} "
            f"(previous close Rs {(quote.previous_close or quote.price):,.2f}, "
            f"day change {quote.day_change_pct or 0:+.2f}%), "
            f"retrieved {fetched.strftime('%d %b %Y %H:%M UTC')}"
        )
        citations.append({
            "chunk_id": f"market:{quote.symbol}",
            "corpus": "market",
            "source_title": f"Live quote for {quote.symbol}",
            "source_reference": f"/market?symbol={quote.symbol}",
            "retrieved_at": fetched.isoformat(),
        })

    return "\n".join(lines), citations


# ---------------------------------------------------------------------------
# Session handling
# ---------------------------------------------------------------------------
def get_or_create_session(
    db: Session, user: User, session_id: str | None
) -> ChatSession:
    """Fetch the learner's session or start a new one.

    A session id belonging to another learner is treated as absent rather than
    as an error: silently starting a fresh session is safer than confirming that
    someone else's session exists.
    """
    if session_id:
        row = db.get(ChatSession, session_id)
        if row is not None and row.user_id == user.id:
            return row
        if row is not None:
            log.error(
                "SECURITY: chat session %s requested by non-owner %s; ignored.",
                session_id, user.id,
            )

    row = ChatSession(user_id=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _history(db: Session, session: ChatSession) -> list[ChatMessage]:
    """The last ``CONTEXT_MESSAGES`` turns, oldest first."""
    rows = (
        db.query(ChatMessage)
        .filter_by(session_id=session.id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(CONTEXT_MESSAGES)
        .all()
    )
    return list(reversed(rows))


def _history_text(messages: list[ChatMessage]) -> str:
    return "\n".join(
        f"{'Learner' if m.role == 'user' else 'DolFin'}: {m.content[:400]}"
        for m in messages
    )


def _persist(
    db: Session,
    session: ChatSession,
    question: str,
    answer: str,
    citations: list[dict],
    mode: str,
) -> ChatMessage:
    db.add(ChatMessage(session_id=session.id, role="user", content=question))
    reply = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        citations=citations,
        mode=mode,
    )
    db.add(reply)
    if not session.title:
        session.title = question[:80]
    db.commit()
    db.refresh(reply)
    return reply


# ---------------------------------------------------------------------------
# Ungrounded and offline answers
# ---------------------------------------------------------------------------
def available_topics(db: Session, limit: int = 3) -> list[str]:
    """A few things DolFin does cover, for the "no material" answer (R7.5).

    Read from the index rather than the seed list, so the suggestions are things
    retrieval can actually ground an answer in.
    """
    from app.models import KnowledgeChunk

    rows = (
        db.query(KnowledgeChunk.source_title)
        .filter(
            KnowledgeChunk.corpus == "A",
            KnowledgeChunk.chunk_key.like("concept:%:takeaways"),
        )
        .limit(limit)
        .all()
    )
    titles = [t.replace(" — key points", "") for (t,) in rows]
    if titles:
        return titles

    from app.data.concepts_seed import CONCEPTS

    return [c["title"] for c in CONCEPTS[:limit]]


_NO_MATERIAL = {
    "en": (
        "I don't have material on that in DolFin's library, so I'd rather say so "
        "than guess. I can only answer from what the platform actually teaches and "
        "from your own record. Here's what I do cover: {topics}."
    ),
    "hi": (
        "Is sawaal ke liye DolFin ki library mein material nahi hai, to main "
        "andaaza nahi lagaunga. Main sirf platform ke content aur aapke record se "
        "jawab de sakta hoon. Jo topics available hain: {topics}."
    ),
}

_OFFLINE_PREFIX = {
    "en": (
        "Generated answers aren't available right now, but DolFin's library covers "
        "your question. Here's what to read:"
    ),
    "hi": (
        "Abhi generated jawab available nahi hai, lekin DolFin ki library mein "
        "aapke sawaal ka jawab hai. Yeh padhiye:"
    ),
}


def _reading_list(result: retrieval.RetrievalResult, language: str) -> str:
    """R7.9: no model, but retrieval worked — hand over the sources directly."""
    lines = [_OFFLINE_PREFIX.get(language, _OFFLINE_PREFIX["en"])]
    for chunk in result.chunks[:3]:
        snippet = chunk.body.strip().replace("\n", " ")
        if len(snippet) > 240:
            snippet = snippet[:240].rsplit(" ", 1)[0] + "..."
        lines.append(f"\n- {chunk.source_title}: {snippet}")
    return "".join(lines) if len(lines) > 1 else lines[0]


_TASK = """\
Answer the learner's question using ONLY the retrieved material, the live market
data, and the conversation so far. Everything you assert must be traceable to
something supplied above.

Rules:
- If the material does not answer the question, say that plainly instead of
  filling the gap from general knowledge.
- Reference the material naturally ("DolFin's diversification page puts it this
  way..."). Do not print the bracketed chunk identifiers.
- When the material includes the learner's own record, use it — a specific answer
  about their own trades is worth more than a general explanation.
- Quote any price only as of the retrieval time given, and say so.
- Keep it under 180 words. Plain language, no jargon without a one-line gloss.
- Explain principles. Never tell them to buy or sell a specific security."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def ask(
    db: Session,
    user: User,
    question: str,
    *,
    session_id: str | None = None,
) -> dict:
    """Answer one question. Never raises."""
    try:
        return _ask(db, user, question, session_id=session_id)
    except Exception as e:
        log.warning("Chatbot failed for %s: %s", user.id, e)
        return {
            "session_id": session_id,
            "answer": (
                "Something went wrong answering that. Please try again in a moment."
            ),
            "citations": [],
            "mode": "offline",
            "grounded": False,
            "status": "error",
        }


def _ask(db: Session, user: User, question: str, *, session_id: str | None) -> dict:
    # Stored exactly as submitted (R16.9). Truncation for the prompt happens in
    # the gateway, on its own copy — a learner reading their transcript back
    # should see what they typed, not what the model was shown.
    question = (question or "").strip()
    if len(question) < 3:
        return {
            "session_id": session_id,
            "answer": "Ask me something about investing, or about your own record.",
            "citations": [],
            "mode": "skipped",
            "grounded": False,
            "status": "empty_question",
        }

    session = get_or_create_session(db, user, session_id)
    language = user.language if user.language in ("en", "hi") else "en"

    # Bounded copy for everything downstream of storage. The learner identifier
    # used for scoping is taken from the request, never from this text (R16.8) —
    # the question only ever becomes a ranking query.
    probe = question[:MAX_QUESTION_CHARS]

    # R7.1 — always retrieve from both corpora before generating. Two separate
    # calls rather than one "both" call, so a strong Corpus A hit cannot crowd
    # the learner's own record out of the top-K entirely.
    corpus_a = retrieval.retrieve(
        db, probe, user_id=user.id, corpus="A", top_k=CORPUS_A_TOP_K
    )
    corpus_b = retrieval.retrieve(
        db, probe, user_id=user.id, corpus="B", top_k=CORPUS_B_TOP_K
    )

    symbols = find_symbols(db, probe) if _PRICE_CUES.search(probe) else []
    market_text, market_citations = _market_context(symbols) if symbols else ("", [])

    top_score = max(corpus_a.top_score, corpus_b.top_score)
    grounded = bool(corpus_a.chunks or corpus_b.chunks)

    # R7.5 — nothing above the floor. Say so, list what exists, make no model call.
    # Live market data on its own counts as grounding, so a bare price question
    # still gets answered.
    if not grounded and not market_citations:
        topics = ", ".join(available_topics(db))
        answer = _NO_MATERIAL.get(language, _NO_MATERIAL["en"]).format(topics=topics)
        reply = _persist(db, session, question, answer, [], "grounding_failed")
        return {
            "session_id": session.id,
            "message_id": reply.id,
            "answer": answer,
            "citations": [],
            "mode": "grounding_failed",
            "grounded": False,
            "status": "no_material",
            "available_topics": available_topics(db),
            "top_score": round(top_score, 4),
        }

    citations = corpus_a.citations() + corpus_b.citations() + market_citations
    history = _history(db, session)

    # R7.9 — retrieval worked but no model. The sources are the answer.
    if not llm_gateway.is_available():
        answer = _reading_list(corpus_a if corpus_a.chunks else corpus_b, language)
        if market_text:
            answer += f"\n\nLive data:\n{market_text}"
        reply = _persist(db, session, question, answer, citations, "offline")
        return {
            "session_id": session.id,
            "message_id": reply.id,
            "answer": answer,
            "citations": citations,
            "mode": "offline",
            "grounded": True,
            "status": "ok",
            "top_score": round(top_score, 4),
        }

    sections: list[PromptSection] = []
    if history:
        sections.append(
            PromptSection("Conversation so far", _history_text(history))
        )
    sections.append(
        PromptSection(
            "DolFin's teaching material",
            corpus_a.as_evidence() or "(nothing retrieved)",
        )
    )
    sections.append(
        PromptSection(
            "This learner's own record",
            corpus_b.as_evidence() or "(nothing retrieved about this learner)",
        )
    )
    if market_text:
        sections.append(PromptSection("Live market data", market_text))
    # The question goes in as untrusted: it is free text a learner typed, so it
    # is delimited and the safety block lands after it.
    sections.append(PromptSection("The learner's question", question, untrusted=True))
    sections.append(PromptSection("Task", _TASK))

    result = llm_gateway.generate(
        "chatbot", sections, language=language, user_id=user.id
    )

    if not result.ok:
        answer = _reading_list(corpus_a if corpus_a.chunks else corpus_b, language)
        if market_text:
            answer += f"\n\nLive data:\n{market_text}"
        reply = _persist(db, session, question, answer, citations, "offline")
        return {
            "session_id": session.id,
            "message_id": reply.id,
            "answer": answer,
            "citations": citations,
            "mode": "offline",
            "grounded": True,
            "status": "ok",
            "top_score": round(top_score, 4),
        }

    # R17.3 — an answer with nothing behind it is exactly what this whole module
    # exists to prevent, so the invariant is asserted rather than assumed. It
    # should be unreachable: we only get here when retrieval or market data
    # produced something. If a future change breaks that, decline loudly instead
    # of shipping an ungrounded answer.
    if not citations:
        log.error(
            "Generated an answer with no citations; discarding. user=%s question=%r",
            user.id, question[:80],
        )
        topics = ", ".join(available_topics(db))
        answer = _NO_MATERIAL.get(language, _NO_MATERIAL["en"]).format(topics=topics)
        reply = _persist(db, session, question, answer, [], "grounding_failed")
        return {
            "session_id": session.id,
            "message_id": reply.id,
            "answer": answer,
            "citations": [],
            "mode": "grounding_failed",
            "grounded": False,
            "status": "no_material",
            "available_topics": available_topics(db),
            "top_score": round(top_score, 4),
        }

    reply = _persist(db, session, question, result.text, citations, result.mode)
    return {
        "session_id": session.id,
        "message_id": reply.id,
        "answer": result.text,
        "citations": citations,
        "mode": result.mode,
        "grounded": True,
        "status": "ok",
        "corpora_used": sorted({c["corpus"] for c in citations}),
        "top_score": round(top_score, 4),
    }


# ---------------------------------------------------------------------------
# Session listing
# ---------------------------------------------------------------------------
def list_sessions(db: Session, user_id: str) -> list[dict]:
    rows = (
        db.query(ChatSession)
        .filter_by(user_id=user_id)
        .order_by(ChatSession.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": r.id,
            "title": r.title or "New conversation",
            "created_at": r.created_at.isoformat(),
            "message_count": db.query(ChatMessage).filter_by(session_id=r.id).count(),
        }
        for r in rows
    ]


def get_transcript(db: Session, user_id: str, session_id: str) -> list[dict] | None:
    """Messages for one session, or None when it is not this learner's."""
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        return None
    rows = (
        db.query(ChatMessage)
        .filter_by(session_id=session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": m.citations or [],
            "mode": m.mode,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]
