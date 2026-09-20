# DolFin — Next Steps (User's Todo)

_Use this checklist to drive the project to completion. Cross items off as you go._

---

## A. Right now — fix the live demo

### A1. Restart the backend after the CORS change
The backend's allowed-origins list was widened from `localhost:3000` to also include `127.0.0.1:3000`. You must restart `uvicorn` for the change to take effect.

In the **backend** terminal:

```cmd
:: stop the running server with Ctrl+C, then:
.venv\Scripts\activate.bat
uvicorn app.main:app --reload
```

### A2. Hard-refresh the browser
After restarting, in the browser do **Ctrl + Shift + R** to bypass any cached CORS errors. Prices will load.

### A3. If prices still look stuck
Open browser DevTools → Network tab → click any stock and confirm the call to `/market/quote/...` returns `200`. If it returns `0` or "blocked", the backend needs to be restarted (step A1).

---

## B. Two short tasks before review (15-20 minutes total)

### B1. Add the Gemini API key (turns on the real AI coach)

Without this, the coach uses deterministic offline templates (works fine, just less natural language).

1. Go to https://aistudio.google.com/apikey
2. Sign in with your Google account
3. Click **Create API key** → copy it
4. In the `backend` folder, copy `.env.example` to `.env`:
   ```cmd
   cd backend
   copy .env.example .env
   ```
5. Open `backend\.env` in VS Code, paste your key after `GEMINI_API_KEY=`
6. Restart the backend. The coach now writes real, persona-aware messages.

### B2. Set up Firebase (for real login later)

Optional — only needed when we replace the localStorage stub with real auth.

1. Go to https://console.firebase.google.com
2. Click **Add project** → name it `dolfin`
3. Enable **Authentication** → Email/Password and Google sign-in
4. Project Settings → Service accounts → **Generate new private key** → downloads a JSON file
5. Save it as `backend\firebase-adminsdk.json`
6. Tell the AI agent (Kiro/Claude/whoever) "Firebase is set up, wire it in."

---

## C. Decisions to make (just answer in chat)

The agent will implement these once you decide:

- **Hindi UI?** — Should the buttons and labels be translatable to Hindi at v1, or stay English-only?
- **Parent dashboard for teens?** — Required for the demo, or post-review?
- **Real-broker handoff at 80+ readiness** — link out to Zerodha Kite Connect from the readiness page? v1 or post-review?
- **Authentication source** — Firebase Auth (planned) or stick with the localStorage stub for the demo?

---

## D. Things still to be implemented (the agent will do these)

These are listed in `HANDOFF.md` with full context. You don't have to do anything; just tell the agent which to start.

| Priority | Feature | Why it matters |
|---|---|---|
| High | Firebase Auth in frontend | Real users instead of localStorage |
| High | Gemini wired into coach (auto once key is in `.env`) | Natural-language AI explanations |
| Medium | Hindi translation of UI strings via `next-intl` | Differentiation, accessibility |
| Medium | Stock detail page with price chart (`recharts` LineChart) | Better trade UX |
| Medium | Dashboard chart of Readiness Score over time | Show progress |
| Medium | Reflection note input ("why are you cancelling?") | Better discipline data |
| Low | APScheduler cron for daily price refresh | Currently on-demand cache works fine |
| Low | Parent dashboard for teen users | Future scope, only if asked |
| Low | Real-broker handoff link | Future scope |

---

## E. Polish / bug fixes

After you use the app, send the agent a short list of:
- Anything that looks ugly or confusing
- Bugs you hit
- Features your guides asked for during reviews

The agent will fix them. **Don't try to edit code yourself** — describe what you want.

---

## F. Move out of OneDrive (optional)

This project is in `OneDrive\Desktop\DolFin`. OneDrive sometimes sync-conflicts with `node_modules` and `.venv`. If you start seeing weird "file in use" errors, ask the agent to move the project to:

```
C:\Users\chith\Projects\DolFin
```

It's a single command and updates all paths automatically.

---

## G. Git commit (when you're happy)

When everything works and you want to push to GitHub:

1. In the project root, ask the agent: **"commit and push to GitHub"**
2. The agent will: `git init`, first commit, set up `.gitignore`, and walk you through creating a GitHub repo.
3. Don't run `git init` yourself — the existing `.gitignore` is set up for the whole project.

---

## H. Run the app — quick reference

You'll do this every time you want to demo or develop.

**Two terminals.** In VS Code: `Terminal → Split Terminal`.

**Terminal 1 — Backend** (`cd backend` first):
```cmd
.venv\Scripts\activate.bat
uvicorn app.main:app --reload
```
Backend runs on http://127.0.0.1:8000 (API docs at /docs).

**Terminal 2 — Frontend** (`cd frontend` first):
```cmd
npm run dev
```
Frontend runs on http://127.0.0.1:3000.

Open the frontend URL in a browser. To stop either, press **Ctrl+C** in that terminal.
