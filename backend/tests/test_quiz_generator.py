"""Adaptive quiz generation.

Generated assessment is the one AI feature that can silently corrupt the score:
a question with two right answers or an out-of-range answer index would let a
learner fail while being told they passed, or vice versa. So the validation tests
here matter more than the generation tests.

The other invariant under test: the answer key never leaves the server. Scoring
reads the stored row, so a client cannot report a pass it did not earn.
"""

from __future__ import annotations

import json

import pytest

from app.models import GeneratedQuestion, QuizAttempt, User
from app.services import indexer, quiz_generator, retrieval


@pytest.fixture(autouse=True)
def clear_cache():
    retrieval.reset_cache()
    yield
    retrieval.reset_cache()


@pytest.fixture
def corpus(db):
    indexer.reindex_corpus_a(db, embed=False)
    return db


def _good_question(concept="panic_selling"):
    return {
        "question": "Prices fall 8% and you sell everything. What does that behaviour show?",
        "options": [
            "Panic selling, which turns a paper loss into a real one",
            "Careful rebalancing based on new information",
            "A tax-efficient way to manage a portfolio",
            "Evidence that the companies have become worse businesses",
        ],
        "answer": 0,
        "explanation": "Selling into a fall realises the loss and takes you out of the recovery.",
    }


def _reply(*questions):
    return json.dumps({"questions": list(questions)})


# ---------------------------------------------------------------------------
class TestValidation:
    def test_accepts_a_well_formed_question(self):
        assert quiz_generator.validate_question(_good_question(), "panic_selling")

    def test_rejects_the_wrong_option_count(self):
        q = _good_question()
        q["options"] = q["options"][:3]
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_duplicate_options(self):
        q = _good_question()
        q["options"][1] = q["options"][0]
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_an_out_of_range_answer_index(self):
        q = _good_question()
        q["answer"] = 4
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_a_negative_answer_index(self):
        q = _good_question()
        q["answer"] = -1
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_a_non_numeric_answer(self):
        q = _good_question()
        q["answer"] = "the first one"
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_an_over_long_question(self):
        q = _good_question()
        q["question"] = "Why? " + "x" * quiz_generator.MAX_QUESTION_CHARS
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_an_over_long_option(self):
        q = _good_question()
        q["options"][2] = "y" * (quiz_generator.MAX_OPTION_CHARS + 1)
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_a_stub_explanation(self):
        q = _good_question()
        q["explanation"] = "Because."
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_an_empty_option(self):
        q = _good_question()
        q["options"][3] = "   "
        assert quiz_generator.validate_question(q, "panic_selling") is None

    def test_rejects_a_question_about_a_different_concept(self):
        """R8.6: the question must actually name or paraphrase the target."""
        q = {
            "question": "What does SIP stand for in Indian mutual funds?",
            "options": ["Systematic Investment Plan", "Single Item Purchase",
                        "Standard Interest Payment", "Secured Income Product"],
            "answer": 0,
            "explanation": "SIP means investing a fixed amount on a fixed schedule.",
        }
        assert quiz_generator.validate_question(q, "index_funds") is None

    def test_accepts_a_paraphrase_of_the_concept(self):
        q = {
            "question": "You hold a stock down 30% only so you can exit at break even. Why is that risky?",
            "options": [
                "The entry price has no bearing on the company's prospects",
                "Break even is a legally protected level",
                "Brokers charge more below the purchase price",
                "Losses are only taxed once realised at a profit",
            ],
            "answer": 0,
            "explanation": "Anchoring on your purchase price is loss aversion, not analysis.",
        }
        assert quiz_generator.validate_question(q, "loss_aversion")

    def test_rejects_a_non_dict(self):
        assert quiz_generator.validate_question("a question", "panic_selling") is None


