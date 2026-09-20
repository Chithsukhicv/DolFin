"""End-to-end smoke test against a running server with real market data.

Walks the full learner journey the way a person would, and asserts at each step.
The unit suite uses stubbed prices; this exists to catch the things only a live
run reveals — Yahoo being unreachable, a router wired up wrong, or the guided
path disagreeing with what actually happened.

Usage, from ``backend/``:
    # terminal 1
    uvicorn app.main:app --reload
    # terminal 2
    python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import httpx

# Run directly (``python scripts/smoke_test.py``) and Python puts scripts/ on the
# path, not backend/ — so the ``app`` package import below fails. Adding the
# parent explicitly makes both that and ``python -m scripts.smoke_test`` work.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000"
TIMEOUT = 30.0

passed = 0
failed: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed.append(label)
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def health_corpora(client: httpx.Client) -> dict:
    """Current corpus counts. Re-read each time — they change as the run proceeds."""
    return client.get("/health").json().get("corpora", {})


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=TIMEOUT)

    section("Server reachable")
    try:
        health = client.get("/health")
        check("GET /health", health.status_code == 200)
    except httpx.ConnectError:
        print("  FAIL  cannot reach the server — start uvicorn first")
        return 1

    section("Learning content is served")
    concepts = client.get("/learn/concepts").json()
    check("concept library populated", len(concepts) >= 8, f"got {len(concepts)}")
    glossary = client.get("/learn/glossary").json()
    check("glossary populated", len(glossary) >= 20, f"got {len(glossary)}")
    detail = client.get("/learn/concepts/panic_selling").json()
    check("concept detail has body", bool(detail.get("body")))
    check("concept detail has takeaways", bool(detail.get("takeaways")))

    section("Live market data")
    quote = client.get("/market/quote/TCS")
    check("GET /market/quote/TCS", quote.status_code == 200, quote.text[:120])
    price = quote.json().get("price", 0) if quote.status_code == 200 else 0
    check("price looks sane", price > 0, f"price={price}")
    if quote.status_code == 200 and quote.json().get("stale"):
        print("        note: price served from cache (Yahoo did not respond)")

    hist = client.get("/market/history/TCS?period=1mo&interval=1d")
    check("price history available", hist.status_code == 200 and len(hist.json()) > 5)

    catalog = client.get("/catalog/stocks").json()
    check("catalogue seeded", len(catalog) >= 30, f"got {len(catalog)}")
    funds = [s for s in catalog if s["sector"] == "Index Fund"]
    check("index funds present for SIP practice", len(funds) >= 3, f"got {len(funds)}")

    section("Onboarding")
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.test"
    user = client.post("/users", json={
        "email": email, "display_name": "Smoke", "persona": "teen",
        "risk_appetite": "low", "language": "en",
    })
    check("POST /users", user.status_code == 200, user.text[:160])
    if user.status_code != 200:
        return 1
    uid = user.json()["id"]
    check("starting cash is 100000", user.json()["cash"] == 100_000)

    recovered = client.get(f"/users/by-email/{email}")
    check("account recoverable by email", recovered.status_code == 200)
    check("recovery returns same user", recovered.json().get("id") == uid)

    templates = client.get("/goals/templates?persona=teen").json()
    check("goal templates for teen", len(templates) > 0)
    goal = client.post("/goals", json={"user_id": uid, "template_key": templates[0]["key"]})
    check("POST /goals", goal.status_code == 200, goal.text[:160])

    section("Readiness starts at zero")
    r0 = client.get(f"/readiness/{uid}").json()
    check("score is 0 before trading", r0["score"] == 0.0, f"got {r0['score']}")
    check("not marked active", r0["is_active"] is False)
    check("not graduated", r0["graduated"] is False)

    section("Guided path gives a next step")
    path = client.get(f"/learn/path/{uid}").json()
    check("path has steps", path["total"] >= 6)
    check("path suggests a next action", path.get("next_step") is not None)

    section("First buy is not treated as a critical mistake")
    # A small first position is ~8% of the portfolio, not 100%.
    prev = client.post("/portfolio/preview", json={
        "user_id": uid, "symbol": "NIFTYBEES", "side": "buy", "quantity": 10,
    })
    check("POST /portfolio/preview", prev.status_code == 200, prev.text[:160])
    preview = prev.json()
    check("preview returns a preview_id", bool(preview.get("preview_id")))
    check("first small buy is not blocking", preview["blocking"] is False,
          f"interventions={[i['rule_id'] for i in preview['interventions']]}")
    check("coach message carries a mode", bool(preview["coach"].get("mode")))

    buy = client.post("/portfolio/buy", json={
        "user_id": uid, "symbol": "NIFTYBEES", "side": "buy", "quantity": 10,
        "preview_id": preview["preview_id"],
    })
    check("POST /portfolio/buy", buy.status_code == 200, buy.text[:160])

    section("Concentration warning fires on an oversized buy")
    big = client.post("/portfolio/preview", json={
        "user_id": uid, "symbol": "TCS", "side": "buy", "quantity": 12,
    }).json()
    rules = [i["rule_id"] for i in big["interventions"]]
    check("concentration rule fires", "concentration" in rules, f"fired={rules}")
    check("every rule finding is flagged source=rule",
          all(i.get("source") == "rule" for i in big["interventions"]),
          f"sources={[i.get('source') for i in big['interventions']]}")

    section("Heeding a warning is recorded and rewarded")
    disc_before = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]
    refl = client.post("/reflections", json={
        "user_id": uid, "symbol": "TCS", "side": "buy", "quantity": 12,
        "preview_id": big["preview_id"],
        "triggering_rule_ids": rules,
        "reason": "smoke test: backing out",
    })
    check("POST /reflections", refl.status_code == 200, refl.text[:160])
    check("warnings credited as heeded", refl.json().get("warnings_heeded", 0) >= 1)

    logs = client.get(f"/history/interventions/{uid}").json()
    check("a log row is marked heeded", any(l["user_action"] == "heeded" for l in logs))
    check("intervention history is flagged source=rule",
          all(l.get("source") == "rule" for l in logs))

    disc_after = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]
    check("discipline improved after heeding", disc_after > disc_before,
          f"{disc_before} -> {disc_after}")

    section("Crash scenario and panic-sell protection")
    scen = client.post("/scenarios/start", json={
        "user_id": uid, "kind": "crash", "severity": -0.30,
        "duration_days": 10, "recovery_days": 20,
    })
    check("POST /scenarios/start", scen.status_code == 200, scen.text[:160])

    sell_prev = client.post("/portfolio/preview", json={
        "user_id": uid, "symbol": "NIFTYBEES", "side": "sell", "quantity": 10,
    }).json()
    sell_rules = [i["rule_id"] for i in sell_prev["interventions"]]
    check("panic_sell fires during a crash", "panic_sell" in sell_rules, f"fired={sell_rules}")
    check("panic sell is blocking", sell_prev["blocking"] is True)

    bypass = client.post("/portfolio/sell", json={
        "user_id": uid, "symbol": "NIFTYBEES", "side": "sell", "quantity": 10,
    })
    check("critical trade cannot bypass the coach", bypass.status_code == 409,
          f"got {bypass.status_code}")

    held = client.post("/reflections", json={
        "user_id": uid, "symbol": "NIFTYBEES", "side": "sell", "quantity": 10,
        "preview_id": sell_prev["preview_id"],
        "triggering_rule_ids": sell_rules,
        "reason": "smoke test: holding through the dip",
    })
    check("holding through the crash is recorded", held.status_code == 200)

    section("Quiz loop feeds the score")
    quiz = client.get("/quizzes/panic_selling")
    check("GET /quizzes/panic_selling", quiz.status_code == 200)
    questions = quiz.json()["questions"]
    check("answers are not leaked", all("answer" not in q for q in questions))

    from app.data.quizzes_seed import QUIZZES  # local import: needs the app package

    correct = [q["answer"] for q in QUIZZES["panic_selling"]]
    before_quiz = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]
    result = client.post("/quizzes/submit", json={
        "user_id": uid, "concept": "panic_selling", "answers": correct,
    })
    check("POST /quizzes/submit", result.status_code == 200, result.text[:160])
    check("all-correct passes", result.json()["passed"] is True)
    check("explanations returned", all(a["explanation"] for a in result.json()["answers"]))
    after_quiz = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]
    check("passing a quiz raises discipline", after_quiz > before_quiz,
          f"{before_quiz} -> {after_quiz}")

    section("Equity curve captured the journey")
    curve = client.get(f"/history/equity/{uid}").json()
    check("curve has points", len(curve) >= 2, f"got {len(curve)}")
    check("a trade point exists", any(p["reason"] == "trade" for p in curve))
    check("a scenario point exists", any(p["reason"] == "scenario_start" for p in curve))

    section("Readiness stays honest for a beginner")
    final = client.get(f"/readiness/{uid}").json()
    check("score is provisional", final["provisional"] is True)
    check("score stays low for a 2-trade learner", final["score"] < 45,
          f"score={final['score']}")
    check("not graduated", final["graduated"] is False)
    print(f"        final score: {final['score']}  confidence: {final['confidence']}")

    section("Concept progress summary")
    summary = client.get(f"/history/interventions/{uid}/summary").json()
    check("summary groups by concept", len(summary) >= 1)
    panic_row = next((s for s in summary if s["concept"] == "panic_selling"), None)
    check("panic_selling tracked", panic_row is not None)
    if panic_row:
        check("quiz pass reflected in summary", panic_row["quiz_passed"] is True)

    # -----------------------------------------------------------------------
    # AI reasoning layer.
    #
    # These pass with or without a GEMINI_API_KEY. That is the point: every AI
    # feature has a deterministic fallback, so the platform is fully usable with
    # no key and the smoke test should prove it rather than skip it.
    # -----------------------------------------------------------------------
    llm_configured = health.json().get("llm", {}).get("configured", False)
    print(f"\n(LLM {'configured' if llm_configured else 'NOT configured'} — "
          f"deterministic fallbacks {'not ' if llm_configured else ''}expected)")

    section("Retrieval corpora are indexed")
    corpora = health.json().get("corpora", {})
    check("Corpus A indexed on startup", corpora.get("corpus_a", 0) >= 80,
          f"got {corpora.get('corpus_a')}")
    check("ranking strategy reported", corpora.get("ranking") in ("lexical", "embedding"),
          f"got {corpora.get('ranking')}")
    print(f"        {corpora.get('corpus_a')} curated chunks, "
          f"{corpora.get('corpus_b')} learner chunks, ranking={corpora.get('ranking')}")

    section("Reflection analysis reads what the learner wrote")
    ref_prev = client.post("/portfolio/preview", json={
        "user_id": uid, "symbol": "TCS", "side": "buy", "quantity": 12,
    }).json()
    written = client.post("/reflections", json={
        "user_id": uid, "symbol": "TCS", "side": "buy", "quantity": 12,
        "preview_id": ref_prev["preview_id"],
        "triggering_rule_ids": [i["rule_id"] for i in ref_prev["interventions"]],
        "reason": "backing out because it'll definitely bounce back tomorrow",
    })
    check("POST /reflections returns an analysis", written.status_code == 200
          and "analysis" in written.json(), written.text[:160])
    analysis = written.json().get("analysis", {})
    check("the written reason was analysed", analysis.get("analysed") is True)
    check("a prediction is not called sound reasoning",
          analysis.get("classification") in ("prediction_based", "partly_sound"),
          f"got {analysis.get('classification')}")
    check("the learner gets a written response", bool(analysis.get("response")))
    check("heeding counted regardless of the reasoning quality",
          written.json().get("warnings_heeded", 0) >= 1)

    # The assessment must survive past the moment it was produced, or the most
    # useful feedback in the app exists for one screen and then vanishes.
    history = client.get(f"/reflections/user/{uid}").json()
    stored = next((r for r in history if r.get("ai_response")), None)
    check("the assessment is retrievable later", stored is not None)
    if stored:
        check("stored reflection keeps its classification",
              stored.get("reasoning_class") in
              ("sound", "partly_sound", "prediction_based"),
              f"got {stored.get('reasoning_class')}")
        check("stored reflection keeps the learner's exact words",
              stored.get("reason") ==
              "backing out because it'll definitely bounce back tomorrow",
              f"got {stored.get('reason')!r}")

    section("AI risk review is advisory, never scored")
    findings = client.get(
        f"/portfolio/preview/{ref_prev['preview_id']}/ai-findings?user_id={uid}"
    )
    check("GET ai-findings", findings.status_code == 200, findings.text[:160])
    check("findings are flagged as not affecting the score",
          findings.json().get("affects_score") is False)
    check("review status is reported",
          findings.json().get("status") in ("pending", "ready", "unavailable"),
          f"got {findings.json().get('status')}")

    section("Pattern analysis names the habit")
    patterns = client.get(f"/coach/patterns/{uid}")
    check("GET /coach/patterns", patterns.status_code == 200, patterns.text[:160])
    pdata = patterns.json()
    check("analysis returned for an active learner", pdata["status"] == "ok",
          f"status={pdata['status']} message={pdata.get('message')}")
    check("at least one pattern named", len(pdata["patterns"]) >= 1)
    check("every pattern cites a counted fact",
          all(p["evidence"] for p in pdata["patterns"]))
    check("every pattern is flagged as AI",
          all(p["source"] == "ai" for p in pdata["patterns"]))
    check("the counted evidence is returned alongside", "trades" in pdata["evidence"])

    cached = client.get(f"/coach/patterns/{uid}").json()
    check("an unchanged record is served from cache", cached["mode"] == "cached",
          f"got {cached['mode']}")

    section("Adaptive learning path uses measured weakness")
    apath = client.get(f"/learn/path/{uid}").json()
    check("path reports whether it adapted", "adaptive" in apath)
    check("every step carries a rationale",
          all(s.get("rationale") for s in apath["steps"]))
    check("weaknesses are measured, not guessed", "weaknesses" in apath)
    if llm_configured:
        check("path adapts when the gateway is available", apath["adaptive"] is True)
    else:
        check("path falls back to the fixed eight", apath["total"] == 8,
              f"got {apath['total']}")

    section("Grounded chatbot cites its sources")
    ask = client.post("/chat/ask", json={
        "user_id": uid, "question": "why is panic selling so expensive?",
    })
    check("POST /chat/ask", ask.status_code == 200, ask.text[:160])
    answer = ask.json()
    check("answer is grounded in retrieved material", answer["grounded"] is True,
          f"top_score={answer.get('top_score')}")
    check("citations returned", len(answer["citations"]) >= 1)
    check("citations name their corpus",
          all(c.get("corpus") in ("A", "B", "market") for c in answer["citations"]))
    check("a session was created", bool(answer["session_id"]))

    follow = client.post("/chat/ask", json={
        "user_id": uid, "question": "how many warnings have I ignored?",
        "session_id": answer["session_id"],
    }).json()
    check("a personal question reuses the session",
          follow["session_id"] == answer["session_id"])
    check("a personal question retrieves the learner's own record",
          any(c["corpus"] == "B" for c in follow["citations"]),
          f"corpora={[c['corpus'] for c in follow['citations']]}")

    ungrounded = client.post("/chat/ask", json={
        "user_id": uid, "question": "who won the 1994 football world cup?",
    }).json()
    check("declines when it has no material", ungrounded["grounded"] is False,
          f"answered anyway: {ungrounded['answer'][:80]}")
    check("names what it does cover instead",
          len(ungrounded.get("available_topics") or []) >= 1)

    transcript = client.get(f"/chat/sessions/{uid}/{answer['session_id']}").json()
    check("the conversation was persisted", len(transcript["messages"]) >= 4,
          f"got {len(transcript['messages'])}")

    section("Adaptive quiz is validated before it is shown")
    aq = client.get(f"/quizzes/adaptive/{uid}/loss_aversion")
    check("GET /quizzes/adaptive", aq.status_code == 200, aq.text[:160])
    quiz_set = aq.json()
    check("a full quiz was assembled", len(quiz_set["questions"]) == 3,
          f"got {len(quiz_set['questions'])}")
    check("every question has exactly 4 options",
          all(len(q["options"]) == 4 for q in quiz_set["questions"]))
    check("options are mutually distinct",
          all(len(set(q["options"])) == 4 for q in quiz_set["questions"]))
    check("answers are not leaked",
          all("answer" not in q for q in quiz_set["questions"]))
    check("question ids returned for scoring",
          len(quiz_set["question_ids"]) == len(quiz_set["questions"]))
    print(f"        {quiz_set['generated_count']} generated, "
          f"{quiz_set['seeded_count']} from the seeded bank")

    bad_score = client.post("/quizzes/adaptive/submit", json={
        "user_id": uid, "concept": "loss_aversion",
        "question_ids": quiz_set["question_ids"], "answers": [-1, -1, -1],
    })
    check("POST /quizzes/adaptive/submit", bad_score.status_code == 200,
          bad_score.text[:160])
    check("no answers means zero", bad_score.json()["score_pct"] == 0.0)
    check("explanations returned even on a fail",
          all(a["explanation"] for a in bad_score.json()["answers"]))

    forged = client.post("/quizzes/adaptive/submit", json={
        "user_id": uid, "concept": "loss_aversion",
        "question_ids": ["not-a-real-id"], "answers": [0],
    })
    check("unknown question ids are rejected", forged.status_code == 400,
          f"got {forged.status_code}")

    missing = client.get(f"/quizzes/adaptive/{uid}/not_a_real_concept")
    check("an unknown concept returns 422", missing.status_code == 422,
          f"got {missing.status_code}")

    section("The score stayed deterministic through all of that")
    determinism = [client.get(f"/readiness/{uid}").json()["score"] for _ in range(3)]
    check("the same record scores the same every time",
          len(set(determinism)) == 1, f"got {determinism}")

    section("Reset does not leave a stale corpus behind")
    before_reset = health_corpora(client)["corpus_b"]
    reset = client.post(f"/users/{uid}/reset")
    check("POST /users/{id}/reset", reset.status_code == 200)
    check("cash restored", reset.json()["cash"] == 100_000)
    after_reset = health_corpora(client)["corpus_b"]
    check("Corpus B was rebuilt after the reset", after_reset > 0,
          f"{before_reset} -> {after_reset}")
    holdings_chunk = client.post("/chat/ask", json={
        "user_id": uid, "question": "what do I currently hold?",
    }).json()
    check("the chatbot does not describe the deleted holdings",
          "NIFTYBEES" not in holdings_chunk["answer"],
          holdings_chunk["answer"][:120])

    section("Deleting an account removes everything derived from it")
    # A throwaway learner, so the deletion path is exercised without disturbing
    # anything the checks above depend on.
    doomed = client.post("/users", json={
        "email": f"doomed-{uuid.uuid4().hex[:8]}@example.test",
        "display_name": "Doomed", "persona": "woman",
        "risk_appetite": "medium", "language": "en",
    })
    check("throwaway learner created", doomed.status_code == 200, doomed.text[:160])
    did = doomed.json()["id"]

    client.post("/portfolio/buy", json={
        "user_id": did, "symbol": "ITC", "side": "buy", "quantity": 5,
    })
    client.post("/chat/ask", json={"user_id": did, "question": "what is diversification?"})
    corpus_with_them = health_corpora(client)["corpus_b"]
    check("they have Corpus B chunks before deletion", corpus_with_them > after_reset,
          f"{after_reset} -> {corpus_with_them}")

    gone = client.delete(f"/users/{did}")
    check("DELETE /users/{id}", gone.status_code == 200, gone.text[:200])
    removed = gone.json().get("removed", {})
    check("their retrieval chunks were deleted", removed.get("knowledge_chunks", 0) > 0,
          f"removed={removed}")
    check("their chat sessions were deleted", removed.get("chat_sessions", 0) > 0,
          f"removed={removed}")
    check("the learner is really gone",
          client.get(f"/users/{did}").status_code == 404)
    check("no orphaned Corpus B chunks remain",
          health_corpora(client)["corpus_b"] <= after_reset,
          f"expected <= {after_reset}, got {health_corpora(client)['corpus_b']}")
    check("deleting again is a clean 404",
          client.delete(f"/users/{did}").status_code == 404)

    client.close()

    print("\n" + "=" * 52)
    print(f"{passed} passed, {len(failed)} failed")
    if failed:
        for name in failed:
            print(f"  - {name}")
        return 1
    print("Full learner journey works end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
