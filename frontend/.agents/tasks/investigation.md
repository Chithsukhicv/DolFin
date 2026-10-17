# DolFin Frontend — UI Investigation Report

> Generated from a full file-by-file read of the frontend source tree.  
> Every page, every component, every API endpoint is documented below.

---

## 1. Discovered Routes

| Route | File | Auth required |
|---|---|---|
| `/` | `src/app/page.tsx` | No (redirects to `/dashboard` if logged in) |
| `/ask` | `src/app/ask/page.tsx` | Yes |
| `/coach` | `src/app/coach/page.tsx` | Yes |
| `/coach/quiz/[concept]` | `src/app/coach/quiz/[concept]/page.tsx` | Yes |
| `/dashboard` | `src/app/dashboard/page.tsx` | Yes |
| `/learn` | `src/app/learn/page.tsx` | No (no `useRequireUser`) |
| `/learn/[concept]` | `src/app/learn/[concept]/page.tsx` | No |
| `/market` | `src/app/market/page.tsx` | Yes |
| `/portfolio` | `src/app/portfolio/page.tsx` | Yes |
| `/readiness` | `src/app/readiness/page.tsx` | Yes |
| `/scenarios` | `src/app/scenarios/page.tsx` | Yes |

**No separate `/login`, `/register`, or `/onboarding` route exists.** The root `/` page serves as onboarding/registration. There is no dedicated auth page.

---

## 2. Per-page API Usage

### `/` — Onboarding / Registration (`page.tsx`)

**API calls:**
- `GET /goals/templates?persona={persona}` — loads goal templates on persona-toggle; called inside `useEffect` via `api.get()`, not SWR
- `POST /users` — creates a new user account on form submit
- `POST /goals` — assigns a goal to the new user after creation
- `GET /users/by-email/{email}` — account recovery: looks up a user by email to restore localStorage session

**Data displayed:**
- Onboarding form: email, name, persona (woman/teen), risk appetite (low/medium/high), language (en/hi), goal picker
- Account recovery form: email → reconnect to existing account
- Hero component (static marketing copy)
- Goal templates from backend (label, suggested amount, horizon)

**Auth pattern:** Checks `getUserId()` from localStorage on mount; redirects to `/dashboard` if already signed in.

---

### `/dashboard` — Dashboard (`page.tsx`)

**API calls (all via SWR):**
- `GET /users/{userId}` — user profile (display_name, persona, risk_appetite); `refreshInterval` none
- `GET /portfolio/{userId}` — full portfolio snapshot; `refreshInterval: 10 000 ms`
- `GET /readiness/{userId}` — readiness score; `refreshInterval: 10 000 ms`
- `GET /history/transactions/{userId}?limit=5` — last 5 transactions; no auto-refresh

**Data displayed:**
- Greeting with user's display name, persona, risk appetite
- `LearningPath` component (compact mode) — fetches `GET /learn/path/{userId}`
- Stale-price warning banner (from `pf.stale_price_count`)
- Stat cards: total portfolio value, unrealised P&L, cash, invested amount, readiness score (with provisional/graduated badges)
- `EquityCurve` chart — fetches `GET /history/equity/{userId}`
- Donut chart (Recharts `PieChart` + `Pie` + `Cell`): sector allocation from `pf.sector_allocation_pct`
- Recent activity list: last 5 transactions with buy/sell badge, symbol, price

---

### `/market` — Market (`page.tsx`)

**API calls (all via SWR or direct `api.post`):**
- `GET /catalog/stocks` — full stock catalogue
- `GET /catalog/sectors` — sector list for the filter dropdown
- `GET /market/quote/{symbol}` — live quote for selected stock; `refreshInterval: 30 000 ms` (inside `BuyPanel`)
- `POST /portfolio/preview` — buy preview that triggers intervention checking; returns `PreviewResult`

