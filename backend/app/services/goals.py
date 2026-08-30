"""Persona-aware goal templates.

The goal a user picks shapes the coaching tone and the readiness-score
'goal alignment' sub-score. We keep the templates lean and editable so we
can add languages/values without code changes later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Persona = Literal["woman", "teen"]


@dataclass(frozen=True)
class GoalTemplate:
    key: str
    label: str
    persona: Persona
    suggested_amount: float
    suggested_horizon_months: int
    coach_hint: str  # what the AI should emphasise for this goal


WOMAN_GOALS: list[GoalTemplate] = [
    GoalTemplate("independence_fund", "Independence fund", "woman", 500_000, 60,
                 "Long horizon, equity-heavy. Discourage frequent trading."),
    GoalTemplate("higher_education", "Higher education", "woman", 1_000_000, 48,
                 "Goal-bound. Emphasise stability as deadline approaches."),
    GoalTemplate("travel", "Travel", "woman", 200_000, 18,
                 "Short horizon. Steer towards lower-risk options."),
    GoalTemplate("wedding", "Wedding", "woman", 800_000, 24,
                 "Time-bound. Capital preservation over high returns."),
    GoalTemplate("child_education", "Child's education", "woman", 2_000_000, 120,
                 "Long horizon, SIP-friendly. Compounding-first."),
    GoalTemplate("retirement", "Retirement", "woman", 5_000_000, 240,
                 "Very long horizon. Diversify; ignore short-term noise."),
]

TEEN_GOALS: list[GoalTemplate] = [
    GoalTemplate("college_fund", "College fund", "teen", 500_000, 36,
                 "Medium horizon. Teach SIP and compounding."),
    GoalTemplate("first_laptop", "First laptop", "teen", 80_000, 12,
                 "Short horizon. Lower-risk choices only."),
    GoalTemplate("gap_year", "Gap-year travel", "teen", 250_000, 24,
                 "Medium horizon. Balanced allocation."),
    GoalTemplate("first_salary_plan", "First-salary plan", "teen", 100_000, 18,
                 "Build the SIP habit early."),
    GoalTemplate("gift_for_parents", "Gift for parents", "teen", 50_000, 12,
                 "Short horizon. Capital preservation."),
]


def all_templates() -> list[GoalTemplate]:
    return WOMAN_GOALS + TEEN_GOALS


def for_persona(persona: Persona) -> list[GoalTemplate]:
    return WOMAN_GOALS if persona == "woman" else TEEN_GOALS


def find(key: str) -> GoalTemplate | None:
    for t in all_templates():
        if t.key == key:
            return t
    return None
