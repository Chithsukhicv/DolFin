# DolFin

A gamified investment learning and portfolio intelligence platform for women and teenagers in India.

## What makes DolFin different

- **Behavioural Intervention Engine** — real-time coaching at the moment of every trade decision, not after-the-fact Q&A.
- **Investment Readiness Score (0–100)** — a graduation metric that tracks when a user is ready to invest with real money.
- **Persona-aware, goal-driven simulation** — purpose-built for women (independence, education, travel) and teens (college fund, first salary), with Hindi + English at v1.
- **Market scenario simulator** — practise patience during a -30% crash without losing real money.

## Repo layout

```
DolFin/
├── backend/        FastAPI service (Python 3.11)
├── frontend/       Next.js 16 + TypeScript + Tailwind 4
├── DolFin.pdf      Project pitch (Phase I, Review 2)
├── Competitive-Analysis.md
└── README.md
```

## Tech stack

| Layer    | Choice                                          |
|----------|-------------------------------------------------|
| Frontend | Next.js (App Router) + TypeScript + Tailwind 4 + Recharts + SWR |
| Backend  | FastAPI, Python 3.11                            |
| Auth     | Local stub today, Firebase Auth swap-in next   |
| Database | SQLite (dev), Firestore-ready models           |
| Market   | yfinance + curl_cffi (NSE `.NS`, BSE `.BO`)    |
| AI       | Google Gemini (with offline rule-based fallback) |

## Run locally

### 1. Backend (port 8000)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env       # optional — fill in Gemini key for live AI coach
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs.

### 2. Frontend (port 3000)

```powershell
cd frontend
npm install
npm run dev
```

App: http://127.0.0.1:3000.

## Backend API surface

| Group          | Endpoints                                                                |
|----------------|--------------------------------------------------------------------------|
| Health         | `GET /health`                                                            |
| Market         | `GET /market/quote/{symbol}`, `GET /market/quotes`, `GET /market/history/{symbol}` |
| Catalog        | `GET /catalog/stocks`, `GET /catalog/sectors`                            |
| Users          | `POST /users`, `GET /users/{id}`, `POST /users/{id}/reset`               |
| Goals          | `GET /goals/templates`, `POST /goals`, `GET /goals/user/{id}`            |
| Portfolio      | `GET /portfolio/{id}`, `POST /portfolio/preview`, `POST /portfolio/buy`, `POST /portfolio/sell` |
| Scenarios      | `POST /scenarios/start`, `POST /scenarios/stop`, `GET /scenarios/active/{id}`, `GET /scenarios/presets` |
| Readiness      | `GET /readiness/{id}`, `POST /readiness/{id}/snapshot`                   |
| Quizzes        | `GET /quizzes/{concept}`, `POST /quizzes/submit`, `GET /quizzes/user/{id}` |
| Reflections    | `POST /reflections`, `GET /reflections/user/{id}`                        |
| History        | `GET /history/transactions/{id}`, `GET /history/interventions/{id}`, `GET /history/readiness/{id}` |

## Behavioural rules

Buy-side: `concentration`, `sector_overlap`, `volatility_mismatch`, `fomo`, `cash_drain`, `buy_during_rally`.
Sell-side: `panic_sell` (the headline), `loss_lock_in`, `short_hold`.

## Smoke test

While the backend is running:

```powershell
cd backend
.venv\Scripts\python.exe scripts\smoke_test.py
```

Walks through user creation → goal → buy → crash → panic-sell preview → readiness.

## Team

Batch 18 — Chithsukhi C V, E R Sunidhi, Harini P, Manya C
Guides — Dr. Asha Rani M, Mrs. Pavithra Gowtham N S