**Data displayed:**
- Searchable + sector-filterable stock list (name, symbol, sector, market cap band, risk level)
- `BuyPanel` (right column, sticky):
  - Live price, day change %, day change ₹
  - Scenario multiplier warning if active
  - `PriceChart` — fetches `GET /market/history/{symbol}?period={period}&interval={interval}`
  - Quantity input, estimated cost
  - "Preview buy" button → `InterventionModal`

**Post-trade SWR invalidations:** `mutate(/portfolio/{userId})`, `mutate(/users/{userId})`

---

### `/portfolio` — Portfolio (`page.tsx`)

**API calls:**
- `GET /portfolio/{userId}` — full portfolio including holdings; `refreshInterval: 10 000 ms`
- `POST /portfolio/preview` — sell preview triggering intervention checking
- `POST /portfolio/sell` (inside `InterventionModal.confirm()`) — executes the sell

**Data displayed:**
- Holdings table: stock name, symbol, sector, quantity, avg cost, live price (with stale badge), market value, unrealised P&L + %, sell button
- Sell modal (inline, not a dedicated page): holding details, quantity input, proceeds estimate
- `InterventionModal` for the preview/warning flow

**Post-sell SWR invalidation:** `mutate(/portfolio/{userId})`

---

### `/scenarios` — Market Scenarios (`page.tsx`)

**API calls:**
- `GET /scenarios/presets` — list of preset scenario configs
- `GET /scenarios/active/{userId}` — currently active scenario; `refreshInterval: 5 000 ms`
- `POST /scenarios/start` — start a scenario preset
- `POST /scenarios/stop` — stop the active scenario

**Data displayed:**
- Active scenario banner (if one is running): kind, severity, narrative, current multiplier, progress %, drawdown days, recovery days, "Stop scenario" button
- Preset grid: label, kind, duration_days, recovery_days; disabled while a scenario is active
- "Why this matters" static explainer card

---

### `/readiness` — Investment Readiness (`page.tsx`)

**API calls:**
- `GET /readiness/{userId}` — full readiness data; `refreshInterval: 8 000 ms`

**Data displayed:**
- Big score number / 100, graduated badge
- Provisional warning with confidence percentage and evidence_needed counts
- Per-dimension breakdown (diversification, discipline, goal_alignment, autonomy, engagement): score bar + weight + tooltip
- Static "how to improve" tips with links to `/learn/diversification` and `/learn/panic_selling`
- `LearningPath` component (full mode) — fetches `GET /learn/path/{userId}`

---

### `/coach` — Coach History (`page.tsx`)

**API calls:**
- `GET /history/interventions/{userId}?limit=50` — intervention log
- `GET /history/interventions/{userId}/summary` — per-concept progress summary

**Components rendered (each with their own API calls):**
- `PatternPanel` — calls `ai.patterns(userId)` → `GET /coach/patterns/{userId}`
- `RetestPanel` — calls `ai.adaptiveTargets(userId)` → `GET /quizzes/adaptive/{userId}`
- `ReflectionHistory` — fetches `GET /reflections/user/{userId}`

**Data displayed:**
- Per-concept progress: fired count, heeded count, overridden count, heed rate badge, quiz-passed status
- Chronological intervention log: severity badge, title, timestamp, user action (heeded / overridden / pending), message, concept link
- Behaviour patterns (AI), retest targets, reflection history (all from sub-components)

---

### `/coach/quiz/[concept]` — Quiz Page (`page.tsx`)

**API calls:**
- `GET /quizzes/{concept}` — seeded (standard) quiz questions
- `GET /quizzes/adaptive/{userId}/{concept}` — AI-generated fresh questions (via `ai.adaptiveQuiz`)
- `POST /quizzes/submit` — submit answers for seeded quiz
- `POST /quizzes/adaptive/submit` — submit answers for adaptive quiz (via `ai.submitAdaptiveQuiz`)

