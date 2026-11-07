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

| Group              | Endpoints                                                                |
|--------------------|--------------------------------------------------------------------------|
| Health             | `GET /health`                                                            |
| Market             | `GET /market/quote/{symbol}`, `GET /market/quotes`, `GET /market/history/{symbol}` |
| **Market ML**      | **`GET /market-ml/{symbol}/forecast`**                                   |
| Catalog            | `GET /catalog/stocks`, `GET /catalog/sectors`                            |
| Users              | `POST /users`, `GET /users/{id}`, `POST /users/{id}/reset`               |
| Goals              | `GET /goals/templates`, `POST /goals`, `GET /goals/user/{id}`            |
| Portfolio          | `GET /portfolio/{id}`, `POST /portfolio/preview`, `POST /portfolio/buy`, `POST /portfolio/sell` |
| Scenarios          | `POST /scenarios/start`, `POST /scenarios/stop`, `GET /scenarios/active/{id}`, `GET /scenarios/presets` |
| Readiness          | `GET /readiness/{id}`, `POST /readiness/{id}/snapshot`                   |
| Quizzes            | `GET /quizzes/{concept}`, `POST /quizzes/submit`, `GET /quizzes/user/{id}` |
| Reflections        | `POST /reflections`, `GET /reflections/user/{id}`                        |
| History            | `GET /history/transactions/{id}`, `GET /history/interventions/{id}`, `GET /history/readiness/{id}` |

---

## Market Movement Predictor

> ⚠️ **Experimental educational feature. Not financial advice.** This module is intended to teach learners how ML-based direction classifiers work, not to guide real investment decisions. Past model output does not guarantee future results. The model may perform at or below random chance.

### Purpose

The Market Movement Predictor classifies short-term directional price movement (UP / SIDEWAYS / DOWN) for NSE-listed symbols across four forecast horizons: 1, 3, 5, and 10 trading days. It does not predict exact prices or guaranteed returns.

### Architecture and data flow

```
GET /market-ml/{symbol}/forecast
         │
         ▼
   routers/market_ml.py          ← validates input, handles HTTP errors
         │
         ▼
   services/market_ml.py         ← engineer_features(), get_forecast()
         │                           lazy-loads .joblib artifacts from data/models/
         ▼
   services/market.get_history() ← period="6mo", interval="1d"
         │
         ▼
   MarketForecastResponse         ← 4 HorizonForecast items, always with disclaimer
```

Training (offline, not on the API path):

```
python -m app.services.market_ml_training
         │
         ▼
   market.get_history()           ← period="2y", interval="1d"
         │
         ▼
   WalkForwardValidator           ← chronological folds, purge gap = horizon bars
         │
         ▼
   LR baseline + GBM candidate    ← best by avg balanced accuracy across folds
         │
         ▼
   data/models/NSE_ALL_Nd_arch.joblib + .json
```

### Feature definitions (23 columns)

| Column | Description | Window |
|--------|-------------|--------|
| `ret_1d` – `ret_10d` | Close-price pct-change returns | 1, 3, 5, 10 bars |
| `sma_5` – `sma_50` | Simple moving averages | 5, 10, 20, 50 bars |
| `ema_12`, `ema_26` | Exponential moving averages | span 12, 26 |
| `macd`, `macd_signal`, `macd_hist` | MACD line, signal, histogram | 12/26/9 |
| `rsi_14` | RSI (Wilder smoothing) | 14 bars |
| `vol_5` – `vol_20` | Rolling volatility of log-returns | 5, 10, 20 bars |
| `atr_14` | Average True Range (Wilder) | 14 bars |
| `vol_chg`, `rel_vol` | Volume % change; volume / 20-day avg | 1, 20 bars |
| `roc_5` – `roc_20` | Rate of change (momentum) | 5, 10, 20 bars |

All indicators are computed with pandas / NumPy only — no ta-lib or pandas-ta dependency.

### Target label definitions

| Label | Condition |
|-------|-----------|
| `UP` | Forward close return > threshold |
| `DOWN` | Forward close return < −threshold |
| `SIDEWAYS` | Return within [−threshold, +threshold] |

Default thresholds (configurable via `.env`):

| Horizon | Default threshold |
|---------|-------------------|
| 1 day   | ±1.0% |
| 3 days  | ±1.5% |
| 5 days  | ±2.0% |
| 10 days | ±2.5% |

### Model choices

| Architecture | Role | Library |
|---|---|---|
| `LogisticRegression` (C=1, lbfgs) | Interpretable baseline | scikit-learn |
| `GradientBoostingClassifier` (200 trees, depth 3, lr 0.05) | Main candidate | scikit-learn |

Both architectures are compared per horizon. The winner (higher average balanced accuracy across walk-forward folds) is saved.

### Training instructions

```powershell
cd backend
pip install -r requirements.txt        # installs scikit-learn==1.6.1

# Train all 4 horizons using broad-market proxy (NIFTYBEES.NS for NSE_ALL scope)
python -m app.services.market_ml_training

# Train a specific symbol and horizon
python -m app.services.market_ml_training --symbol TCS.NS --horizon 1 3

# Force only the baseline model
python -m app.services.market_ml_training --arch lr

# Force only GradientBoosting
python -m app.services.market_ml_training --arch gbm
```

