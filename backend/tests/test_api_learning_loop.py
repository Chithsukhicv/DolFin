"""End-to-end API tests for the loop the whole product depends on:

    warning fires → learner heeds it → discipline score reflects that

Each link was broken before. Warnings were only recorded on *executed* trades,
so cancelling had nothing to mark as heeded; and readiness never read quiz
results even though the UI announced a "discipline boost". These tests drive the
real HTTP endpoints so the wiring, not just the services, is covered.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.models import Stock


@pytest.fixture
def client(fake_market):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with TestingSession() as seed:
        seed.add_all([
            Stock(symbol="TCS.NS", name="TCS", sector="IT", market_cap_band="large", risk_level="low"),
            Stock(symbol="INFY.NS", name="Infosys", sector="IT", market_cap_band="large", risk_level="low"),
            Stock(symbol="HDFCBANK.NS", name="HDFC Bank", sector="Banking", market_cap_band="large", risk_level="low"),
            Stock(symbol="TATASTEEL.NS", name="Tata Steel", sector="Metals", market_cap_band="large", risk_level="high"),
            Stock(symbol="NIFTYBEES.NS", name="Nifty 50 ETF", sector="Index Fund", market_cap_band="index", risk_level="low"),
        ])
        seed.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # Replace the real lifespan with a no-op so startup doesn't create tables in
    # or seed the on-disk database.
    @asynccontextmanager
    async def no_lifespan(_app):
        yield

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.router.lifespan_context = no_lifespan

    with TestClient(app) as c:
        yield c

    engine.dispose()


@pytest.fixture
def learner(client):
    res = client.post("/users", json={
        "email": "loop@example.test",
        "display_name": "Loop",
        "persona": "teen",
        "risk_appetite": "low",
        "language": "en",
    })
    assert res.status_code == 200, res.text
    return res.json()


class TestHeedingAWarningIsRewarded:
    def test_cancel_and_reflect_credits_the_warning(self, client, learner):
        uid = learner["id"]

        preview = client.post("/portfolio/preview", json={
            "user_id": uid, "symbol": "TCS.NS", "side": "buy", "quantity": 10,
        }).json()

        assert preview["interventions"], "expected a concentration warning"
        assert preview["preview_id"]

        # Back out, citing the warnings we were shown.
        res = client.post("/reflections", json={
            "user_id": uid,
            "symbol": "TCS.NS",
            "side": "buy",
            "quantity": 10,
            "preview_id": preview["preview_id"],
            "triggering_rule_ids": [i["rule_id"] for i in preview["interventions"]],
            "reason": "Too concentrated, will spread out instead",
        })
        assert res.status_code == 200, res.text
        assert res.json()["warnings_heeded"] >= 1, "heeding was not recorded"

        logs = client.get(f"/history/interventions/{uid}").json()
        assert any(l["user_action"] == "heeded" for l in logs)

    def test_trading_anyway_is_recorded_as_ignored(self, client, learner):
        uid = learner["id"]
        preview = client.post("/portfolio/preview", json={
            "user_id": uid, "symbol": "TCS.NS", "side": "buy", "quantity": 10,
        }).json()

        res = client.post("/portfolio/buy", json={
            "user_id": uid, "symbol": "TCS.NS", "side": "buy", "quantity": 10,
            "preview_id": preview["preview_id"],
        })
        assert res.status_code == 200, res.text

        logs = client.get(f"/history/interventions/{uid}").json()
        assert logs and all(l["user_action"] == "ignored" for l in logs)

    def test_heeding_beats_ignoring_on_the_discipline_score(self, client, learner):
        """The payoff must be visible in the number, or the button is theatre."""
        uid = learner["id"]

        # Establish a small position so a sell is possible.
        client.post("/portfolio/buy", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "buy", "quantity": 5,
        })
        baseline = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]

        # A crash makes selling a panic-sell.
        client.post("/scenarios/start", json={
            "user_id": uid, "kind": "crash", "severity": -0.30,
            "duration_days": 10, "recovery_days": 20,
        })
        preview = client.post("/portfolio/preview", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "sell", "quantity": 5,
        }).json()
        assert preview["blocking"] is True
        assert any(i["rule_id"] == "panic_sell" for i in preview["interventions"])

        client.post("/reflections", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "sell", "quantity": 5,
            "preview_id": preview["preview_id"],
            "triggering_rule_ids": ["panic_sell"],
            "reason": "Holding through the dip",
        })

        after = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]
        assert after > baseline, (
            f"discipline did not improve after heeding a critical warning "
            f"({baseline} → {after})"
        )

    def test_panic_selling_anyway_lowers_discipline(self, client, learner):
        uid = learner["id"]
        client.post("/portfolio/buy", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "buy", "quantity": 5,
        })
        baseline = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]

        client.post("/scenarios/start", json={
            "user_id": uid, "kind": "crash", "severity": -0.30,
            "duration_days": 10, "recovery_days": 20,
        })
        preview = client.post("/portfolio/preview", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "sell", "quantity": 5,
        }).json()
        client.post("/portfolio/sell", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "sell", "quantity": 5,
            "preview_id": preview["preview_id"],
        })

        after = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]
        assert after < baseline, f"panic sell was not penalised ({baseline} → {after})"


class TestCriticalWarningsCannotBeBypassed:
    def test_direct_api_call_refuses_a_critical_trade(self, client, learner):
        """'blocking' was cosmetic: it only changed a button label."""
        uid = learner["id"]
        client.post("/portfolio/buy", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "buy", "quantity": 5,
        })
        client.post("/scenarios/start", json={
            "user_id": uid, "kind": "crash", "severity": -0.30,
            "duration_days": 10, "recovery_days": 20,
        })

        # No preview_id: the caller never saw the coaching.
        res = client.post("/portfolio/sell", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "sell", "quantity": 5,
        })
        assert res.status_code == 409
        assert "preview" in res.json()["detail"].lower()

    def test_acknowledging_via_preview_allows_it(self, client, learner):
        """Learners must stay free to override — informed, not blocked."""
        uid = learner["id"]
        client.post("/portfolio/buy", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "buy", "quantity": 5,
        })
        client.post("/scenarios/start", json={
            "user_id": uid, "kind": "crash", "severity": -0.30,
            "duration_days": 10, "recovery_days": 20,
        })
        preview = client.post("/portfolio/preview", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "sell", "quantity": 5,
        }).json()

        res = client.post("/portfolio/sell", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "sell", "quantity": 5,
            "preview_id": preview["preview_id"],
        })
        assert res.status_code == 200, res.text


class TestQuizLoop:
    def test_passing_a_quiz_raises_readiness(self, client, learner):
        uid = learner["id"]
        client.post("/portfolio/buy", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "buy", "quantity": 5,
        })
        before = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]

        from app.data.quizzes_seed import QUIZZES

        answers = [q["answer"] for q in QUIZZES["diversification"]]
        res = client.post("/quizzes/submit", json={
            "user_id": uid, "concept": "diversification", "answers": answers,
        })
        assert res.status_code == 200, res.text
        assert res.json()["passed"] is True

        after = client.get(f"/readiness/{uid}").json()["breakdown"]["discipline"]
        assert after > before, "quiz pass did not affect discipline"

    def test_wrong_answers_come_back_with_explanations(self, client, learner):
        uid = learner["id"]
        from app.data.quizzes_seed import QUIZZES

        raw = QUIZZES["panic_selling"]
        wrong = [(q["answer"] + 1) % len(q["options"]) for q in raw]
        res = client.post("/quizzes/submit", json={
            "user_id": uid, "concept": "panic_selling", "answers": wrong,
        }).json()

        assert res["passed"] is False
        assert all(a["explanation"] for a in res["answers"])

    def test_quiz_get_does_not_leak_answers(self, client):
        res = client.get("/quizzes/diversification").json()
        for q in res["questions"]:
            assert "answer" not in q


class TestEquityCurve:
    def test_trades_and_scenarios_produce_points(self, client, learner):
        """This curve is how 'you held through the crash and recovered' is shown."""
        uid = learner["id"]
        client.post("/portfolio/buy", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "buy", "quantity": 5,
        })
        client.post("/scenarios/start", json={
            "user_id": uid, "kind": "crash", "severity": -0.30,
            "duration_days": 10, "recovery_days": 20,
        })

        curve = client.get(f"/history/equity/{uid}").json()
        assert len(curve) >= 2
        assert all("total_value" in p and "at" in p for p in curve)
        assert any(p["reason"] == "trade" for p in curve)


class TestGuidedPath:
    def test_path_gives_a_new_learner_somewhere_to_go(self, client, learner):
        path = client.get(f"/learn/path/{learner['id']}").json()
        assert path["next_step"]["href"]
        assert path["total"] >= 6

    def test_path_reflects_progress(self, client, learner):
        uid = learner["id"]
        before = client.get(f"/learn/path/{uid}").json()["completed"]
        client.post("/portfolio/buy", json={
            "user_id": uid, "symbol": "HDFCBANK.NS", "side": "buy", "quantity": 5,
        })
        after = client.get(f"/learn/path/{uid}").json()["completed"]
        assert after > before


class TestAccountRecovery:
    def test_account_can_be_found_by_email(self, client, learner):
        """Clearing localStorage used to orphan the portfolio permanently."""
        res = client.get(f"/users/by-email/{learner['email']}")
        assert res.status_code == 200
        assert res.json()["id"] == learner["id"]

    def test_unknown_email_is_a_clean_404(self, client):
        assert client.get("/users/by-email/nobody@example.test").status_code == 404


class TestConceptLibraryEndpoints:
    def test_library_lists_concepts(self, client):
        items = client.get("/learn/concepts").json()
        assert len(items) >= 8
        assert all(i["title"] and i["one_liner"] for i in items)

    def test_concept_detail_has_body(self, client):
        c = client.get("/learn/concepts/panic_selling").json()
        assert c["body"] and c["takeaways"]

    def test_unknown_concept_404s(self, client):
        assert client.get("/learn/concepts/nope").status_code == 404

    def test_glossary_available(self, client):
        terms = client.get("/learn/glossary").json()
        assert len(terms) >= 20