**Data displayed:**
- Toggle: Standard vs Fresh questions
- Question list with radio options
- Results screen: score %, pass/fail, per-question breakdown with correct answer + explanation, citations
- Mode badge (AI or offline) when fresh questions are used

---

### `/learn` — Concept Library (`page.tsx`)

**API calls:**
- `GET /learn/concepts` — all concept summaries
- `GET /learn/glossary` — all glossary terms

**Data displayed:**
- Grid of concept cards: title, difficulty badge, read time, one-liner, "Includes a quiz" label
- Glossary `<dl>` grid: term label + definition

---

### `/learn/[concept]` — Concept Detail (`page.tsx`)

**API calls:**
- `GET /learn/concepts/{key}` — full concept with body sections, takeaways, misconception

**Data displayed:**
- Breadcrumb nav
- Title, one-liner, difficulty + read time
- Article sections (heading + prose text)
- Misconception block (myth vs reality)
- Takeaways list
- CTA buttons: quiz link + market link
- Related rules note

---

### `/ask` — AI Chat (`page.tsx`)

**API calls:**
- SWR key `["chat-sessions", userId]` → `ai.sessions(userId)` → `GET /chat/sessions/{userId}`
- `ai.ask({user_id, question, session_id})` → `POST /chat/ask`
- `ai.transcript(userId, sessionId)` → `GET /chat/sessions/{userId}/{sessionId}`

**Data displayed:**
- Conversation transcript (user messages right-aligned indigo bubble, assistant messages left card)
- `AiBadge` mode on each assistant turn
- Collapsible `Citations` per turn
- Suggestion chip buttons for first-time users
- Past sessions sidebar (session title + date; click to reload transcript)
- `AiDisclaimer` below the chat

---

## 3. Existing Colour Scheme and CSS Approach

### Framework

**Tailwind CSS v4** (package: `tailwindcss: ^4`, `@tailwindcss/postcss: ^4`). There is **no `tailwind.config.js/ts`** — Tailwind v4 reads configuration entirely from CSS via `@theme inline {}` inside `globals.css`. This is a fundamental v4 difference: no JS config file exists or is needed.

### CSS Architecture

- Single `globals.css` with `@import "tailwindcss"` at the top
- All design tokens declared as CSS custom properties inside `:root`
- Tokens mapped into Tailwind's theme via `@theme inline {}` block
- Utility classes are generated from those tokens (e.g. `bg-elev-1`, `text-muted`, `border-hairline`)

### Design Language

**Dark theme only** (`color-scheme: dark` on `:root`). Colour philosophy documented in detail in globals.css header:
- Background hierarchy via lightness (elevation steps), not drop shadows
- Desaturated 300-tone accents to avoid optical vibration on dark backgrounds
- WCAG minimum 4.5:1 contrast on all body text

### CSS Custom Properties (Design Tokens)

**Elevation / Surfaces:**
| Token | Value | Purpose |
|---|---|---|
| `--bg` | `#121418` | Page background |
| `--elev-1` | `#1a1d23` | Cards, panels |
| `--elev-2` | `#21252d` | Hover state, raised elements |
| `--elev-3` | `#282d36` | Inputs, nested surfaces |
| `--elev-4` | `#2f3540` | Most elevated |
| `--hairline` | `#2b3039` | Default borders |
| `--hairline-strong` | `#3a414e` | Prominent borders |

**Foreground / Text:**
| Token | Value | Contrast on `--bg` |
|---|---|---|
| `--fg` | `#e6e8ec` | ~13:1 |
| `--fg-muted` | `#b9bec9` | ~8.6:1 |
| `--fg-subtle` | `#949aa6` | ~5.4:1 |
| `--fg-faint` | `#6f7684` | ~3.4:1 (decorative only) |

