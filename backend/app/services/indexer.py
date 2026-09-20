"""Builds and refreshes the two retrieval corpora.

Corpus A is curated content shared by every learner. It is indexed from the
modules that already own that content — concept articles, glossary, quiz
explanations, rule definitions — plus the Indian-market and behavioural-finance
material in ``knowledge_seed``. Indexing from the source modules rather than
copying the text keeps one source of truth.

Corpus B is one learner's own behavioural record, written as short factual
summaries. This is the grounding that exists in no language model's training
data, and it is what makes an answer say "you have overridden this warning four
times" instead of "diversification is important".

Both are idempotent: every chunk has a stable ``chunk_key``, so re-indexing
updates in place, inserts what is new, and deletes what no longer exists.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Goal,
    Holding,
    InterventionLog,
    KnowledgeChunk,
    PortfolioSnapshot,
    QuizAttempt,
    Reflection,
    Transaction,
    User,
)
from app.services import ranking

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Corpus A construction
# ---------------------------------------------------------------------------
def build_corpus_a() -> list[dict]:
    """Every Corpus A chunk, assembled from the modules that own the content."""
    from app.data import knowledge_seed
    from app.data.concepts_seed import CONCEPTS, GLOSSARY
    from app.data.quizzes_seed import QUIZZES

    chunks: list[dict] = []

    # Concept articles, split by section so a retrieved chunk is a coherent idea
    # rather than a whole article.
    for concept in CONCEPTS:
        for i, section in enumerate(concept["body"]):
            chunks.append({
                "chunk_key": f"concept:{concept['key']}:section:{i}",
                "source_title": f"{concept['title']} — {section['heading']}",
                "source_reference": f"/learn/{concept['key']}",
                "body": section["text"],
            })
        # Takeaways and the named misconception are high-signal and worth
        # retrieving independently of the prose.
        chunks.append({
            "chunk_key": f"concept:{concept['key']}:takeaways",
            "source_title": f"{concept['title']} — key points",
            "source_reference": f"/learn/{concept['key']}",
            "body": " ".join(concept["takeaways"]),
        })
        chunks.append({
            "chunk_key": f"concept:{concept['key']}:misconception",
            "source_title": f"{concept['title']} — common misconception",
            "source_reference": f"/learn/{concept['key']}",
            "body": (
                f"A common but incorrect belief: \"{concept['misconception']['myth']}\" "
                f"In reality: {concept['misconception']['reality']}"
            ),
        })

    # Glossary: one chunk per term.
    for term, definition in GLOSSARY.items():
        chunks.append({
            "chunk_key": f"glossary:{term}",
            "source_title": f"Glossary: {term.replace('_', ' ').title()}",
            "source_reference": "/learn",
            "body": f"{term.replace('_', ' ')}: {definition}",
        })

    # Quiz explanations: already written as tight teaching paragraphs.
    for concept, questions in QUIZZES.items():
        for i, q in enumerate(questions):
            if q.get("explanation"):
                chunks.append({
                    "chunk_key": f"quiz:{concept}:{i}",
                    "source_title": f"Quiz explanation — {concept.replace('_', ' ')}",
                    "source_reference": f"/coach/quiz/{concept}",
                    "body": f"Question: {q['question']} Explanation: {q['explanation']}",
                })

    chunks.extend(_rule_chunks())

    for extra in knowledge_seed.all_extra_chunks():
        chunks.append({
            "chunk_key": extra["key"],
            "source_title": extra["title"],
            "source_reference": None,
            "body": extra["body"],
        })

    return chunks


def _rule_chunks() -> list[dict]:
    """One chunk per deterministic rule.

    Indexing the rules themselves lets the chatbot answer "why did you warn me
    about that trade?" from the actual rule definition rather than guessing.
    """
    rules = [
        ("concentration", "20% of total portfolio value (critical above 30%)",
         "warn or critical",
         "Limits how much of the portfolio sits in one company, so a single "
         "company's decline cannot dominate the outcome. Index funds are exempt "
         "up to 60% because they already hold many companies."),
        ("sector_overlap", "40% of total portfolio value in one sector", "warn",
         "Companies in one sector face the same industry-wide risks and tend to "
         "fall together, so four names in one sector behaves like one bet."),
        ("volatility_mismatch", "low-risk profile buying a high-risk stock", "warn",
         "Flags a mismatch between the learner's stated risk appetite and the "
         "volatility of what they are buying."),
        ("fomo", "stock up more than 15% over about five trading days", "warn",
         "Buying immediately after a sharp rise often means paying near a local "
         "top, because the move is already priced in."),
        ("cash_drain", "cash falling below 10% of portfolio value", "info",
         "A cash buffer prevents becoming a forced seller when an expense arrives."),
        ("buy_during_rally", "an active simulated rally", "info",
         "Markets feel easiest near a top; this flags sizing up on optimism."),
        ("panic_sell", "selling while a simulated crash or correction is active",
         "critical",
         "The headline rule. Selling into a fall converts a recoverable paper "
         "loss into a permanent realised one."),
        ("loss_lock_in", "selling at a loss worse than 10%", "warn",
         "Prompts the learner to check whether the reason for owning it changed, "
         "or only the price did."),
        ("short_hold", "selling within seven days of buying", "info",
         "Frequent trading erodes returns through brokerage and higher "
         "short-term capital gains tax."),
    ]
    return [
        {
            "chunk_key": f"rule:{rule_id}",
            "source_title": f"Rule: {rule_id}",
            "source_reference": None,
            "body": (
                f"The {rule_id} rule fires when {threshold}. It is raised at "
                f"{severity} severity. Why it exists: {rationale}"
            ),
        }
        for rule_id, threshold, severity, rationale in rules
    ]


# ---------------------------------------------------------------------------
# Corpus B construction — the learner's own record
# ---------------------------------------------------------------------------
def _fmt_date(dt: datetime | None) -> str:
    if dt is None:
        return "unknown date"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%d %b %Y")


def build_corpus_b(db: Session, user: User) -> list[dict]:
    """Factual summaries of what this learner has actually done.

    Deliberately facts only, no interpretation — counts, dates, symbols and
    outcomes. Interpretation is the model's job at generation time; baking it in
    here would mean caching a judgement that may no longer hold.

    Email and display name are excluded so no PII enters a prompt.
    """
    uid = user.id
    chunks: list[dict] = []

    def add(key: str, title: str, body: str) -> None:
        chunks.append({
            "chunk_key": f"user:{uid}:{key}",
            "source_title": title,
            "source_reference": None,
            "body": body,
        })

    # --- profile and goal -------------------------------------------------
    goals = db.query(Goal).filter_by(user_id=uid).all()
    goal_text = "; ".join(
        f"{g.label} targeting Rs {g.target_amount:,.0f} over {g.horizon_months} months"
        for g in goals
    ) or "no goal set"
    add(
        "profile",
        "Your profile and goal",
        f"This learner uses the {user.persona} persona with a {user.risk_appetite} "
        f"risk appetite and prefers language '{user.language}'. Cash available: "
        f"Rs {user.cash:,.0f}. Goals: {goal_text}.",
    )

    # --- holdings ---------------------------------------------------------
    holdings = db.query(Holding).filter_by(user_id=uid).all()
    if holdings:
        lines = [
            f"{h.quantity:g} units of {h.symbol} at an average cost of Rs {h.avg_cost:,.2f}"
            for h in holdings
        ]
        add(
            "holdings",
            "Your current holdings",
            f"This learner currently holds {len(holdings)} position(s): " + "; ".join(lines) + ".",
        )
    else:
        add("holdings", "Your current holdings", "This learner holds no positions right now.")

    # --- trade history ----------------------------------------------------
    txns = (
        db.query(Transaction)
        .filter_by(user_id=uid)
        .order_by(Transaction.created_at.desc())
        .limit(40)
        .all()
    )
    if txns:
        buys = sum(1 for t in txns if t.side == "buy")
        sells = len(txns) - buys
        realised = sum(t.realised_pnl or 0.0 for t in txns)
        add(
            "trade_summary",
            "Your trading activity",
            f"This learner has placed {len(txns)} recent trades ({buys} buys, {sells} sells) "
            f"with total realised profit or loss of Rs {realised:,.2f}.",
        )
        recent = "; ".join(
            f"{t.side} {t.quantity:g} {t.symbol} at Rs {t.price:,.2f} on {_fmt_date(t.created_at)}"
            + (f" realising Rs {t.realised_pnl:,.2f}" if t.side == "sell" and t.realised_pnl else "")
            for t in txns[:12]
        )
        add("recent_trades", "Your recent trades", f"Most recent trades, newest first: {recent}.")
    else:
        add("trade_summary", "Your trading activity", "This learner has not placed any trades yet.")

    chunks.extend(_corpus_b_behaviour(db, user))
    return chunks


def _corpus_b_behaviour(db: Session, user: User) -> list[dict]:
    """Warning outcomes, quiz results, reflections and the equity curve."""
    uid = user.id
    out: list[dict] = []

    def add(key: str, title: str, body: str) -> None:
        out.append({
            "chunk_key": f"user:{uid}:{key}",
            "source_title": title,
            "source_reference": None,
            "body": body,
        })

    # --- warnings and how they were handled -------------------------------
    logs = db.query(InterventionLog).filter_by(user_id=uid).all()
    if logs:
        resolved = [l for l in logs if l.user_action in ("heeded", "ignored")]
        heeded = sum(1 for l in resolved if l.user_action == "heeded")
        rate = f"{int(heeded / len(resolved) * 100)}%" if resolved else "not yet measurable"
        add(
            "warning_summary",
            "How you respond to warnings",
            f"This learner has received {len(logs)} warnings, of which {len(resolved)} were "
            f"resolved by either cancelling or trading through. They heeded {heeded}, "
            f"an overall heed rate of {rate}.",
        )

        # Per concept, so retrieval can surface the specific weakness.
        by_concept: dict[str, dict[str, int]] = {}
        for l in logs:
            key = l.concept or "other"
            entry = by_concept.setdefault(key, {"fired": 0, "heeded": 0, "ignored": 0})
            entry["fired"] += 1
            if l.user_action in entry:
                entry[l.user_action] += 1
        for concept, counts in by_concept.items():
            add(
                f"warnings:{concept}",
                f"Your record on {concept.replace('_', ' ')}",
                f"The {concept.replace('_', ' ')} warning has fired {counts['fired']} times "
                f"for this learner. They heeded it {counts['heeded']} times and traded "
                f"through it {counts['ignored']} times.",
            )
    else:
        add("warning_summary", "How you respond to warnings",
            "No warnings have fired for this learner yet.")

    # --- quiz results -----------------------------------------------------
    attempts = db.query(QuizAttempt).filter_by(user_id=uid).all()
    if attempts:
        passed = sorted({a.concept for a in attempts if a.passed})
        failed = sorted({a.concept for a in attempts if not a.passed} - set(passed))
        add(
            "quizzes",
            "Your quiz results",
            f"This learner has made {len(attempts)} quiz attempts. "
            f"Passed concepts: {', '.join(passed) if passed else 'none'}. "
            f"Attempted but not yet passed: {', '.join(failed) if failed else 'none'}.",
        )

    # --- reflections (their own words) ------------------------------------
    reflections = (
        db.query(Reflection)
        .filter_by(user_id=uid)
        .order_by(Reflection.created_at.desc())
        .limit(10)
        .all()
    )
    written = [r for r in reflections if r.reason and len(r.reason.strip()) > 12]
    if written:
        joined = "; ".join(
            f"on {_fmt_date(r.created_at)}, cancelling a {r.side} of {r.symbol}, they wrote: "
            f"\"{r.reason.strip()[:200]}\""
            for r in written[:5]
        )
        add(
            "reflections",
            "Reasons you gave for backing out of trades",
            f"This learner has written reasons when cancelling trades: {joined}.",
        )

    # --- the market they are currently living in ---------------------------
    # Without this the chatbot answers "why is everything down?" from the concept
    # library when the actual answer is "because you started a 30% crash
    # simulation on Tuesday".
    from app.services import scenarios as scenarios_service

    scenario = scenarios_service.active_scenario(db, uid)
    if scenario is not None:
        multiplier = scenarios_service.current_multiplier(scenario)
        add(
            "scenario",
            "The simulated market conditions you are in",
            f"This learner has an active simulated {scenario.kind} running, started on "
            f"{_fmt_date(scenario.started_at)} with a severity of "
            f"{scenario.severity:+.0%} over {scenario.duration_days} days and a "
            f"{scenario.recovery_days}-day recovery. Prices they see are currently "
            f"multiplied by {multiplier:.2f} against the real market. "
            f"Narrative: {scenario.narrative or 'none given'}.",
        )
    else:
        add(
            "scenario",
            "The simulated market conditions you are in",
            "This learner has no simulated market event running, so the prices they "
            "see are real NSE prices.",
        )

    # --- equity curve -----------------------------------------------------
    snaps = (
        db.query(PortfolioSnapshot)
        .filter_by(user_id=uid)
        .order_by(PortfolioSnapshot.created_at.asc())
        .all()
    )
    if len(snaps) >= 2:
        first, last = snaps[0], snaps[-1]
        low = min(snaps, key=lambda s: s.total_value)
        add(
            "equity_curve",
            "Your portfolio value over time",
            f"This learner's portfolio was worth Rs {first.total_value:,.0f} at the start of "
            f"tracking on {_fmt_date(first.created_at)} and Rs {last.total_value:,.0f} most "
            f"recently. The lowest point recorded was Rs {low.total_value:,.0f} on "
            f"{_fmt_date(low.created_at)}.",
        )

    return out


# ---------------------------------------------------------------------------
# Idempotent upsert
# ---------------------------------------------------------------------------
def _sync(
    db: Session,
    desired: list[dict],
    *,
    corpus: str,
    owner_user_id: str | None,
    embed: bool,
) -> dict:
    """Make the stored chunks for this corpus match ``desired`` exactly.

    Updates rows whose ``chunk_key`` still exists, inserts new ones, deletes
    those that no longer appear. Running this twice over unchanged input produces
    the same set of chunk keys and touches nothing.
    """
    query = db.query(KnowledgeChunk).filter(KnowledgeChunk.corpus == corpus)
    if corpus == "B":
        query = query.filter(KnowledgeChunk.owner_user_id == owner_user_id)
    existing = {c.chunk_key: c for c in query.all()}

    wanted_keys = {d["chunk_key"] for d in desired}
    inserted = updated = deleted = 0

    # Embed only what actually changed, so a re-index does not re-pay for
    # unchanged content.
    to_embed: list[KnowledgeChunk] = []

    for item in desired:
        row = existing.get(item["chunk_key"])
        if row is None:
            row = KnowledgeChunk(
                corpus=corpus,
                chunk_key=item["chunk_key"],
                owner_user_id=owner_user_id,
                source_title=item["source_title"],
                source_reference=item.get("source_reference"),
                body=item["body"],
            )
            db.add(row)
            inserted += 1
            to_embed.append(row)
        else:
            # The title is part of what a chunk is ranked against, so a title
            # change invalidates the vector just as a body change does.
            text_changed = (
                row.body != item["body"] or row.source_title != item["source_title"]
            )
            row.source_title = item["source_title"]
            row.source_reference = item.get("source_reference")
            row.body = item["body"]
            if text_changed:
                row.embedding = None  # stale vector
                to_embed.append(row)
                updated += 1

    for key, row in existing.items():
        if key not in wanted_keys:
            db.delete(row)
            deleted += 1

    db.commit()

    embedded = 0
    if embed and to_embed:
        embedded = _attach_embeddings(db, to_embed)

    return {
        "corpus": corpus,
        "inserted": inserted,
        "updated": updated,
        "deleted": deleted,
        "embedded": embedded,
        "total": len(desired),
    }


def _attach_embeddings(db: Session, rows: list[KnowledgeChunk]) -> int:
    """Embed changed chunks. A failure leaves vectors null and lexical ranking works.

    Embeds ``ranking.document_text`` rather than the raw body, so the semantic and
    lexical representations of a chunk cover the same text.
    """
    settings = get_settings()
    vectors = ranking.embed_texts([ranking.document_text(row) for row in rows])
    if not vectors or len(vectors) != len(rows):
        log.info("Embeddings unavailable; %d chunks will rank lexically.", len(rows))
        return 0
    for row, vector in zip(rows, vectors):
        row.embedding = vector
        row.embedding_model = settings.gemini_embedding_model
    db.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def reindex_corpus_a(db: Session, *, embed: bool = True) -> dict:
    """Rebuild the curated corpus. Safe to run repeatedly."""
    result = _sync(db, build_corpus_a(), corpus="A", owner_user_id=None, embed=embed)
    log.info("Corpus A reindexed: %s", result)
    return result


def refresh_corpus_b(db: Session, user: User, *, embed: bool = True) -> dict:
    """Rebuild one learner's behavioural corpus.

    Called after the learner's records change. Cheap enough to run on demand:
    it is a handful of summary rows, not a per-row index.
    """
    result = _sync(
        db, build_corpus_b(db, user), corpus="B", owner_user_id=user.id, embed=embed
    )
    log.debug("Corpus B refreshed for %s: %s", user.id, result)
    return result


def refresh_corpus_b_safe(db: Session, user: User, *, embed: bool = True) -> None:
    """Refresh Corpus B, swallowing any failure.

    Callers are request handlers whose primary job already succeeded by the time
    they reach this. A failed re-index means the chatbot's view of the learner is
    briefly stale, which is not worth failing a trade or a quiz submission over.
    """
    try:
        refresh_corpus_b(db, user, embed=embed)
    except Exception as e:
        log.warning("Corpus B refresh failed for %s: %s", user.id, e)


def delete_corpus_b(db: Session, user_id: str) -> int:
    """Remove a learner's chunks. Called when the learner is deleted."""
    rows = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.corpus == "B", KnowledgeChunk.owner_user_id == user_id)
        .all()
    )
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)


def corpus_stats(db: Session) -> dict:
    """Counts for the health endpoint and for verifying an index run."""
    total = db.query(KnowledgeChunk).count()
    corpus_a = db.query(KnowledgeChunk).filter(KnowledgeChunk.corpus == "A").count()
    embedded = (
        db.query(KnowledgeChunk).filter(KnowledgeChunk.embedding.isnot(None)).count()
    )
    return {
        "total_chunks": total,
        "corpus_a": corpus_a,
        "corpus_b": total - corpus_a,
        "embedded": embedded,
        "ranking": "embedding" if embedded else "lexical",
    }
