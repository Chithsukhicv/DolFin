# How to Run DolFin in VS Code

_Step-by-step guide for Windows_

---

## 🚀 Quick Start (First Time Setup)

### Step 1: Open the Project in VS Code

1. Open VS Code
2. Click **File → Open Folder**
3. Navigate to `C:\Users\chith\OneDrive\Desktop\DolFin`
4. Click **Select Folder**

---

## 🔧 Backend Setup (Do this ONCE)

### Step 2: Open Terminal in VS Code

1. In VS Code, press **Ctrl + `** (backtick) to open the terminal
2. Or go to **Terminal → New Terminal** from the menu

### Step 3: Navigate to Backend Folder

In the terminal, type:
```cmd
cd backend
```

### Step 4: Create Virtual Environment (if not already done)

```cmd
python -m venv .venv
```

Wait for it to finish (takes 10-20 seconds).

### Step 5: Activate Virtual Environment

```cmd
.venv\Scripts\activate
```

You should see **(.venv)** appear at the start of your terminal line. This means it's activated.

### Step 6: Install Python Dependencies

```cmd
pip install -r requirements.txt
```

This will take 1-2 minutes. Wait for it to finish.

### Step 7: Create or migrate the database

```cmd
alembic upgrade head
```

Alembic creates the tables on a fresh database, and migrates an existing one
in place without losing your data. Run this again after any `git pull` that
changes `app/models.py`.

You can confirm it worked:

```cmd
python scripts\check_schema.py
```

### Step 8: Stock catalogue and quizzes

Nothing to run. The stock catalogue is seeded automatically on server startup,
and it upserts — so newly added symbols (the index ETFs, the mid-caps) appear
without a wipe. Quizzes and concepts are read straight from Python modules and
need no seeding at all.

---

## 🌐 Frontend Setup (Do this ONCE)

### Step 10: Open a NEW Terminal

1. Click the **+** icon in the terminal panel (or press **Ctrl + Shift + `**)
2. This opens a second terminal (backend terminal stays running)

### Step 11: Navigate to Frontend Folder

In the NEW terminal, type:
```cmd
cd frontend
```

### Step 12: Install Node Dependencies

```cmd
npm install
```

This will take 2-3 minutes. Wait for it to finish.

---

## ▶️ Running the App (Every Time)

### Step 13: Start the Backend

1. Go to the **first terminal** (the one in `backend` folder)
2. Make sure virtual environment is activated (you should see `(.venv)`)
3. If not activated, run: `.venv\Scripts\activate`
4. Start the backend:

```cmd
uvicorn app.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

✅ **Backend is now running!** Keep this terminal open.

### Step 14: Start the Frontend

1. Go to the **second terminal** (the one in `frontend` folder)
2. Start the frontend:

```cmd
npm run dev
```

You should see:
```
  ▲ Next.js 15.1.6
  - Local:        http://localhost:3000
  - Ready in 2.5s
```

✅ **Frontend is now running!** Keep this terminal open.

### Step 15: Open the App

1. Open your web browser (Chrome, Edge, Firefox)
2. Go to: **http://localhost:3000**
3. You should see the DolFin signup page!

---

## Verifying it works

Two levels of check. The unit tests need nothing running; the smoke test needs
the backend up.

```cmd
cd backend
.venv\Scripts\activate

:: 140 unit tests, stubbed prices, no network needed
python -m pytest

:: 52 checks walking the whole learner journey against real market data
:: (leave uvicorn running in another terminal first)
python scripts\smoke_test.py
```

The smoke test is the one to run if something feels broken — it names the exact
step that failed rather than leaving you guessing.

Frontend checks:

```cmd
cd frontend
npx tsc --noEmit                 :: type errors
npx eslint src --ext .ts,.tsx    :: lint
npm run build                    :: full production build
```

---

## 🎯 Quick Visual Guide

Your VS Code should look like this:

```
┌─────────────────────────────────────────────┐
│  VS Code                                    │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  File Explorer (left sidebar)       │   │
│  │  - backend/                         │   │
│  │  - frontend/                        │   │
│  │  - HANDOFF.md                       │   │
│  │  - INTERVIEW-PREP.md                │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  Terminal Panel (bottom)            │   │
│  │  ┌──────────────┬──────────────┐    │   │
│  │  │ Terminal 1   │ Terminal 2   │    │   │
│  │  │ (backend)    │ (frontend)   │    │   │
│  │  │ uvicorn...   │ npm run dev  │    │   │
│  │  └──────────────┴──────────────┘    │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## 🛑 Stopping the App