**Semantic Accents:**
| Token | Value | Meaning |
|---|---|---|
| `--brand` | `#8ab4f8` | Product actions, links |
| `--brand-dim` | `#5b8ee0` | Hover states for brand |
| `--brand-fill` | `#3f5fbf` | Filled brand buttons |
| `--brand-fill-hover` | `#4a6dd4` | Filled button hover |
| `--ai` | `#c58af9` | AI-produced content |
| `--pos` | `#81c995` | Gains, correct answers |
| `--neg` | `#f28b82` | Losses, errors |
| `--warn` | `#fdd663` | Caution, scenarios |

**Tailwind token names** (used in JSX via the `@theme inline` mapping):
- Colors: `bg-background`, `bg-surface`, `bg-surface-hover`, `bg-surface-muted`, `bg-elev-1..4`, `bg-elevated`
- Borders: `border-hairline`, `border-hairline-strong`
- Text: `text-fg`, `text-muted`, `text-subtle`, `text-faint`
- Semantic: `text-brand`, `text-ai`, `text-pos`, `text-neg`, `text-warn`, `bg-brand` etc.

### Utility Classes (Global)

| Class | Description |
|---|---|
| `.card` | Base surface: `bg-elev-1`, `border hairline`, `shadow-sm`, transitions |
| `.card-interactive` | Hover: lifts to `elev-2`, stronger border |
| `.card-raised` | Modal/dialog surface: `elev-2` + `shadow-lg` |
| `.glass` | Frosted glass: `color-mix(bg 85%)` + `backdrop-filter blur(12px)` |
| `.btn-primary` | Filled brand button |
| `.btn-ghost` | Secondary bordered button |
| `.grid-bg` | Faint 64×64px blueprint grid overlay (fixed, `z-0`) |
| `.hairline-gradient` | 1px horizontal rule with fade-out gradient |
| `.metric` | JetBrains Mono, tabular-nums, tight line-height |
| `.label` | 10.5px mono, uppercase, tracked, `--fg-subtle` |
| `.animate-rise` | `rise-in` keyframe (fade + 8px translate) |
| `.stagger` | Staggered `rise-in` for up to 6 children |
| `.live-dot` | Pulsing ring animation (emerald) for live data indicators |
| `.skeleton` | Shimmer loading placeholder |
| `.row-hover` | Table/list row hover: `bg-elev-2` |
| `.tnum` | Tabular numeric figures |

### Fonts (Google Fonts via `next/font`)

| Variable | Font | Weights | Used for |
|---|---|---|---|
| `--font-display-stack` | Sora | 500, 600, 700, 800 | Headings, titles |
| `--font-sans-stack` | Inter | variable | Body copy |
| `--font-mono-stack` | JetBrains Mono | 400, 500, 700 | Numbers, code, `.metric`, `.label` |

### Inconsistency: Mixed Token Usage

Several pages and components still use **Tailwind v3-style hardcoded palette classes** instead of the design token classes defined in `globals.css`. Examples found:

- `text-slate-500`, `text-slate-600`, `bg-slate-50`, `border-slate-200` — widespread across `EquityCurve`, `LearningPath`, `PatternPanel`, `ReflectionHistory`, `PriceChart`, `portfolio/page.tsx`, `scenarios/page.tsx`, `readiness/page.tsx`, `coach/page.tsx`, `learn/[concept]/page.tsx`
- `text-emerald-600`, `bg-emerald-100`, `text-red-600`, `bg-red-50` — in dashboard, portfolio sell modal, LearningPath
- `text-indigo-600`, `bg-indigo-600`, `rounded-lg bg-indigo-600` — button styles not using `.btn-primary`
- `bg-amber-50`, `border-amber-200`, `text-amber-800` — stale-price banners in dashboard + portfolio
- `bg-white p-6 shadow-xl` — the sell modal in portfolio page is pure light-theme white (visually broken on the dark theme)

The design system is **partially migrated**: newer components (`InterventionModal`, `States`, `Card`, market page) use token classes correctly; older or less-touched pages use hardcoded Tailwind palette values that will appear wrong against the dark theme.

