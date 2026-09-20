# DolFin Quick Start Guide (5 Minutes)

_Super simple steps to run your app RIGHT NOW_

---

## ⚡ First Time? Do This Setup (One Time Only)

### 1️⃣ Create Environment Files

#### Backend .env file:
1. Open `backend` folder in VS Code
2. Copy `.env.example` and rename the copy to `.env`
3. Open `.env` and change this line:
   ```
   GEMINI_API_KEY=your-gemini-api-key-here
   ```
   To (if you have a Gemini key):
   ```
   GEMINI_API_KEY=your-actual-key
   ```
   Or leave it as is (app will work in offline mode)

#### Frontend .env.local file:
1. Open `frontend` folder in VS Code
2. Copy `.env.local.example` and rename the copy to `.env.local`
3. It should contain:
   ```
   NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
   ```
   (This is already correct, don't change it)

### 2️⃣ Setup Backend

Open terminal in VS Code (Ctrl + `), then:

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.db
python -m app.data.stocks_seed
python -m app.data.quizzes_seed
```

Wait for each command to finish. This takes 3-4 minutes total.

### 3️⃣ Setup Frontend

Open a NEW terminal (click + icon), then:

```cmd
cd frontend
npm install
```

Wait for it to finish (2-3 minutes).

✅ **Setup complete! You only do this once.**

---

## 🚀 Running the App (Every Time)

### Terminal 1 (Backend):
```cmd
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Wait until you see: `Uvicorn running on http://127.0.0.1:8000`

### Terminal 2 (Frontend):
```cmd
cd frontend
npm run dev
```

Wait until you see: `Local: http://localhost:3000`

### Open Browser:
Go to: **http://localhost:3000**

✅ **Done! Your app is running.**

---

## 🎯 Visual Guide

```
Step 1: Open VS Code → Open Folder → Select "DolFin"

Step 2: Open Terminal (Ctrl + `)
┌────────────────────────────────────┐
│ PS C:\...\DolFin>                  │  ← You're here
└────────────────────────────────────┘

Step 3: Start Backend
┌────────────────────────────────────┐
│ PS C:\...\DolFin> cd backend       │
│ PS C:\...\backend> .venv\Scripts\activate │
│ (.venv) PS C:\...\backend> uvicorn app.main:app --reload │
│ INFO: Uvicorn running on http://127.0.0.1:8000 │  ← Backend ready!
└────────────────────────────────────┘

Step 4: Open NEW terminal (click +), Start Frontend
┌────────────────────────────────────┐
│ PS C:\...\DolFin> cd frontend      │
│ PS C:\...\frontend> npm run dev    │
│ ▲ Next.js Local: http://localhost:3000 │  ← Frontend ready!
└────────────────────────────────────┘

Step 5: Open browser → http://localhost:3000
```

---

## 🛑 Stopping the App

1. Terminal 1 → Press **Ctrl + C**
2. Terminal 2 → Press **Ctrl + C**
3. Done!

---

## ❓ Something Wrong?

### "python not found"
→ Install Python from https://www.python.org/downloads/
→ Check "Add Python to PATH" during install

### "npm not found"
→ Install Node.js from https://nodejs.org/

### Virtual environment won't activate
→ Try: `.venv\Scripts\activate.bat`

### Backend starts but shows database errors
→ Run these again:
```cmd
cd backend
.venv\Scripts\activate
python -m app.db
python -m app.data.stocks_seed
python -m app.data.quizzes_seed
```

### Prices not loading in the app
→ Check backend terminal is running
→ Check `.env.local` in frontend has: `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`

---

## 📚 Next Steps

Once your app is running:
1. Sign up (pick "Teen", "College fund")
2. Buy some stocks
3. Try the crash simulator
4. Check your readiness score

Then start **Day 1** of your study plan! 🚀

---

## 💡 Pro Tip

Keep both terminals open while using the app. If you see errors, look at the terminal output — it shows you what went wrong.

**Both terminals need to be running for the app to work!**
- Backend = The brain (handles data)
- Frontend = The face (what you see)
