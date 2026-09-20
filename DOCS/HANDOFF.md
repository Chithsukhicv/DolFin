# DolFin — Full Project Handoff

**Last updated:** 31 August 2026  
**Prepared by:** Chith (lead) + Kiro  
**For:** Teammates picking up where we left off

This document covers everything that was built, in the order it was built, with an honest account of what works, what is only half-done, and what is not started yet. Read it before touching any file.

---

## Table of Contents

1. [What is this project](#1-what-is-this-project)
2. [How to run it](#2-how-to-run-it)
3. [Architecture overview](#3-architecture-overview)
4. [Phase 1 — Rule engine and core platform](#4-phase-1--rule-engine-and-core-platform)
5. [Phase 2 — Correctness fixes](#5-phase-2--correctness-fixes)
6. [Phase 3 — Learning experience](#6-phase-3--learning-experience)
7. [Phase 4 — AI reasoning layer and RAG](#7-phase-4--ai-reasoning-layer-and-rag)
8. [Phase 5 — Frontend redesign (in progress)](#8-phase-5--frontend-redesign-in-progress)
9. [What is verified working](#9-what-is-verified-working)
10. [What is yet to be done](#10-what-is-yet-to-be-done)
11. [Known bugs and gotchas](#11-known-bugs-and-gotchas)
12. [Numbers for the review panel](#12-numbers-for-the-review-panel)
13. [How to explain the architecture in a review](#13-how-to-explain-the-architecture-in-a-review)

---

## 1. What is this project

DolFin is a **behavioural investing simulator** for first-time Indian investors. The problem it solves is specific: the costliest beginner mistake is not picking the wrong stock, it is selling the right one in a panic. The product exists to give a learner the experience of watching their own portfolio fall 30%, feeling the urge to sell, and choosing not to — before it costs them anything.

**The core loop:**
1. You start with ₹1,00,000 of practice money
2. You browse real NSE prices and buy stocks
3. Before confirming any trade, a deterministic rule engine checks nine behavioural risk rules
4. If it fires, the AI coach explains the warning using your own history
5. You can confirm anyway or cancel and write down why
6. Your written reason is classified by the AI — the distinction between "the business hasn't changed" and "it'll bounce back tomorrow" is the whole lesson
7. A crash simulator drops prices 30% and the `panic_sell` rule blocks you from selling without acknowledgement
8. An Investment Readiness Score (0–100) grades your habits over time, not your luck

---

## 2. How to run it

### Prerequisites
- Python 3.11+ with `.venv` at `backend/.venv`
- Node.js 18+ with `node_modules` at `frontend/node_modules`
- A `backend/.env` file (copy from `.env.example` and fill in `GEMINI_API_KEY`)

### Start both servers (VS Code)
Press **`Ctrl+Shift+B`** — this runs both servers in parallel via `.vscode/tasks.json`.

### Manual start

```cmd
# Terminal 1 — backend
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Then open `http://localhost:3000`.

### Run the test suite

```cmd
cd backend
.venv\Scripts\python.exe -m pytest -q
```

449 tests, all should pass in ~30 seconds. No network calls — market feed and LLM are both stubbed.

### Run the live smoke test (needs the backend running)

```cmd
cd backend
.venv\Scripts\python.exe scripts/smoke_test.py
```

111 checks. Walks the full learner journey against real market data. Requires the server to be up.

### Check the database schema

```cmd
cd backend
.venv\Scripts\python.exe -m alembic current        # should print: 750d286dc8ca (head)
.venv\Scripts\python.exe -m scripts.check_schema   # should print: all good
```

### Gemini API key

The app is fully functional without a key — every AI feature has a deterministic fallback. To enable the AI layer:

1. Get a free key at https://aistudio.google.com/apikey (no credit card)
2. Copy `backend/.env.example` to `backend/.env`
3. Set `GEMINI_API_KEY=your-key`
4. Restart the backend
5. Verify at `http://127.0.0.1:8000/health` — `llm.configured` should be `true`

**Known model values that work with a fresh free-tier key** (as of Aug 2026):
- Generation: `gemini-3.5-flash` (~6s round trip)
- Embeddings: `models/gemini-embedding-001`
- Free tier ceiling: **5 requests/minute** (not 60 — the config reflects this)

Models named `gemini-1.5-flash` and `gemini-2.5-flash` are both retired and will 404.

---

## 3. Architecture overview

```
frontend/          Next.js 16 + Tailwind v4 + SWR
backend/
  app/
    routers/       49 FastAPI endpoints
    services/      business logic (no ORM queries here)
    data/          seed data — concepts, quizzes, stocks, knowledge
    models.py      18 SQLAlchemy tables
    main.py        app factory, startup hooks
  migrations/      Alembic — current head: 750d286dc8ca
  tests/           449 pytest tests
  scripts/         smoke_test, check_schema, api_inventory, reindex, audit_catalogue
data/
  dolfin.db        SQLite — main app database
  prices.db        SQLite — price cache (separate so a slow Yahoo call can't lock the app DB)
```

### The determinism boundary

This is the single most important architectural decision. **Rules measure, AI interprets. Never the reverse.**

- The **Intervention Engine** (`services/interventions.py`) — nine deterministic rules, each a threshold comparison. Identical input always produces identical output. Every finding carries `source: "rule"`.
- The **Readiness Score** (`services/readiness.py`) — reads only `intervention_logs`. Never reads `ai_findings`. This means AI output can never affect the score, even by accident.
- The **AI Reasoning Layer** — everything in `services/` prefixed with `llm_`, `coach`, `reflection_analyzer`, `pattern_analyzer`, `chatbot`, `quiz_generator`, `risk_reviewer`. Every finding carries `source: "ai"` and is stored in `ai_findings`, not `intervention_logs`.

The separation is enforced at the storage level (different tables), at the serialisation level (`source` field on every response), and at the test level (R18.5 in the spec asserts the score is unchanged when AI findings exist).

### The RAG pipeline

Two corpora stored in the `knowledge_chunks` table:

- **Corpus A** — DolFin's own material: 10 concept articles (split by section), 33 glossary terms, 30 quiz explanations, 9 rule definitions, 5 Indian-market context chunks, 5 behavioural-finance chunks. Indexed on every app boot (lexically, no network call). 139 chunks total.
- **Corpus B** — one learner's behavioural record: holdings, trades, warning outcomes by concept, quiz results, reflections, equity curve, active scenario. Built per-user after every trade, quiz, or reflection. Never contains email or display name.

The **Retriever** (`services/retrieval.py`) is the single path to any chunk. Scope-then-rank: access control runs before similarity scoring. Corpus B chunks are filtered to the requesting user's ID before any ranking happens — if ranking ran first, another learner's chunks could crowd the owner's own record out of the top-K.

The ranker is pluggable: lexical TF-IDF (no deps, works offline) or semantic (Gemini `embed_content`, 3072-dim vectors). Selected automatically based on whether embeddings are stored. Currently `ranking: "lexical"` — embeddings have never been computed because no key existed at build time.

---

## 4. Phase 1 — Rule engine and core platform

Built before this conversation. The foundation everything else rests on.

**Backend:**
- 9 intervention rules in `services/interventions.py`
- Portfolio buy/sell with P&L tracking
- 5-tier readiness score with confidence ramp
- Scenario simulator (crash/correction/rally/sideways)
- Goal templates by persona
- `prices.db` cache with stale-fallback
- 26 large-cap NSE stocks in the catalogue

**Frontend:**
- Onboarding → Dashboard → Market → Portfolio → Scenarios → Readiness → Coach
- `InterventionModal` for the coaching flow
- SWR throughout for data fetching

---

## 5. Phase 2 — Correctness fixes

Ten bugs where the app was saying one thing and doing another.

| # | Bug | Fix |
|---|---|---|
| 1 | "Cancel & reflect" did nothing or corrupted history | Warnings written at **preview** time with `preview_id`; resolved by that exact id |
| 2 | Quiz results were decorative | Wired `QuizAttempt` into readiness; `QUIZ_PASS_BONUS=6`, `QUIZ_BONUS_CAP=24`, once per concept |
| 3 | Heeding a warning still penalised you | Only `ignored` rows generate penalties |
| 4 | Panic selling **raised** the score | Fixed ordering: ramp then subtract; confirmed by test |
| 5 | First trade always fired CRITICAL | Concentration measured against total portfolio value, not invested value |
| 6 | Holdings vanished on quote failure | Falls back to cost basis; `price_stale`/`price_unavailable` flags on the row |
| 7 | Scenarios never expired | Lazy retirement when drawdown + recovery windows have both elapsed |
| 8 | `blocking` was cosmetic | 409 without `preview_id` for critical trades |
| 9 | Lost browser data = lost account | `GET /users/by-email/{email}` + recovery UI |
| 10 | NaN crashed preview with 500 | `dropna()`, `math.isfinite` guards, `_json_safe` backstop |

Files changed: `services/interventions.py`, `services/readiness.py`, `services/portfolio.py`, `services/scenarios.py`, `services/market.py`, `models.py`.

---

## 6. Phase 3 — Learning experience

**Concept library** (`/learn`)  
10 concepts, each with body sections, worked rupee examples, a named misconception, takeaways, related rules and a quiz link. `data/concepts_seed.py`.

**Guided learning path** (`/learn/path/{user_id}`)  
8 ordered steps computed from what the learner has actually done. Adaptive mode (Phase 4) reorders by demonstrated weaknesses when the AI layer is available.

**Equity curve** (`/history/equity/{user_id}`)  
One point per trade and per scenario boundary. The dip and recovery on your own portfolio is the product's core argument made visible.

**Price history charts**  
`/market/history/{symbol}` was already built; the frontend now renders it with period buttons and a drawdown callout.

**Quiz explanations**  
30 questions across 10 concepts, every question with an explanation. Went from 19 questions, 9 concepts, 2 single-question banks.

**Glossary** (`/learn/glossary`)  
33 terms. Available as inline `<Term>` tooltips on jargon in the UI.

**Expanded catalogue**  
35 instruments: 26 original large-caps + 5 index ETFs + 4 mid-caps. ETFs use a 60% concentration threshold (they are baskets, not single-company bets).

**Tata Motors → TMPV fix** (most recent change)  
`TATAMOTORS.NS` was retired after Tata's 2025 demerger. Replaced with `TMPV.NS`. Also rewrote `seed_if_empty` as `sync_catalogue` — it now updates changed metadata and **removes** retired symbols rather than only inserting new ones. Run `python scripts/audit_catalogue.py` any time Yahoo returns "possibly delisted" errors on a symbol.

---

## 7. Phase 4 — AI reasoning layer and RAG

The largest phase. Spec at `.kiro/specs/ai-reasoning-layer/requirements.md` (20 requirements, ~200 acceptance criteria).

### What is built and working

**`services/llm_gateway.py`** — The single chokepoint. Everything routes through `generate()`. Owns:
- `_call_model()` is the only function touching the network. Stubbed in every test.
- Safety constraint block appended last (after untrusted text, for injection resistance)
- Response screening: trade directives + price predictions, evaluating all checks before rejecting
- Prompt-hash cache with per-feature TTLs (15 min for coach/chat/reflection/risk, 24h for patterns/quizzes/path)
- 5/min budget (the real Gemini free-tier ceiling, measured empirically)
- 20s interactive / 45s deferred timeouts (measured: a real coach call takes ~6s)
- One retry, counted against the budget
- **Quota backoff:** a 429 from the API fills the local budget window immediately rather than retrying — one provider rejection used to trigger two more identical calls
- Bilingual support: Hindi detection via Devanagari ratio; English retry if Hindi call fails
- `language_fallback` flag on `GatewayResult` so callers know what language actually came back

**`services/coach.py`** — Context-aware coaching. Reads trade count, heed rate per concept, repeat-ignore count, goal horizon. Three distinct tones: repeat offender / strong track record / beginner. Offline fallback uses the same computed context.

**`services/reflection_analyzer.py`** — Classifies free-text reasoning as `sound` / `partly_sound` / `prediction_based`. Cites Corpus A. Keyword fallback (never returns nothing). Result persisted to `reflections` table in four new columns.

**`services/risk_reviewer.py`** — Second-opinion portfolio review. Runs in `BackgroundTasks` after the preview response is sent. Finds correlated exposure, goal-horizon mismatch, repeat losses in one symbol. `_completed` dict distinguishes "still working" from "finished with nothing to add". Results in `ai_findings` table, never in `intervention_logs`.

**`services/pattern_analyzer.py`** — Names recurring patterns across whole history. Cache fingerprinted on four record counts (txn, resolved warnings, quiz attempts, reflections). Returns "insufficient activity" with no model call when fewer than 3 trades AND fewer than 1 resolved warning. Fallback builds a counted summary from rule outcomes. R5.5 backstop: if the model returned only criticism but the record shows a concept heeded ≥50%, a strength is added.

**`services/chatbot.py`** — Grounded Q&A. Retrieves from Corpus A and Corpus B in two separate calls (so a strong library hit can't crowd the learner's own record out of top-K). Declines with a reading list when nothing clears the relevance floor — no model call. Stores every question/answer with citations against a `ChatSession`. Injection prevention: the question is marked `untrusted`, retrieval uses only the `user_id` from the request.

**`services/quiz_generator.py`** — Generates fresh questions grounded in Corpus A. 5 quality checks per question (length, distinct options, concept mention, answer range, explanation length). Discard-and-substitute: failed questions replaced by seeded ones, never shown. Server-side scoring: answers stored against `GeneratedQuestion.id`, client never holds the answer key.

**`services/learning_path.py`** — Adaptive ordering. Weakness = `(ignored_warnings × 2) + failed_quizzes`. Remedial steps for top-scored weak concepts, linked to real Corpus A material. Falls back to fixed 8-step sequence when gateway unavailable. `done` always computed deterministically.

**`services/indexer.py`** — Corpus A indexed on every boot (lexically, zero network). `refresh_corpus_b` called after every trade, quiz, reflection, and reset. `sync_catalogue` reconciles the stocks table (insert + update + remove retired, skip symbols still held). `document_text()` ranks on title + body so "Your current holdings" appears when asked about holdings.

**`services/ranking.py`** — IDF floored at 1.0 (not 0) to prevent universal-term collapse in small Corpus B sets. The `embed_texts` seam is stubbed in every test.

**Routers added:** `/coach/patterns`, `/coach/evidence`, `/chat/ask`, `/chat/sessions`, `/chat/topics`, and the adaptive quiz endpoints under `/quizzes/adaptive`.

**`DELETE /users/{user_id}`** — Cleans up `ChatSession`, `ChatMessage`, `AIFinding`, `PatternAnalysis`, `GeneratedQuestion`, `Reflection`, `QuizAttempt`, `ReadinessSnapshot`, `PortfolioSnapshot`, `Scenario`, and Corpus B chunks. Needed because Corpus B is a copy — deleting the source rows leaves the chunks describing someone who no longer exists.

**Migration `750d286dc8ca`** — Adds 4 columns to `reflections`: `reasoning_class`, `ai_response`, `ai_citations`, `ai_mode`.

**Corpus A at boot** — 139 chunks indexed lexically on startup. `/health` reports `corpora.corpus_a` and `corpora.ranking`. A zero count means the RAG layer is not actually grounded.

**Source flagging on the wire** — `Intervention.to_dict()` now includes `source: "rule"`. `GET /history/interventions` likewise. Every AI output carries `source: "ai"`. The frontend can always tell which kind of finding it is looking at without knowing which array it came from.

### New tables (18 total)

| Table | Purpose |
|---|---|
| `knowledge_chunks` | Both RAG corpora |
| `ai_findings` | Advisory AI findings (risk review, pattern) |
| `pattern_analyses` | Cached whole-history analyses |
| `chat_sessions` | Chatbot conversation containers |
| `chat_messages` | Individual turns with citations |
| `generated_questions` | AI quiz questions, answer key server-side |

### Frontend — AI-specific components

**`AiLabel.tsx`** — `AiBadge`, `AiDisclaimer`, `Citations`. Placed on every AI surface. The disclaimer is not decoration: this app shows live NSE prices and portfolio commentary, which is close enough to advice that the educational distinction needs permanent labelling.

**`AiFindingsPanel.tsx`** — Polls `/portfolio/preview/{id}/ai-findings`. 15-second spinner (R13.10), then quiet background polling for up to 60 seconds (R13.11 — late findings append rather than being lost).

**`PatternPanel.tsx`** — Shows named habits with evidence. Strengths listed last. Collapsible raw evidence table so every number in a pattern can be traced back.

**`ReflectionHistory.tsx`** — Past reflections with their AI assessments persisted. The assessment used to exist for one screen; now it is reviewable any time on the Coach page.

**`RetestPanel.tsx`** — Lists failed concepts and links to the adaptive quiz for each. Uses `GET /quizzes/adaptive/{user_id}`.

**`/ask` page** — Full chatbot UI with session history, citation expand/collapse, and suggested prompts. "Ask" tab in the nav carries a violet dot to mark it as generative.

**`/coach/quiz/[concept]` page** — Now has a "Fresh questions" toggle that fetches from the adaptive generator rather than the seeded bank.

---

## 8. Phase 5 — Frontend redesign (in progress)

**Status: partially complete. Inner pages are broken.**

### What was changed

**Design system (`globals.css`):**  
Dark theme built against Material Design dark-mode rules rather than by eye. Three previous mistakes fixed:
1. Background `#06070d` → `#121418` (near-black causes halation; dark grey lets elevation read as "lighter")
2. Saturated accents removed (they vibrate on dark surfaces) → 300-tone desaturated palette
3. Muted text contrast raised from ~3.5:1 to ~5.4:1 (WCAG minimum is 4.5:1)

Elevation is now lightness-based (`--elev-1` through `--elev-4`) rather than shadow-based. Drop shadows are swallowed by dark backgrounds.

**Three fonts:**
- **Sora** (display, headings) — geometric, holds up at large hero sizes
- **Inter** (body) — most legible at 13–15px
- **JetBrains Mono** (numbers) — tabular figures, so portfolio values don't jitter horizontally as they update

**Custom classes defined in CSS** (not Tailwind utility classes):
- `.card` — elevation-1 background, hairline border
- `.card-interactive` — hover lift to elevation-2
- `.card-raised` — for modals and the signup card
- `.glass` — frosted nav
- `.btn-primary`, `.btn-ghost`
- `.metric` — mono font, tabular figures
- `.label` — uppercase mono, 5.4:1 contrast
- `.grid-bg` — faint blueprint grid behind everything
- `.skeleton` — shimmer loading state
- `.animate-rise`, `.stagger` — entrance animations

**Pages converted to the new design system:**
- Landing page (`/`) — hero, signup form, footer
- Nav — collapses to a sheet below `lg`
- Footer — permanent educational disclaimer

### What is NOT converted

Every inner page still has light-theme Tailwind classes baked in: `bg-white`, `text-slate-900`, `border-slate-200`, `hover:bg-slate-50`, etc. They render but look wrong — light panels on a dark background, low-contrast text, the intervention modal is still `bg-white`.

**Files that need converting:**
- `src/app/dashboard/page.tsx`
- `src/app/market/page.tsx`
- `src/app/portfolio/page.tsx`
- `src/app/readiness/page.tsx`
- `src/app/scenarios/page.tsx`
- `src/app/learn/page.tsx` and `src/app/learn/[concept]/page.tsx`
- `src/components/InterventionModal.tsx` — still `bg-white` on the dialog
- `src/components/LearningPath.tsx` — still `bg-white` and `text-slate-900` on step cards
- `src/components/PriceChart.tsx` — light range buttons
- `src/components/EquityCurve.tsx` — light text on values
- `src/components/ScenarioBanner.tsx` — light tone classes
- `src/components/AiLabel.tsx` — `bg-slate-100` on the offline badge
- `src/components/PatternPanel.tsx` — several `text-slate-*` on pattern cards
- `src/components/ReflectionHistory.tsx` — partly-sound tone still uses `bg-slate-50`
- `src/components/RetestPanel.tsx` — `bg-white` on concept links
- `src/app/coach/page.tsx` — concept list items still light-theme
- `src/app/coach/quiz/[concept]/page.tsx` — quiz options still `border-slate-200 bg-indigo-50`

### How to convert a component

Replace light-theme classes with the dark equivalents:

| Light | Dark |
|---|---|
| `bg-white` | `bg-elevated` or `card` class |
| `bg-slate-50`, `bg-slate-100` | `bg-surface-muted`, `bg-elev-2` |
| `text-slate-900`, `text-slate-800` | `text-fg` or `text-white` |
| `text-slate-700`, `text-slate-600` | `text-muted` |
| `text-slate-500`, `text-slate-400` | `text-subtle` |
| `border-slate-200`, `border-slate-300` | `border-hairline`, `border-hairline-strong` |
| `hover:bg-slate-50` | `hover:bg-surface-hover` |
| `bg-indigo-50` | `bg-indigo-500/15` |
| `text-indigo-700`, `text-indigo-600` | `text-indigo-300`, `text-brand` |
| `bg-emerald-50` | `bg-emerald-500/10` |
| `text-emerald-700` | `text-emerald-300` or `text-pos` |
| `bg-amber-50` | `bg-amber-500/10` |
| `text-amber-800` | `text-amber-300` or `text-warn` |
| `bg-red-50`, `bg-rose-50` | `bg-rose-500/10` |
| `text-red-700`, `text-rose-700` | `text-rose-300` or `text-neg` |

The `severityClasses()` function in `lib/format.ts` also returns light-theme classes — update it for the dark tokens and all intervention panels will convert at once.

---

## 9. What is verified working

Verified by tests and a live smoke run. These are facts, not claims.

**Backend:**
- 449 unit tests, 0 failures, ~30s, fully offline
- 111 live smoke checks against a real server, 0 failures
- `alembic current` shows `750d286dc8ca (head)`
- `scripts/check_schema.py` shows all 21 checks PASS
- `TATAMOTORS.NS` removed, `TMPV.NS` present and priceable
- `/health` reports `corpora.corpus_a: 139` and `corpora.ranking: "lexical"` on a cold start
- With a real Gemini key: `_call_model` returns a real coaching message in ~6s, embeddings return 3072-dim vectors, both corpora are used in chatbot answers

**Frontend:**
- `tsc --noEmit` clean
- `eslint` clean (0 errors, 0 warnings)
- `npm run build` succeeds (Next.js production build)
- Landing page, nav, footer render in the new dark theme
- Inner pages render but have light-theme colour conflicts (see Phase 5)

---

## 10. What is yet to be done

### P0 — Must do before deployment

**1. Complete the frontend dark-theme conversion**  
Every inner page listed in Phase 5 needs its light-theme Tailwind classes replaced. The `severityClasses()` function in `lib/format.ts` is the highest-value single change — it drives all intervention panels. Estimated: 1 full day.

**2. Deploy-safe database**  
SQLite is not suitable for any hosted tier. The file is wiped on every Render/Railway container restart. Two options:
- **Postgres (easiest):** Change `DATABASE_URL` in `.env`. SQLAlchemy is already the ORM; the only code change is the connection string. Use `asyncpg` for async or `psycopg2` for sync. Render's free Postgres instance works for demo use.
- **Firestore (planned):** Larger migration — 18 tables of SQLAlchemy queries need rewriting to Firestore collections. Boundary is drawn cleanly (each service owns its own queries), but it is a week of work.

**3. Real authentication**  
`user_id` is currently a request body parameter. Any client that knows a UUID can read that portfolio. Firebase Auth is the documented path — user gets a JWT at login, the backend verifies it, and the `user_id` comes from the verified token rather than the request body.

**4. Semantic embeddings**  
Retrieval currently uses TF-IDF. Semantic ranking is fully built (`EmbeddingRanker`, `embed_texts`, `_attach_embeddings`) but the vectors have never been computed because no key existed until the last session. With a key active, run:
```cmd
cd backend
.venv\Scripts\python.exe -m scripts.reindex
```
This runs `reindex_corpus_a(db, embed=True)` — 139 API calls to `gemini-embedding-001`. After this, `/health` should show `embedded: 139` and `ranking: "embedding"`.

### P1 — Should do before the review demo

**5. CORS for production**  
`CORS_ORIGINS` is currently hardcoded to `localhost:3000`. Add your production frontend URL before deploying.

**6. Catalogue audit**  
Run `python scripts/audit_catalogue.py` against the live feed before the demo. Corporate actions (delistings, mergers, symbol changes) happen without notice. `TATAMOTORS.NS` was the most recent casualty. The script prints every dead symbol.

**7. Gemini quota strategy for the demo**  
Free tier is 5 requests/minute. If reviewers click through six AI features quickly, the last few will show offline output. The gateway handles this correctly (degrades gracefully, never errors), but it looks like a broken feature to someone who doesn't know what `mode: "offline"` means. Options:
- Pay ₹200 to add a credit card and use the paid tier (much higher quota)
- Walk through features in order with ~15-second pauses between them
- Demo on a prepared account that has already generated and cached the key responses

**8. `reflections.reason` stored verbatim, truncated in prompts**  
Already implemented (R16.9). Confirm it works end-to-end with a real key: type a reason in the reflect modal, check `/reflections/user/{id}` to confirm the full text is stored, check that the AI response classifies it correctly.

### P2 — Nice to have

**9. Hindi UI strings**  
`users.language` is stored and respected by the AI layer (coach message, chatbot, reflection, pattern analysis are all in Hindi when `language: "hi"`). Every static UI string is hardcoded English. Needs `next-intl` or a simpler `t()` wrapper and ~150 strings translated.

**10. Frontend tests**  
Backend has 449 tests. Frontend has type-checking and linting only. Playwright is the natural choice — it tests what the user actually sees, including the intervention modal flow and the chatbot conversation.

**11. Goals — progress view and editing**  
Goals are set at onboarding and used for a coarse alignment heuristic in the readiness score. There is no screen showing "you set a goal of ₹2,00,000 for a car, your portfolio is currently ₹1,10,000, you are on track". The data is all there; it just needs a component.

**12. Dashboard AI nudges**  
The pattern analysis runs on the Coach page. A one-line summary ("You've overridden the panic-sell warning 3 times this week") as a dashboard nudge would surface the most important behavioural insight without requiring the learner to navigate to a separate page.

**13. Reflections in the reflect modal should offer a follow-up chat**  
When the AI assessment comes back in step 3 of the modal ("Right call, shaky reason"), there is no way to ask a follow-up question. A "Ask DolFin about this" button that opens the chatbot with the reflection context pre-loaded would close that loop.

---

## 11. Known bugs and gotchas

**Gemini model availability**  
Model names change and retired ones fail with a 404 that surfaces as a 500 at request time (not startup time). The current working models were verified against a real key on 31 Aug 2026: `gemini-3.5-flash` for generation, `models/gemini-embedding-001` for embeddings. Check `.env.example` for notes. Before any demo, verify at `/health`.

**`embed_content()` requires the `models/` prefix**  
`genai.GenerativeModel("gemini-3.5-flash")` adds the prefix automatically. `genai.embed_content(model="gemini-embedding-001", ...)` does not — it raises a `ValueError` that the gateway swallows as "embeddings unavailable" and silently falls back to lexical ranking. The correct value is `models/gemini-embedding-001`. This is set correctly in `.env` and `config.py`, but watch for it if you change the model name.

**TATAMOTORS.NS is dead**  
Tata Motors demerged in 2025. `TATAMOTORS.NS` returns "symbol may be delisted" from Yahoo. Replaced by `TMPV.NS` in the seed. If the smoke test reports a dead symbol, run `python scripts/audit_catalogue.py` to find it.

**5 requests/minute on the free tier**  
This is the real Gemini free-tier ceiling, confirmed by the API's own error message (`GenerateRequestsPerMinutePerProjectPerModel-FreeTier, limit: 5`). The gateway degrades gracefully when the budget is exhausted, but features will show `mode: "offline"` output if you use them faster than once every 12 seconds. The gateway sets `LLM_REQUESTS_PER_MINUTE=5` as the default. Do not raise this without a paid plan.

**OneDrive file locks**  
The project lives at `C:\Users\chith\OneDrive\Desktop\DolFin`. OneDrive syncs `.next` (Next.js build output), causing `EPERM: operation not permitted, unlink` errors during `npm run build`. Fix: stop the dev server before building, or clear `.next` manually first. Long-term fix: move the repo to `C:\dev\DolFin` outside OneDrive.

**`useSyncExternalStore` and localStorage**  
User identity is stored in `localStorage` and read via `useSyncExternalStore` in `lib/useSession.ts`. Clearing browser data loses the session. `GET /users/by-email/{email}` is the recovery path. When Firebase Auth is added, the localStorage approach should be removed entirely.

**No server-side error logging**  
`uvicorn` prints errors to stdout; nothing is sent to Sentry or any aggregator. In the current dev setup this is fine. Before a production deploy, wire `fastapi` exceptions into a logging service.

---

## 12. Numbers for the review panel

| Metric | Value |
|---|---|
| Backend tests | 449 (unit) + 111 (live smoke) |
| API endpoints | 49 |
| Database tables | 18 |
| Alembic migrations | 2 (baseline + reflection analysis columns) |
| Quiz questions | 30 across 10 concepts |
| Tradeable instruments | 35 (26 large-cap + 4 mid-cap + 5 index ETFs) |
| Concepts in the library | 10 |
| Glossary terms | 33 |
| Corpus A chunks | 139 |
| RAG retrieval budget/min | 5 |
| Measured round-trip latency | ~6s (gemini-3.5-flash, coach prompt) |
| Frontend lint errors | 0 |
| Frontend type errors | 0 |

---

## 13. How to explain the architecture in a review

The answer that holds up is not "we built 49 endpoints." It is the design decisions:

**"Why rules and not just AI?"**  
Rules are arithmetic comparisons. The same trade must produce the same warning every time — a learner's Readiness Score depends on it. An LLM computing "is 25% too much?" would be non-deterministic and untestable. We use rules for measurement and AI for judgment, with a hard boundary enforced at the storage level.

**"Where is the AI actually doing work?"**  
Six specific jobs that are provably impossible with rules:
1. Reading free text (reflection analysis — no threshold encodes the difference between "the business hasn't changed" and "it'll bounce back tomorrow")
2. Reading across time (pattern analysis — naming a 6-week habit requires synthesising 20 rows of history)
3. Goal-horizon mismatch detection (risk review — requires understanding that a 6-month goal and a 60% small-cap portfolio are a problem together)
4. Grounded free-form Q&A (chatbot — grounds answers in DolFin's own material and the learner's own record, declining when it has no material)
5. Fresh assessment questions (quiz generator — prevents memorisation, grounded in the same Corpus A the concept pages are written from)
6. Personalised learning path ordering (learning path — sorts by demonstrated weaknesses rather than fixed sequence)

**"What is RAG giving you that a general model can't?"**  
Two things. First, DolFin's own rule definitions — the chatbot can answer "why did you warn me about that trade?" from the actual threshold rather than guessing. Second, the learner's own record (Corpus B) — "you have overridden this warning four times" exists in no model's training data. That is the grounding that makes an answer specific rather than generic.

**"How do you prevent one learner's data reaching another learner's prompt?"**  
Single enforcement point: the Retriever scopes the candidate set before any ranking happens. Ranking across all candidates and filtering afterwards would apply top-K before the owner filter — another learner's chunks could crowd the owner's own record out. We scope first, rank second. A defence-in-depth post-filter logs a SECURITY event and discards any mismatch that gets through. Both are tested.

---

*For the full spec, see `.kiro/specs/ai-reasoning-layer/requirements.md`.*  
*For the original interview prep material, see `INTERVIEW-PREP.md`, `INTERVIEW-PREP-PART2.md`, `INTERVIEW-PREP-PART3.md`.*