---

## 4. Installed npm Packages

### `dependencies`

| Package | Version | Relevance |
|---|---|---|
| `next` | 16.2.6 | Framework (App Router) |
| `react` | 19.2.4 | UI runtime |
| `react-dom` | 19.2.4 | DOM renderer |
| `recharts` | ^3.8.1 | **Charts** — used for `EquityCurve` (AreaChart), dashboard sector donut (PieChart), `PriceChart` (LineChart) |
| `swr` | ^2.4.1 | **Data fetching** — used on every authenticated page for auto-refreshing API data |
| `clsx` | ^2.1.1 | Conditional class name merging — used in `Card.tsx` |

### `devDependencies`

| Package | Version | Relevance |
|---|---|---|
| `tailwindcss` | ^4 | CSS framework |
| `@tailwindcss/postcss` | ^4 | PostCSS integration for Tailwind v4 |
| `typescript` | ^5 | Type checking |
| `@types/node` | ^20 | Node types |
| `@types/react` | ^19 | React types |
| `@types/react-dom` | ^19 | React DOM types |
| `eslint` | ^9 | Linting |
| `eslint-config-next` | 16.2.6 | Next.js ESLint rules |

### Packages NOT installed (relevant absences)

- **No `framer-motion`** — animations are pure CSS keyframes in `globals.css` (`.animate-rise`, `.stagger`, `.live-dot`, `.skeleton`)
- **No `three.js` / `@react-three/fiber`** — no 3D
- **No `react-spring`** — no spring physics
- **No `@radix-ui/*`** — no headless UI primitives
- **No `zustand` / `jotai` / `redux`** — global state is localStorage + SWR cache only
- **No `axios`** — custom `fetch` wrapper in `src/lib/api.ts`
- **No `date-fns` / `dayjs`** — uses native `Intl.DateTimeFormat` / `Date.toLocaleString()`
- **No `react-hook-form`** — all forms use controlled state
- **No `zod`** — no client-side schema validation
- **No icon library** (`lucide-react`, `heroicons`, etc.) — all icons are inline SVGs

---

## 5. Component Structure

All components live flat in `src/components/` — no subdirectories.

### Layout Components

| Component | File | Description |
|---|---|---|
| `NavBar` | `NavBar.tsx` | Sticky glass header; responsive (collapse to sheet below `lg`); `hasUser` gates nav links; sign-out clears localStorage |
| `Footer` | `Footer.tsx` | 4-col grid with product + learn nav links; legal disclaimer about simulated money |
| `ScenarioBanner` | `ScenarioBanner.tsx` | Full-width coloured banner below NavBar when a scenario is active; polls every 5s |
| `AuthGuard` | `AuthGuard.tsx` | Renders nothing; validates localStorage `userId` against backend on every pathname change; clears session and redirects to `/` if user no longer exists |

### Surface / Primitive Components

| Component | File | Exports |
|---|---|---|
| `Card` | `Card.tsx` | `Card` (surface), `CardHeader` (title+subtitle+right slot), `Stat` (metric with delta badge), `SectionTitle` |
| `States` | `States.tsx` | `LoadingCard` (shimmer skeleton), `ErrorState` (alert with offline detection), `EmptyState` (dashed border placeholder), `StaleBadge` (inline "delayed" / "no price" badge) |
| `Term` | `Term.tsx` | Inline glossary tooltip; fetches `/learn/glossary` (shared SWR cache); renders as button with hover/focus tooltip |

### Chart Components

| Component | File | Chart type | Data source |
|---|---|---|---|
| `EquityCurve` | `EquityCurve.tsx` | Recharts `AreaChart` | `GET /history/equity/{userId}` |
| `PriceChart` | `PriceChart.tsx` | Recharts `LineChart` | `GET /market/history/{symbol}?period=&interval=` |