# ---------------------------------------------------------------------------
class TestSeededFallback:
    def test_serves_seeded_questions_without_a_model(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        assert quiz["status"] == "ok"
        assert quiz["mode"] == "seeded"
        assert quiz["generated_count"] == 0

    def test_returns_the_full_quiz_length(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        assert len(quiz["questions"]) == quiz_generator.QUESTIONS_PER_QUIZ

    def test_unknown_concept_is_unavailable(self, db, user, corpus):
        """R8.8: no seeded bank and nothing generated."""
        quiz = quiz_generator.build_quiz(db, user, "not_a_real_concept")
        assert quiz["status"] == "unavailable"
        assert quiz["concept"] == "not_a_real_concept"

    def test_questions_are_persisted_so_scoring_is_reproducible(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        rows = db.query(GeneratedQuestion).filter_by(user_id=user.id).all()
        assert len(rows) == len(quiz["question_ids"])

    def test_options_are_returned_but_answers_are_not(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        for question in quiz["questions"]:
            assert question["options"]
            assert "answer" not in question


# ---------------------------------------------------------------------------
class TestGeneration:
    def test_uses_generated_questions_when_available(self, db, user, corpus, llm):
        llm.reply = _reply(_good_question(), _good_question() | {
            "question": "You sell during a crash. What is the main cost of panic selling?",
        }, _good_question() | {
            "question": "A dip of 5% makes you sell. What does panic selling cost you?",
        })
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        assert quiz["mode"] == "generated"
        assert quiz["generated_count"] == 3

    def test_grounds_generation_in_corpus_a(self, db, user, corpus, llm):
        llm.reply = _reply(_good_question())
        quiz_generator.build_quiz(db, user, "panic_selling")
        assert "Reference material" in llm.prompts[0]

    def test_citations_are_persisted_with_generated_questions(self, db, user, corpus, llm):
        llm.reply = _reply(_good_question())
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        generated = [q for q in quiz["questions"] if q["source"] == "generated"]
        row = db.get(GeneratedQuestion, generated[0]["id"])
        assert row.citations

    def test_bad_questions_are_replaced_by_seeded_ones(self, db, user, corpus, llm):
        """R8.7: discard and substitute, never show a broken question."""
        broken = _good_question()
        broken["answer"] = 9
        llm.reply = _reply(broken)
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        assert quiz["generated_count"] == 0
        assert quiz["seeded_count"] == quiz_generator.QUESTIONS_PER_QUIZ

    def test_a_partial_generation_is_topped_up_from_the_seed_bank(
        self, db, user, corpus, llm
    ):
        llm.reply = _reply(_good_question())
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        assert quiz["generated_count"] == 1
        assert len(quiz["questions"]) == quiz_generator.QUESTIONS_PER_QUIZ

    def test_no_corpus_material_means_no_generation(self, db, user, llm):
        """Nothing indexed, so there is nothing to ground a question in."""
        questions, citations = quiz_generator.generate(db, user, "panic_selling")
        assert questions == []
        assert citations == []
        assert llm.calls == 0

    def test_unparseable_response_falls_back(self, db, user, corpus, llm):
        llm.reply = "Sure! Here are some questions..."
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        assert quiz["mode"] == "seeded"

    def test_excludes_questions_already_answered_correctly(self, db, user, corpus, llm):
        """R8.10: re-asking a solved question measures memory, not understanding."""
        repeat = _good_question()
        db.add(QuizAttempt(
            user_id=user.id, concept="panic_selling", score_pct=100.0, passed=True,
            answers=[{"question": repeat["question"], "is_correct": True}],
        ))
        db.commit()
        llm.reply = _reply(repeat)
        questions, _ = quiz_generator.generate(db, user, "panic_selling")
        assert questions == []

    def test_previously_solved_questions_are_listed_in_the_prompt(
        self, db, user, corpus, llm
    ):
        db.add(QuizAttempt(
            user_id=user.id, concept="panic_selling", score_pct=100.0, passed=True,
            answers=[{"question": "Selling during a crash leads to what?", "is_correct": True}],
        ))
        db.commit()
        llm.reply = _reply(_good_question())
        quiz_generator.generate(db, user, "panic_selling")
        assert "Already answered correctly" in llm.prompts[0]


# ---------------------------------------------------------------------------
class TestScoring:
    def test_all_correct_passes(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        answers = [
            db.get(GeneratedQuestion, qid).answer for qid in quiz["question_ids"]
        ]
        result = quiz_generator.score(db, user, "panic_selling", quiz["question_ids"], answers)
        assert result["score_pct"] == 100.0
        assert result["passed"] is True

    def test_all_wrong_fails(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        answers = [
            (db.get(GeneratedQuestion, qid).answer + 1) % 4 for qid in quiz["question_ids"]
        ]
        result = quiz_generator.score(db, user, "panic_selling", quiz["question_ids"], answers)
        assert result["score_pct"] == 0.0
        assert result["passed"] is False

    def test_uses_the_existing_eighty_percent_threshold(self, db, user, corpus):
        """R8.4: two of three is 66.7%, which is a fail."""
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        ids = quiz["question_ids"]
        answers = [db.get(GeneratedQuestion, qid).answer for qid in ids]
        answers[0] = (answers[0] + 1) % 4
        result = quiz_generator.score(db, user, "panic_selling", ids, answers)
        assert result["score_pct"] == pytest.approx(66.7, abs=0.1)
        assert result["passed"] is False

    def test_explanation_is_returned_for_correct_answers_too(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        answers = [db.get(GeneratedQuestion, qid).answer for qid in quiz["question_ids"]]
        result = quiz_generator.score(db, user, "panic_selling", quiz["question_ids"], answers)
        assert all(row["explanation"] for row in result["answers"])

    def test_missing_answers_count_as_wrong(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        result = quiz_generator.score(db, user, "panic_selling", quiz["question_ids"], [])
        assert result["score_pct"] == 0.0

    def test_another_learners_questions_are_rejected(self, db, user, corpus):
        other = User(email="other@example.test")
        db.add(other)
        db.commit()
        theirs = quiz_generator.build_quiz(db, other, "panic_selling")
        assert quiz_generator.score(db, user, "panic_selling",
                                    theirs["question_ids"], [0, 0, 0]) is None

    def test_mismatched_concept_is_rejected(self, db, user, corpus):
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        assert quiz_generator.score(db, user, "diversification",
                                    quiz["question_ids"], [0, 0, 0]) is None

    def test_unknown_question_id_is_rejected(self, db, user, corpus):
        assert quiz_generator.score(db, user, "panic_selling", ["nope"], [0]) is None

    def test_recorded_attempt_uses_the_shared_concept_key(self, db, user, corpus):
        """R8.5: the Readiness Engine counts distinct concepts, so this must match."""
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        answers = [db.get(GeneratedQuestion, qid).answer for qid in quiz["question_ids"]]
        attempt = quiz_generator.record(db, user, "panic_selling", quiz["question_ids"], answers)
        assert attempt.concept == "panic_selling"
        assert attempt.passed is True

    def test_a_passed_generated_quiz_reaches_the_readiness_score(self, db, user, corpus):
        from app.services import readiness as readiness_service

        before = readiness_service.compute_readiness(db, user)["score"]
        quiz = quiz_generator.build_quiz(db, user, "panic_selling")
        answers = [db.get(GeneratedQuestion, qid).answer for qid in quiz["question_ids"]]
        quiz_generator.record(db, user, "panic_selling", quiz["question_ids"], answers)
        after = readiness_service.compute_readiness(db, user)["score"]
        assert after > before


# ---------------------------------------------------------------------------
class TestTargets:
    def test_lists_concepts_the_learner_failed(self, db, user):
        db.add(QuizAttempt(user_id=user.id, concept="loss_aversion",
                           score_pct=33.0, passed=False, answers=[]))
        db.commit()
        assert quiz_generator.failed_concepts(db, user) == ["loss_aversion"]

    def test_a_later_pass_removes_the_concept(self, db, user):
        db.add(QuizAttempt(user_id=user.id, concept="loss_aversion",
                           score_pct=33.0, passed=False, answers=[]))
        db.add(QuizAttempt(user_id=user.id, concept="loss_aversion",
                           score_pct=100.0, passed=True, answers=[]))
        db.commit()
        assert quiz_generator.failed_concepts(db, user) == []

    def test_orders_by_failure_count(self, db, user):
        for _ in range(3):
            db.add(QuizAttempt(user_id=user.id, concept="loss_aversion",
                               score_pct=33.0, passed=False, answers=[]))
        db.add(QuizAttempt(user_id=user.id, concept="fomo",
                           score_pct=33.0, passed=False, answers=[]))
        db.commit()
        assert quiz_generator.failed_concepts(db, user)[0] == "loss_aversion"
