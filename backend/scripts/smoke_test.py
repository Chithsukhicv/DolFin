"""End-to-end smoke test against a running server with real market data.

Walks the full learner journey the way a person would, and asserts at each step.
The unit suite uses stubbed prices; this exists to catch the things only a live
run reveals — Yahoo being unreachable, a router wired up wrong, or the guided
path disagreeing with what actually happened.

Usage:
    # terminal 1
    uvicorn app.main:app --reload
    # terminal 2
    python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
import uuid

import httpx

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

    section("Cleanup")
    reset = client.post(f"/users/{uid}/reset")
    check("POST /users/{id}/reset", reset.status_code == 200)
    check("cash restored", reset.json()["cash"] == 100_000)

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