Both charts have colour (green/red) driven by whether the value is up or down. Both use `ResponsiveContainer`. Both have hardcoded light-theme axis tick colours (`#64748b`, `#94a3b8` = slate shades).

### Feature Components

| Component | File | Description | API |
|---|---|---|---|
| `InterventionModal` | `InterventionModal.tsx` | 3-view modal: warnings → reflect → assessment; handles buy/sell confirmation; manages focus trap and Escape key | `POST /portfolio/buy` or `/sell`; `POST /reflections` |
| `AiFindingsPanel` | `AiFindingsPanel.tsx` | Polls for AI second-opinion findings after a trade preview; polls every 1.5s for up to 15s (spinner), then quietly up to 60s | `GET /portfolio/preview/{id}/ai-findings?user_id=` |
| `LearningPath` | `LearningPath.tsx` | Compact (dashboard) and full (readiness) modes; progress bar; ordered step list with done indicators | `GET /learn/path/{userId}` |
| `PatternPanel` | `PatternPanel.tsx` | AI-computed behaviour patterns with evidence details; recompute button | `GET /coach/patterns/{userId}` |
| `ReflectionHistory` | `ReflectionHistory.tsx` | Past trade cancellations with user reasoning and AI classification | `GET /reflections/user/{userId}` |
| `RetestPanel` | `RetestPanel.tsx` | Links to adaptive quiz for failed concepts; renders nothing if no retests | `GET /quizzes/adaptive/{userId}` |
| `Hero` | `Hero.tsx` | Landing page hero (marketing); animated terminal mockup; stat strip; references `.aurora` and `.scene`/`.tilt` CSS classes that are **not defined in globals.css** |

### AI Attribution Components

| Component | File | Exports |
|---|---|---|
| `AiLabel` | `AiLabel.tsx` | `AiBadge` (mode label), `AiDisclaimer` (regulatory disclaimer), `AdvisoryNote`, `Citations` (collapsible source list) |

---

## 6. Tailwind Config (v4, CSS-based)

There is **no `tailwind.config.js` or `tailwind.config.ts`**. Tailwind v4 uses CSS-native configuration. The full effective config is in `src/app/globals.css`.

**Version:** Tailwind CSS v4 (`tailwindcss: ^4`, `@tailwindcss/postcss: ^4`)

**Custom tokens exposed as Tailwind utilities** (via `@theme inline`):

```css
@theme inline {
  /* Colors */
  --color-background
  --color-foreground
  --color-elev-1 through --color-elev-4
  --color-surface          (= elev-1)
  --color-surface-muted    (= bg)
  --color-surface-hover    (= elev-2)
  --color-elevated         (= elev-1)
  --color-hairline
  --color-hairline-strong
  --color-fg
  --color-muted            (fg-muted)
  --color-subtle           (fg-subtle)
  --color-faint            (fg-faint)
  --color-brand
  --color-ai
  --color-pos
  --color-neg
  --color-warn

  /* Fonts */
  --font-sans
  --font-display
  --font-mono
}
```

