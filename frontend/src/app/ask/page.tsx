"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { ai, ApiError, type ChatAnswer, type ChatMessage } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";
import { AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";

const SUGGESTIONS = [
  "What is a P/E ratio?",
  "Why is panic selling so expensive?",
  "How much of my portfolio should one stock be?",
  "What did DolFin warn me about most?",
  "How do capital gains taxes work in India?",
];

interface Turn {
  role: "user" | "assistant";
  content: string;
  citations: ChatMessage["citations"];
  mode: ChatMessage["mode"];
  grounded?: boolean;
  topics?: string[];
}

export default function AskPage() {
  const userId = useRequireUser();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const { data: sessions, mutate: refreshSessions } = useSWR(
    userId ? ["chat-sessions", userId] : null,
    () => ai.sessions(userId!),
    { revalidateOnFocus: false },
  );

  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length, busy]);

  if (!userId) return null;
  const uid: string = userId;

  async function send(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setDraft("");
    setError(null);
    setBusy(true);
    setTurns((prev) => [...prev, { role: "user", content: text, citations: [], mode: null }]);
    try {
      const res: ChatAnswer = await ai.ask({ user_id: uid, question: text, session_id: sessionId });
      setSessionId(res.session_id);
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          citations: res.citations,
          mode: res.mode,
          grounded: res.grounded,
          topics: res.available_topics,
        },
      ]);
      void refreshSessions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the coach just now.");
      setTurns((prev) => prev.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  async function openSession(id: string) {
    setError(null);
    try {
      const res = await ai.transcript(uid, id);
      setSessionId(id);
      setTurns(res.messages.map((m) => ({
        role: m.role,
        content: m.content,
        citations: m.citations,
        mode: m.mode,
      })));
    } catch {
      setError("Couldn't open that conversation.");
    }
  }

  function startNew() {
    setSessionId(null);
    setTurns([]);
    setError(null);
  }

  return (
    <div className="space-y-6">
      {/* ── Header with orb ── */}
      <header className="flex items-center gap-4">
        <AssistantOrb />
        <div>
          <h1 className="font-display text-2xl font-bold text-white">Ask DolFin</h1>
          <p className="mt-0.5 text-sm text-muted">
            Answers from DolFin&apos;s concept library and your own record — every answer shows its sources.
          </p>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_16rem]">
        {/* ── Conversation ── */}
        <Card className="flex min-h-[28rem] flex-col">
          <CardHeader
            title="Conversation"
            subtitle="Grounded in the concept library, rule definitions, and your history"
            right={
              turns.length > 0 ? (
                <button
                  onClick={startNew}
                  className="btn-ghost rounded-lg px-2.5 py-1 text-xs font-medium"
                >
                  New
                </button>
              ) : undefined
            }
          />

          <div
            className="flex-1 space-y-4 overflow-y-auto pr-1"
            role="log"
            aria-live="polite"
            aria-label="Conversation with DolFin"
          >
            {turns.length === 0 && (
              <div className="rounded-xl border border-dashed border-hairline-strong bg-elev-2/50 p-5">
                <p className="text-sm font-medium text-fg">
                  Ask anything about investing, or about your own record.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => void send(s)}
                      className="rounded-full border border-hairline-strong bg-elev-2 px-3 py-1.5 text-xs text-muted transition hover:border-brand/40 hover:bg-brand/10 hover:text-brand"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {turns.map((turn, i) =>
              turn.role === "user" ? (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand/20 px-4 py-2.5 text-sm text-white ring-1 ring-brand/30">
                    {turn.content}
                  </p>
                </div>
              ) : (
                <div key={i} className="fade-in-up max-w-[92%]">
                  <div className="card-sheen rounded-2xl rounded-bl-sm border border-hairline bg-elev-1 px-4 py-3 text-sm">
                    <div className="mb-1.5 flex items-center gap-2">
                      <span className="text-xs font-semibold text-ai">DolFin</span>
                      {turn.mode && <AiBadge mode={turn.mode} />}
                    </div>
                    <p className="whitespace-pre-wrap text-muted">{turn.content}</p>
                    {turn.topics && turn.topics.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {turn.topics.map((t) => (
                          <span
                            key={t}
                            className="rounded-full border border-hairline bg-elev-2 px-2 py-0.5 text-xs text-subtle"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                    <Citations citations={turn.citations} />
                  </div>
                </div>
              ),
            )}

            {busy && (
              <p role="status" className="flex items-center gap-2 text-xs text-muted">
                <span className="inline-flex gap-0.5">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-ai"
                      style={{ animationDelay: `${i * 120}ms` }}
                      aria-hidden
                    />
                  ))}
                </span>
                Looking through the library and your record…
              </p>
            )}
            <div ref={endRef} />
          </div>

          {error && <p role="alert" className="mt-3 text-sm text-neg">{error}</p>}

          <AiDisclaimer />

          <form
            onSubmit={(e) => { e.preventDefault(); void send(draft); }}
            className="mt-4 flex gap-2 border-t border-hairline pt-4"
          >
            <label htmlFor="chat-input" className="sr-only">Your question</label>
            <input
              id="chat-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={500}
              placeholder="Why did DolFin warn me about that trade?"
              className="flex-1 rounded-xl border border-hairline-strong bg-elev-2 px-3 py-2 text-sm text-fg placeholder:text-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
            />
            <button
              type="submit"
              disabled={busy || draft.trim().length === 0}
              className="btn-primary rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-50"
            >
              Ask
            </button>
          </form>
        </Card>

        {/* ── Sidebar ── */}
        <div className="space-y-4">
          <Card>
            <CardHeader title="Past questions" />
            {!sessions || sessions.length === 0 ? (
              <p className="text-sm text-subtle">Nothing yet.</p>
            ) : (
              <ul className="space-y-1">
                {sessions.map((s) => (
                  <li key={s.id}>
                    <button
                      onClick={() => void openSession(s.id)}
                      className={`w-full rounded-lg px-2 py-1.5 text-left text-xs transition hover:bg-elev-2 ${
                        s.id === sessionId
                          ? "bg-brand/10 font-medium text-brand"
                          : "text-muted"
                      }`}
                    >
                      <span className="line-clamp-2 block">{s.title}</span>
                      <span className="text-subtle">
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <p className="text-xs leading-relaxed text-muted">
              <strong className="block text-fg">Why the sources matter</strong>
              DolFin answers only from its own concept library, its rule definitions, and your
              own trade record. If it has no material on your question it will say so rather
              than guess.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ── Assistant orb decoration ── */
function AssistantOrb() {
  return (
    <div className="relative flex h-12 w-12 shrink-0 items-center justify-center" aria-hidden>
      {/* Outer glow ring */}
      <div className="absolute inset-0 rounded-full bg-gradient-to-br from-brand/30 to-ai/20 ai-orb" />
      {/* Spinning ring */}
      <svg
        className="absolute inset-0 ai-orb-ring"
        width="48" height="48" viewBox="0 0 48 48"
        fill="none"
      >
        <circle
          cx="24" cy="24" r="22"
          stroke="url(#orbGrad)"
          strokeWidth="1"
          strokeDasharray="8 4"
          opacity="0.5"
        />
        <defs>
          <linearGradient id="orbGrad" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
            <stop stopColor="#6C63FF" />
            <stop offset="1" stopColor="#40D9FF" />
          </linearGradient>
        </defs>
      </svg>
      {/* Core */}
      <div className="relative flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand to-ai text-white shadow-lg">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      </div>
    </div>
  );
}