Artifacts are written to `backend/data/models/` (excluded from git — see `.gitignore`).

### Walk-forward validation methodology

Financial time-series data must not be split randomly. A model trained on data that includes the future of its test set will appear to perform well in evaluation but will be worthless in production.

The `WalkForwardValidator` splits the labeled dataset into strictly ordered folds:

1. **Initial training set** — first 60% of labeled bars.
2. **Purge gap** — `horizon` bars are removed between the end of each training fold and the start of its validation fold. This prevents the overlapping forward-return windows of multi-day labels from leaking future information.
3. **Validation fold** — the next slice is evaluated with the scaler fitted only on training data.
4. **Final holdout** — last 20% of bars, untouched during cross-validation; used only for the evaluation report.

Random cross-validation (`sklearn.model_selection.cross_val_score` etc.) must never be used on financial time-series because it mixes past and future observations.

### API usage

```
GET /market-ml/{symbol}/forecast
```

**Path parameter:** `symbol` — 1–20 characters, e.g. `TCS.NS`, `RELIANCE`.  
Symbols without an exchange suffix are treated as NSE (`.NS` appended automatically).

**Example response (HTTP 200):**

```json
{
  "symbol": "TCS.NS",
  "fetched_at": 1737020400,
  "disclaimer": "Experimental educational feature. Not financial advice.",
  "horizons": [
    {
      "horizon_days": 1,
      "predicted_class": "UP",
      "prob_up": 0.52,
      "prob_sideways": 0.31,
      "prob_down": 0.17,
      "uncertainty_flag": false,
      "model_status": "ok",
      "model_training_date": "2025-01-10",
      "is_stale": false
    },
    {
      "horizon_days": 3,
      "predicted_class": "SIDEWAYS",
      "prob_up": 0.28,
      "prob_sideways": 0.44,
      "prob_down": 0.28,
      "uncertainty_flag": true,
      "model_status": "ok",
      "model_training_date": "2025-01-10",
      "is_stale": false
    },
    {
      "horizon_days": 5,
      "predicted_class": null,
      "prob_up": null,
      "prob_sideways": null,
      "prob_down": null,
      "uncertainty_flag": false,
      "model_status": "not_trained",
      "model_training_date": null,
      "is_stale": false
    },
    {
      "horizon_days": 10,
      "predicted_class": null,
      "prob_up": null,
      "prob_sideways": null,
      "prob_down": null,
      "uncertainty_flag": false,
      "model_status": "not_trained",
      "model_training_date": null,
      "is_stale": false
    }
  ]
}
```

**`model_status` values:**

| Value | Meaning |
|---|---|
| `ok` | Model loaded, probabilities are current |
| `stale` | Model artifact is older than `MARKET_ML_STALENESS_DAYS` days |
| `not_trained` | No `.joblib` artifact found for this horizon |
| `insufficient_history` | Too few OHLCV bars to produce features |

**`uncertainty_flag`:** `true` when `max(prob_up, prob_sideways, prob_down) < 0.45` — the model has no clear view.

### How market predictions interact with behavioural analysis and RAG

The `market_insights.get_market_insight()` service (called from other backend routes) combines:

1. The forecast probabilities (as labelled factual context, not instructions)
2. The user's behavioural pattern analysis from `pattern_analyzer.analyse()`
3. Recent deterministic intervention warnings from `InterventionLog` (read-only)
4. RAG-retrieved financial education material from `retrieval.retrieve()`

This combined context is passed to `llm_gateway.generate("market_insight", ...)` so the AI can narrate an educational explanation. The LLM never originates predictions — it only explains what the model computed.

**Determinism boundary:** Market prediction output is persisted to `AIFinding` (kind="market_prediction"). It is never written to `InterventionLog`. The Investment Readiness Score reads only `InterventionLog`, so no ML output can influence scoring.

### Required new dependencies

```
scikit-learn==1.6.1   # required
joblib==1.4.2          # required (ships with scikit-learn; pinned for reproducibility)
# xgboost==2.1.3      # optional — uncomment in requirements.txt to enable
```

### Configuration (`.env` overrides)

```
MARKET_ML_MODEL_DIR=./data/models
MARKET_ML_RETURN_THRESHOLD_1D=0.01
MARKET_ML_RETURN_THRESHOLD_3D=0.015
MARKET_ML_RETURN_THRESHOLD_5D=0.02
MARKET_ML_RETURN_THRESHOLD_10D=0.025
MARKET_ML_STALENESS_DAYS=7
MARKET_ML_MIN_HISTORY_BARS=60
```

### Limitations and disclaimer

- This module is **experimental and educational**. It is not a financial product.
- Predictions are **not financial advice** and must not be used to make real investment decisions.
- The model was trained on historical market data. **Past performance does not guarantee future results.**
- The model may perform **at or below random chance** on out-of-sample data. Evaluation metrics are reported in the `.json` artifact alongside each trained model.
- Reported metrics are from a held-out test period using chronological splitting. They cannot guarantee future accuracy.
- The model does not account for fundamental analysis, earnings events, macroeconomic changes, or corporate actions.

### Running the tests

```powershell
# New ML tests only
python -m pytest tests/test_market_ml.py -v

# Full backend test suite
python -m pytest tests/ -q
```

---

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
