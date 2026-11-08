# Readiness Score V2

## Score and weights

When the record is assessable, the overall score is the weighted mean of the
available dimension estimates. Configured weights are normalized over the
dimensions with an estimate; `effective_weights` reports the resulting weights.
The defaults total 100%:

| Dimension | Weight |
| --- | ---: |
| Diversification | 25% |
| Discipline | 25% |
| Goal alignment | 15% |
| Autonomy | 10% |
| Consistency | 15% |
| Engagement | 10% |

These defaults live in `backend/app/config.py` and can be overridden through
the matching `READINESS_WEIGHT_*` environment variables. The settings validator
requires the weights to sum to 1.0. The graduation threshold remains 80.

The overall numeric score is withheld (`score: null`) until there are at least
12 valid trades and 5 distinct trade dates in the last 60 days, at least 8
current holdings, and a recent trade history spanning at least 14 UTC dates.
This is an evidence gate, not a penalty or a score ceiling. During cold start,
dimension estimates, evidence counts and practice achievements remain visible.
An unassessable score is not presented as zero or as risky behaviour.

Graduation also requires sufficient evidence for diversification, discipline,
goal alignment, autonomy and consistency. Without a goal, goal alignment is
unobserved and graduation is not eligible. Historical snapshots are untouched;
new snapshots carry `version: 2` and are only written for assessable scores.
Legacy snapshots have no version marker and retain their original meaning.

## Dimension calculations

- **Diversification:** `60 + min(8 × distinct sectors, 40)`, minus a position
  penalty of `100 × (max position share − 0.20)` above 20%, and a sector penalty
  of `80 × (max sector share − 0.40)` above 40%; clamped to 0–100. No holding or
  zero market value means no estimate.
- **Discipline:** 50 when no warnings were observed, otherwise 70; plus 5 per
  heeded warning up to 30, plus 6 per distinct passed quiz concept up to 24;
  subtract 20 per ignored panic-sell, 10 per ignored FOMO, and 5 per ignored
  short-hold warning; clamped to 0–100. Pending warnings are neither good nor
  bad evidence. Quiz credit supplements but does not replace observed conduct.
- **Goal alignment:** starts at 70; add 10 for an average horizon from 12 to 60
  months, subtract 25 for a 60+ month horizon with more than 30 trades, and
  subtract 15 for a horizon below 12 months with more than 5 holdings. No goal
  or no trades means unobserved.
- **Autonomy:** over the last 60 days, Laplace-smoothed clean-trade rate using a
  prior of 6 trades at 50%: `(clean trades + 3) / (trades + 6) × 100`. No recent
  trades means unobserved.
- **Consistency:** `min(rolling-30-day qualifying practice dates / 8 × 100, 100)`.
  Eight distinct dates is the target of roughly two practice days per week.
- **Engagement:** `min(lifetime distinct qualifying dates / 10 × 100, 100)`.
  Trade count within a session does not increase this value.

The behavior state is `insufficient_evidence` until the overall evidence gate
is met. With sufficient history, discipline or autonomy at 35 or below is
labelled `demonstrated_risky_behaviour`; otherwise it is
`adequate_neutral_or_positive_evidence`. That state is separate from the
overall score and graduation eligibility.

## Practice dates and streaks

UTC is the canonical day boundary because existing timestamps are created in
UTC and `User` has no timezone preference. Naive timestamps returned by SQLite
are interpreted as UTC. Future, missing, malformed and invalid trades are
excluded. Qualifying dates are deduplicated across:

- Valid buy/sell transactions (positive finite quantity and price).
- Persisted completed quiz attempts, including failed attempts; practice
  consistency measures showing up, not answer quality.
- Persisted reflection records written by the reflection endpoint. Optional
  reflection text is not read by the scorer.

Logins, page views, readiness refreshes and portfolio polls do not qualify.
`InterventionLog.created_at` is the warning preview time, not when a learner
resolves it, so it is not used to assign a practice date. Resolved warning
outcomes still feed discipline. Current streak allows today or yesterday as the
latest qualifying date; a longer gap resets the current streak but preserves
the historical longest streak. The rolling window includes today and the prior
29 UTC dates. Lifetime practice rate is qualifying dates divided by the
inclusive span from first to last qualifying date.

## Behavioural intelligence boundary

`behavioral_ml.py` provides a per-user longitudinal outlier check for daily
trade frequency. It requires 20 trades and 6 trade dates in the recent 60-day
window, uses the learner's own previous five-or-more trade days as a median/MAD
baseline, and flags a recent robust z-score of at least 3.5. The result is an
advisory novelty signal only: an unusual burst is not inherently harmful and
cannot affect readiness.

The repository has no representative, labelled multi-user outcome data and no
validated model for predicting readiness. This detector is a lightweight
unsupervised statistical method, not a trained predictive model. It returns no
numeric dimension estimate. The evidence aggregator supports a configurable
50/50 blend only for `discipline` and `autonomy`, the configured candidate
dimensions, and only when both deterministic and ML estimates are valid and
sufficient. Since the current anomaly detector is not a score estimator, the
dimension contributions explicitly fall back to deterministic estimates; no
ML value is invented or treated as zero. Gemini remains an explanation layer
and is never called by scoring.

## Persistence and API

No schema migration is required: practice dates are derived from existing
user-scoped records. `GET /readiness/{user_id}` keeps the existing response
fields and adds `score_version`, assessment and behaviour states, per-dimension
evidence/contributions, effective weights, practice dates/streaks, evidence
needed, and advisory anomaly output. The score may now be null until sufficient
evidence exists. `POST /readiness/{user_id}/snapshot` does not persist an
unassessable result; it reports `snapshot_recorded: false`. New assessable
snapshots are versioned in their JSON breakdown. Existing snapshots are not
rewritten.