**Global CSS utilities defined** (not Tailwind utilities, but used via `className`):
`.card`, `.card-interactive`, `.card-raised`, `.card-sheen` (referenced in `Card.tsx` but **`card-sheen` is not defined in globals.css** — it's only referenced), `.glass`, `.btn-primary`, `.btn-ghost`, `.grid-bg`, `.hairline-gradient`, `.animate-rise`, `.stagger`, `.live-dot`, `.skeleton`, `.row-hover`, `.metric`, `.label`, `.tnum`

---

## 7. Animation Libraries

**No third-party animation library is installed.**

All animation is CSS-only:

| Mechanism | Where defined | Where used |
|---|---|---|
| `@keyframes rise-in` + `.animate-rise` | `globals.css` | `page.tsx` (hero, form card), `NavBar.tsx` (mobile sheet), `Hero.tsx` |
| `.stagger > *` with nth-child delays | `globals.css` | `Hero.tsx` StatStrip, potentially others |
| `@keyframes pulse-ring` + `.live-dot` | `globals.css` | `Hero.tsx` Badge component |
| `@keyframes shimmer` + `.skeleton` | `globals.css` | `States.tsx` `LoadingCard` (uses `animate-pulse` Tailwind utility, not this) |
| CSS `transition:` on `.card`, `.btn-primary`, `.btn-ghost` | `globals.css` | All interactive elements |
| `@media (prefers-reduced-motion: reduce)` | `globals.css` | Disables all animations globally |

Note: `States.tsx` `LoadingCard` uses Tailwind's `animate-pulse` class (built-in), not the custom `.skeleton` shimmer class.

---

## 8. Gaps and Risks

### 8.1 Missing CSS Classes

**`.card-sheen`** — referenced in `Card.tsx` (`sheen && "card-sheen"`) and `page.tsx` (`className="card card-sheen animate-rise rounded-2xl p-5"`) but **not defined anywhere in globals.css**. This class silently does nothing. The `Card` component's `sheen` prop defaults to `true`, meaning every `<Card>` renders without the intended visual treatment.

**`.aurora`** — referenced in `Hero.tsx` (`<div className="aurora" aria-hidden />`) but **not defined in globals.css**. The aurora effect on the landing page hero is missing entirely.

**`.scene` and `.tilt`** — referenced in `Hero.tsx` (`<div className="scene animate-rise hidden lg:block">` and `<div className="tilt relative">`) but **not defined in globals.css**. The 3D perspective tilt effect on the terminal mockup is absent. The component still renders (the `hidden lg:block` just hides it on mobile) but without any tilt perspective transform.

### 8.2 Light-Theme Styling Leaks

Multiple components render visually incorrect on the dark theme because they use hardcoded light Tailwind palette values:

- **Sell modal in `portfolio/page.tsx`**: `bg-white p-6 shadow-xl` — solid white panel on a dark page. This is the most severe: it's a functional modal that looks completely wrong.
- **`EquityCurve.tsx`**: axis tick colours `#64748b` / `#64748b` (slate-500) are readable in light mode; on dark they're too light. Chart `stroke="#e2e8f0"` gridlines are barely visible. Text above the chart: `text-slate-900` will render nearly black on a dark background.
- **`LearningPath.tsx`** (full mode): extensive use of `border-slate-200`, `bg-white`, `text-slate-900`, `bg-emerald-50/60`, `border-indigo-300 bg-indigo-50`, `border-slate-200 bg-white` — all light backgrounds that make the steps look broken in dark mode.
- **`PatternPanel.tsx`**: `border-emerald-200 bg-emerald-50`, `border-amber-200 bg-amber-50` — light tinted backgrounds.
- **`ReflectionHistory.tsx`**: same light-tone borders and backgrounds.
- **`scenarios/page.tsx`**: active scenario card `border-amber-300 bg-amber-50 text-red-900`, preset buttons `border-slate-200 hover:bg-indigo-50` — light-theme only.
- **`ScenarioBanner.tsx`**: `border-red-300 bg-red-50 text-red-900`, `border-emerald-300 bg-emerald-50 text-emerald-900` — light banners.
- **`readiness/page.tsx`**: multiple `text-slate-500/600/900`, `bg-slate-50`, `bg-emerald-100`, `bg-indigo-600` buttons.
- **`coach/page.tsx`**: `text-slate-900`, `text-slate-500`, `border-slate-200`, `bg-emerald-100 text-emerald-700`, `bg-amber-100 text-amber-800`.
- **`learn/[concept]/page.tsx`**: `text-slate-900`, `text-slate-700`, `bg-amber-50 border-amber-200`, `bg-white` — entirely light-theme styled.
- **`ask/page.tsx`**: `bg-indigo-600` user bubbles (fine), but assistant cards `border-slate-200 bg-white text-slate-800`, sidebar `bg-slate-50`, suggestion chips `bg-white ring-slate-200`.

**Pattern:** Components written or last touched earlier in development target light mode. Components in `InterventionModal`, `States`, `Card`, `NavBar`, `Footer`, `market/page.tsx`, and the `AiLabel`/`AiFindings` family correctly use the dark token system.

### 8.3 Chart Theming

Both `EquityCurve` and `PriceChart` have hardcoded light-theme colours for Recharts internals:
- `CartesianGrid stroke="#e2e8f0"` — nearly invisible on dark backgrounds
- `XAxis/YAxis tick fill: "#64748b"` / `"#94a3b8"` — slate colours that don't match `--fg-subtle`
- `Tooltip contentStyle` defaults to white background — white tooltip on dark theme
- `PriceChart` range buttons use `bg-slate-100 text-slate-600 hover:bg-slate-200` — light palette

### 8.4 Session / Auth Model

There is **no real authentication**. The user ID is stored in `localStorage` under `dolfin.user.id`. The `AuthGuard` component validates it on every route change by hitting `GET /users/{id}` — if the backend returns an error, localStorage is cleared. This is explicitly described as a stub. For the UI rewrite this is acceptable but means there are no JWT tokens, cookies, or auth headers to worry about.

### 8.5 Routing Gap: No 404 Page

No `not-found.tsx` exists under `src/app/`. Next.js will serve its default 404, which won't match the DolFin design.

### 8.6 `next.config.ts` is Empty

The config has no image domains, no rewrites, no env variable validation. `process.env.NEXT_PUBLIC_API_BASE` defaults to `http://127.0.0.1:8000` if unset (defined in `src/lib/api.ts`).

### 8.7 No Error Boundary

No `error.tsx` exists. An unhandled render error on any page will surface Next.js's default error UI.

### 8.8 `InterventionModal` Accessibility Note

The modal implements focus trap and Escape key handling manually. It uses `role="dialog"` and `aria-modal`. The focus trap only queries `a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])` — it will miss any `input` or `textarea` elements that appear in the "reflect" view. This is a functional gap in the accessibility implementation.

### 8.9 Recharts v3

The installed version is `recharts: ^3.8.1`. Recharts v3 is a fairly recent major release. The usage in `EquityCurve` and `PriceChart` uses `recharts` named imports (`Area`, `AreaChart`, `Line`, `LineChart`, etc.) which are the same API as v2. No breaking-change issues are expected, but the v3 API should be confirmed for any new chart work.

### 8.10 React 19 + Next 16

The app uses React 19 and Next.js 16 — both on the leading edge. These are generally stable but mean some third-party packages may not yet be tested against this version combination.

### 8.11 Missing `src/utils/` Directory

No `src/utils/` directory exists. Utility functions live in `src/lib/` (api.ts, format.ts, session.ts, useSession.ts). The `@/` alias maps to `src/`, so imports like `@/lib/api` are correct throughout.

---

## Summary Table

| Area | Current state | Risk for UI rewrite |
|---|---|---|
| CSS framework | Tailwind v4, CSS-only config | Low — all tokens in one file |
| Dark theme coverage | Partial — newer components correct, older ones broken | **High** — many pages need token migration |
| Chart theming | Both charts use light-mode colours | **Medium** — Recharts colours need overriding |
| Animation | Pure CSS, no library | Low — add framer-motion if needed |
| Sell modal | White card on dark background | **High** — needs full retheme |
| `.card-sheen`, `.aurora`, `.scene`, `.tilt` | Defined nowhere | **Medium** — missing effects |
| Auth | localStorage stub | Low for UI purposes |
| Missing pages | No 404, no error boundary | Low — easy to add |
| Fonts | Sora + Inter + JetBrains Mono | Low — already wired up |
| Icons | Inline SVGs only | Low (or add icon library) |
