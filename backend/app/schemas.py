"""Pydantic request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _validate_email_loose(v: str) -> str:
    """Accept .test / .local / etc. — useful for the demo."""
    from email_validator import EmailNotValidError, validate_email

    try:
        return validate_email(
            v, check_deliverability=False, test_environment=True
        ).normalized
    except EmailNotValidError as e:
        raise ValueError(str(e))


# ----- users -----------------------------------------------------------------
class UserCreate(BaseModel):
    email: str
    display_name: str | None = None
    persona: Literal["woman", "teen"] = "woman"
    risk_appetite: Literal["low", "medium", "high"] = "medium"
    language: Literal["en", "hi"] = "en"

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _validate_email_loose(v)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    persona: str
    risk_appetite: str
    language: str
    cash: float


# ----- trades ----------------------------------------------------------------
class PreviewTradeRequest(BaseModel):
    user_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)


class ConfirmTradeRequest(PreviewTradeRequest):
    # Returned by /portfolio/preview. Lets the backend resolve exactly the
    # warnings this user saw, and enforce acknowledgement of critical ones.
    preview_id: str | None = None


# ----- goals -----------------------------------------------------------------
class GoalCreate(BaseModel):
    user_id: str
    template_key: str
    label: str | None = None
    target_amount: float | None = None
    horizon_months: int | None = None


# ----- scenarios -------------------------------------------------------------
class ScenarioStart(BaseModel):
    user_id: str
    kind: Literal["crash", "correction", "rally", "sideways"]
    severity: float = Field(ge=-0.6, le=0.6)
    duration_days: int = Field(default=10, ge=1, le=120)
    recovery_days: int = Field(default=20, ge=1, le=240)
    narrative: str | None = None


class ScenarioStop(BaseModel):
    user_id: str


# ----- quizzes ---------------------------------------------------------------
class QuizSubmit(BaseModel):
    user_id: str
    concept: str
    answers: list[int]


# ----- reflections -----------------------------------------------------------
class ReflectionCreate(BaseModel):
    user_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    triggering_rule_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    # Identifies which preview was backed out of, so the right warnings get
    # credited as "heeded".
    preview_id: str | None = None


# ----- adaptive quizzes ------------------------------------------------------
class AdaptiveQuizSubmit(BaseModel):
    """Submission for a quiz built by the generator.

    ``question_ids`` echoes back the exact questions the learner was shown. The
    server reads each correct answer from its own stored row, so the client never
    holds the answer key.
    """

    user_id: str
    concept: str
    question_ids: list[str] = Field(min_length=1)
    answers: list[int]


# ----- chatbot ---------------------------------------------------------------
class ChatAsk(BaseModel):
    user_id: str
    question: str = Field(min_length=1, max_length=500)
    # Omit to start a new conversation.
    session_id: str | None = None