When you're done:

1. Go to **Terminal 1** (backend) → press **Ctrl + C**
2. Go to **Terminal 2** (frontend) → press **Ctrl + C**
3. Close VS Code

---

## 🔄 Next Time You Want to Run It

You don't need to do the setup again! Just:

1. Open VS Code
2. Open the project folder
3. Open Terminal 1 → `cd backend` → `.venv\Scripts\activate` → `uvicorn app.main:app --reload`
4. Open Terminal 2 → `cd frontend` → `npm run dev`
5. Go to http://localhost:3000

---

## ❗ Common Issues & Fixes

### Issue 1: "python is not recognized"

**Fix:** Install Python first
1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or 3.12
3. **Important:** Check "Add Python to PATH" during installation
4. Restart VS Code after installation

### Issue 2: "npm is not recognized"

**Fix:** Install Node.js first
1. Go to https://nodejs.org/
2. Download the LTS version (Long Term Support)
3. Install it (just keep clicking Next)
4. Restart VS Code after installation

### Issue 3: "uvicorn: command not found"

**Fix:** Make sure virtual environment is activated
```cmd
cd backend
.venv\Scripts\activate
pip install -r requirements.txt
```

### Issue 4: Virtual environment won't activate

**Fix:** Try this instead:
```cmd
.venv\Scripts\activate.bat
```

Or use PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

### Issue 5: Backend runs but errors about a missing table or column

**Fix:** You're on an older schema. Migrate:
```cmd
cd backend
.venv\Scripts\activate
alembic upgrade head
python scripts\check_schema.py
```

If you'd rather start completely fresh (this deletes your practice data):
```cmd
del data\dolfin.db
alembic upgrade head
```

### Issue 6: Frontend runs but can't fetch data (prices don't load)

**Fix:** Make sure backend is running first
- Backend should be at http://127.0.0.1:8000
- Check `.env.local` in frontend folder has: `NEXT_PUBLIC_API_URL=http://localhost:8000`

### Issue 7: Port 3000 or 8000 already in use

**Fix for Windows:**

Find what's using the port:
```cmd
netstat -ano | findstr :3000
```

Kill the process (replace XXXX with the PID from above):
```cmd
taskkill /PID XXXX /F
```

Or just use a different port:
```cmd
# Backend on different port
uvicorn app.main:app --reload --port 8001

# Frontend on different port
npm run dev -- -p 3001
```

### Issue 8: Prices not loading (Yahoo Finance blocked)

**Fix:** This is expected sometimes. The cache will help. If it persists:
1. Check your internet connection
2. Wait a minute and refresh
3. The app will show cached prices (up to 60 seconds old)

---

## 📝 Handy Commands Cheat Sheet

### Backend Commands
```cmd
cd backend
.venv\Scripts\activate

pip install -r requirements.txt      :: install dependencies
alembic upgrade head                 :: create / migrate the database
uvicorn app.main:app --reload        :: run the server

python -m pytest                     :: unit tests
python scripts\smoke_test.py         :: live end-to-end checks
python scripts\check_schema.py       :: confirm the schema is current

:: after changing app/models.py
alembic revision --autogenerate -m "describe the change"
alembic upgrade head

:: start over from scratch (deletes your practice data)
del data\dolfin.db
alembic upgrade head
```

### Frontend Commands
```cmd
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run frontend
npm run dev

# Build for production (optional)
npm run build
```

---

## 🎓 For Day 1 of Study Plan

When you start Day 1, you'll run both terminals and use the app. Now you know how! 

Good luck! 🚀
