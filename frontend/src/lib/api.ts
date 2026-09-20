// Thin fetch wrapper around the FastAPI backend.

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/** Timeout for any single request. Yahoo-backed endpoints can hang, and a
 *  spinner that never resolves is worse than a clear error. */
const TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the backend is unreachable rather than returning an error. */
  get isOffline() {
    return this.status === 0;
  }
}

/** Pull the useful text out of FastAPI's `{"detail": ...}` envelope. */
function parseDetail(body: string): string | undefined {
  try {
    const parsed = JSON.parse(body);
    if (typeof parsed?.detail === "string") return parsed.detail;
    if (Array.isArray(parsed?.detail)) {
      // Pydantic validation errors arrive as a list of issues.
      return parsed.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ");
    }
  } catch {
    /* not JSON — fall through to the raw text */
  }
  return body || undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (err) {
    // Network failure or timeout. Status 0 lets callers show "can't reach the
    // server" rather than a misleading HTTP error.
    const aborted = err instanceof DOMException && err.name === "AbortError";
    throw new ApiError(
      aborted
        ? "The server took too long to respond."
        : "Can't reach the DolFin server. Is the backend running?",
      0,
    );
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const detail = parseDetail(await res.text());
    throw new ApiError(detail ?? `Request failed (${res.status})`, res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
};

export const fetcher = <T>(path: string) => request<T>(path);

// ---------- Domain types ----------
export type Persona = "woman" | "teen";
export type RiskAppetite = "low" | "medium" | "high";
export type Lang = "en" | "hi";
export type Severity = "info" | "warn" | "critical";

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  persona: Persona;
  risk_appetite: RiskAppetite;
  language: Lang;
  cash: number;
}

export interface Stock {
  symbol: string;
  name: string;
  sector: string;
  market_cap_band: string;
  risk_level: string;
}

export interface Quote {
  symbol: string;
  price: number;
  currency: string;
  name: string | null;
  exchange: string | null;
  previous_close: number | null;
  day_change: number | null;
  day_change_pct: number | null;
  fetched_at: number;
  /** Backend served a cached price because Yahoo failed. Shown to the learner
   *  so they never act on an old number believing it is live. */
  stale?: boolean;
  scenario?: { id: string; kind: string; severity: number; narrative: string } | null;
  scenario_multiplier?: number;
}

export interface Holding {
  symbol: string;
  name: string;
  sector: string;
  quantity: number;
  avg_cost: number;
  live_price: number;
  cost_basis: number;
  market_value: number;
  unrealised_pnl: number;
  unrealised_pnl_pct: number;
  price_stale: boolean;
  /** Quote lookup failed entirely; value falls back to cost basis. */
  price_unavailable: boolean;
}

export interface Portfolio {
  user_id: string;
  cash: number;
  invested: number;
  market_value: number;
  total_value: number;
  unrealised_pnl: number;
  holdings: Holding[];
  sector_allocation_pct: Record<string, number>;
  stale_price_count: number;
  scenario: {
    id: string;
    kind: string;
    severity: number;
    narrative: string;
    multiplier: number;
  } | null;
}

export interface Intervention {
  rule_id: string;
  severity: Severity;
  title: string;
  message: string;
  concept: string | null;
  context: Record<string, unknown>;
  /** Always "rule". Rule findings feed the Readiness Score; AI findings never do,
   *  and the distinction travels with the data so the UI never has to infer it. */
  source: "rule";
}

export interface PreviewResult {
  /** Must be echoed back on confirm or cancel so the backend can record
   *  whether the learner heeded these warnings. */
  preview_id: string;
  quote: Quote;
  interventions: Intervention[];
  /** `mode` is "none" when no rule fired, so there was nothing to explain. */
  coach: { mode: AiMode | "none"; message: string };
  blocking: boolean;
  estimated_cost: number;
}

export interface TradeResult {
  transaction: {
    id: string;
    symbol: string;
    side: "buy" | "sell";
    quantity: number;
    price: number;
    fee: number;
    realised_pnl: number;
  };
  cash_after: number;
  holding_quantity: number;
  avg_cost: number;
  interventions_fired: Intervention[];
}

export interface Readiness {
  score: number;
  graduated: boolean;
  graduation_threshold: number;
  breakdown: Record<string, number>;
  weights: Record<string, number>;
  is_active: boolean;
  transactions_count: number;
  holdings_count: number;
  /** 0–1. Below 1 means too little history to judge habits yet. */
  confidence: number;
  provisional: boolean;
  evidence_needed: { trades: number; holdings: number };
}

export interface Scenario {
  id: string;
  kind: string;
  severity: number;
  duration_days: number;
  recovery_days: number;
  narrative: string | null;
  is_active: boolean;
  started_at: string | null;
  ends_at: string | null;
  current_multiplier: number;
  progress: number;
}

export interface ScenarioPreset {
  kind: string;
  severity: number;
  duration_days: number;
  recovery_days: number;
  label: string;
}

export interface GoalTemplate {
  key: string;
  label: string;
  persona: Persona;
  suggested_amount: number;
  suggested_horizon_months: number;
  coach_hint: string;
}

export interface Transaction {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  fee: number;
  realised_pnl: number;
  scenario_id: string | null;
  interventions_fired: Intervention[];
  created_at: string;
}

export interface InterventionLogItem {
  id: string;
  rule_id: string;
  severity: Severity;
  title: string;
  message: string;
  concept: string | null;
  user_action: "heeded" | "ignored" | "pending";
  source: "rule";
  created_at: string;
}

export interface QuizQuestion {
  index: number;
  question: string;
  options: string[];
}

export interface QuizAnswer {
  index: number;
  question: string;
  options: string[];
  given: number;
  correct_answer: number;
  is_correct: boolean;
  /** Why the right answer is right. The actual teaching payload. */
  explanation: string;
}

export interface QuizResult {
  id: string;
  concept: string;
  score_pct: number;
  passed: boolean;
  answers: QuizAnswer[];
  created_at: string;
}

// ---------- Learning content ----------
export interface ConceptSummary {
  key: string;
  title: string;
  one_liner: string;
  difficulty: "beginner" | "intermediate";
  read_minutes: number;
  quiz: string | null;
  related_rules: string[];
}

export interface Concept extends ConceptSummary {
  body: Array<{ heading: string; text: string }>;
  takeaways: string[];
  misconception: { myth: string; reality: string };
}

export interface GlossaryTerm {
  term: string;
  label: string;
  definition: string;
}

export interface PathStep {
  key: string;
  title: string;
  description: string;
  done: boolean;
  href: string;
  action: string;
  /** Names the learner evidence this step was picked from. */
  rationale: string;
  concept: string | null;
  current?: number;
  target?: number;
}

export interface LearningPath {
  steps: PathStep[];
  completed: number;
  total: number;
  percent: number;
  next_step: PathStep | null;
  all_done: boolean;
  /** True when ordering reflects measured weaknesses rather than the fixed sequence. */
  adaptive: boolean;
  weaknesses: Record<
    string,
    { ignored: number; heeded: number; fired: number; failed_quizzes: number; passed_quiz: boolean; score: number }
  >;
  /** Progress could not be computed; every step reads as not done. */
  degraded?: boolean;
}

export interface EquityPoint {
  at: string;
  total_value: number;
  cash: number;
  market_value: number;
  invested_cost: number;
  unrealised_pnl: number;
  reason: "trade" | "scenario_start" | "scenario_stop" | "poll";
  scenario_id: string | null;
}

export interface ConceptProgress {
  concept: string;
  fired: number;
  heeded: number;
  ignored: number;
  pending: number;
  quiz_passed: boolean;
  heed_rate: number | null;
}

export interface PriceBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ---------- AI reasoning layer ----------
// Everything below is advisory. `source: "ai"` is carried through from the
// backend so the UI can label it, and none of it reaches the Readiness Score —
// that stays computed from the deterministic rules alone.

/** Where a claim came from. `corpus` is "A" (curated), "B" (this learner's own
 *  record) or "market" (a live quote, in which case `retrieved_at` is set). */
export interface Citation {
  chunk_id: string;
  corpus: "A" | "B" | "market";
  source_title: string;
  source_reference: string | null;
  retrieved_at?: string;
}

/** How an AI response was produced. `offline` means the deterministic fallback
 *  ran, which is a normal state, not an error. */
export type AiMode =
  | "generated"
  | "cached"
  | "offline"
  | "skipped"
  | "grounding_failed";

export interface AiFinding {
  id: string;
  title: string;
  body: string;
  severity: Severity;
  concept: string | null;
  confidence: string | null;
  citations: Citation[];
  source: "ai";
}

export interface AiFindingsResponse {
  preview_id: string;
  /** "pending" means keep polling. "ready" is final, including when the review
   *  finished with nothing to add. "unavailable" means no model is configured. */
  status: "pending" | "ready" | "unavailable";
  findings: AiFinding[];
  /** Always false. Restated on the wire so these can never be mistaken for
   *  scored rule findings. */
  affects_score: false;
}

export interface BehaviourPattern {
  label: string;
  evidence: string[];
  insight: string;
  next_action: string | null;
  concept: string | null;
  /** True when this names something the learner does well. */
  is_strength: boolean;
  source: "ai";
  citations: Citation[];
}

export interface PatternAnalysis {
  status: "ok" | "insufficient_activity" | "unavailable";
  message: string | null;
  patterns: BehaviourPattern[];
  evidence: PatternEvidence | Record<string, never>;
  mode: AiMode | "cached";
  generated_at?: string;
  /** Only present when status is "insufficient_activity". */
  trades_needed?: number;
}

/** The counted facts the analysis was computed from. Every number in a pattern
 *  should be traceable to one of these. */
export interface PatternEvidence {
  trades: number;
  buys: number;
  sells: number;
  activity_span_days: number | null;
  sells_during_a_scenario: number;
  holding_periods_days: number[];
  sells_within_7_days: number;
  holdings: number;
  distinct_sectors: number;
  sector_names: string[];
  realised_pnl: number;
  warnings_fired: number;
  warnings_resolved: number;
  warnings_heeded: number;
  by_concept: Record<string, { fired: number; heeded: number; ignored: number }>;
  quizzes_passed: string[];
  quizzes_failed: string[];
}

/** How sound the learner's written reason was. Advisory: it never changes
 *  whether the warning counted as heeded. */
export type ReasoningClass = "sound" | "partly_sound" | "prediction_based";

export interface ReflectionAnalysis {
  analysed: boolean;
  reason?: "no_text";
  classification?: ReasoningClass;
  response?: string;
  concept?: string | null;
  citations?: Citation[];
  mode: AiMode;
}

export interface ReflectionResult {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  triggering_rule_ids: string[];
  reason: string | null;
  preview_id: string | null;
  warnings_heeded: number;
  analysis: ReflectionAnalysis;
  created_at: string;
}

/** A past reflection, with its assessment persisted alongside it. */
export interface StoredReflection {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  triggering_rule_ids: string[];
  reason: string | null;
  preview_id: string | null;
  reasoning_class: ReasoningClass | null;
  ai_response: string | null;
  ai_citations: Citation[];
  ai_mode: AiMode | null;
  source: "ai" | null;
  created_at: string;
}

// ---------- Chatbot ----------
export interface ChatAnswer {
  session_id: string;
  message_id?: string;
  answer: string;
  citations: Citation[];
  mode: AiMode;
  /** False when nothing was retrieved above the relevance floor. */
  grounded: boolean;
  status: "ok" | "no_material" | "empty_question" | "error";
  available_topics?: string[];
  corpora_used?: Array<"A" | "B" | "market">;
  top_score?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  mode: AiMode | null;
  created_at: string;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
}

// ---------- Adaptive quizzes ----------
export interface AdaptiveQuestion {
  index: number;
  id: string;
  question: string;
  options: string[];
  /** "generated" questions came from the model; "seeded" are the hand-written bank. */
  source: "generated" | "seeded";
}

export interface AdaptiveQuiz {
  status: "ok";
  concept: string;
  mode: "generated" | "seeded";
  generated_count: number;
  seeded_count: number;
  citations: Citation[];
  /** Echo these back on submit so the server can score against its own answers. */
  question_ids: string[];
  questions: AdaptiveQuestion[];
}

export interface AdaptiveQuizAnswer extends QuizAnswer {
  citations: Citation[];
}

export interface AdaptiveQuizResult extends Omit<QuizResult, "answers"> {
  answers: AdaptiveQuizAnswer[];
}

// ---------- Typed endpoint helpers ----------
// Grouped so a page imports one object rather than assembling URL strings, and
// so a path change lands in exactly one place.
export const ai = {
  /** Poll after a trade preview. `status: "pending"` means keep waiting. */
  findings: (previewId: string, userId: string) =>
    api.get<AiFindingsResponse>(
      `/portfolio/preview/${previewId}/ai-findings?user_id=${encodeURIComponent(userId)}`,
    ),

  patterns: (userId: string, force = false) =>
    api.get<PatternAnalysis>(
      `/coach/patterns/${userId}${force ? "?force=true" : ""}`,
    ),

  evidence: (userId: string) => api.get<PatternEvidence>(`/coach/evidence/${userId}`),

  ask: (body: { user_id: string; question: string; session_id?: string | null }) =>
    api.post<ChatAnswer>("/chat/ask", body),

  sessions: (userId: string) =>
    api.get<ChatSessionSummary[]>(`/chat/sessions/${userId}`),

  transcript: (userId: string, sessionId: string) =>
    api.get<{ session_id: string; messages: ChatMessage[] }>(
      `/chat/sessions/${userId}/${sessionId}`,
    ),

  topics: () => api.get<{ topics: string[] }>("/chat/topics"),

  adaptiveQuiz: (userId: string, concept: string) =>
    api.get<AdaptiveQuiz>(`/quizzes/adaptive/${userId}/${concept}`),

  adaptiveTargets: (userId: string) =>
    api.get<{ concepts: string[] }>(`/quizzes/adaptive/${userId}`),

  submitAdaptiveQuiz: (body: {
    user_id: string;
    concept: string;
    question_ids: string[];
    answers: number[];
  }) => api.post<AdaptiveQuizResult>("/quizzes/adaptive/submit", body),
};
