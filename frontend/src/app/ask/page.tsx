"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { ai, ApiError, type ChatAnswer, type ChatMessage } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";
import { AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";

/**
 * Ask DolFin.
 *
 * The difference between this and a general chatbot is what sits behind it: every
 * answer is assembled from retrieved material, and the sources come back with it.
 * Two corpora are searched — DolFin's own concept library and rule definitions,
 * and the learner's own trades, warnings and reflections. The second one is why
 * "why did you warn me about that trade?" gets a real answer rather than a
 * plausible-sounding guess.
 *
 * When nothing is retrieved above the relevance floor, the answer is "I don't
 * have material on that". Declining is the feature, not a failure: a grounded
 * assistant that quietly falls back to general knowledge has stopped being
 * grounded.
 */

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

  // Keep the newest turn in view without yanking the page on first paint.
  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length, busy]);

  if (!userId) return null;

  // Narrowed once here so the handlers below don't each need a non-null
  // assertion; they only ever run after this render path.
  const uid: string = userId;

  async function send(question: string) {
    const text = question.trim();
    if (!text || busy) return;

    setDraft("");
    setError(null);
    setBusy(true);
    setTurns((prev) => [
      ...prev,
      { role: "user", content: text, citations: [], mode: null },
    ]);

    try {
      const res: ChatAnswer = await ai.ask({
        user_id: uid,
        question: text,
        session_id: sessionId,
      });
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
      setError(
        err instanceof ApiError ? err.message : "Couldn't reach the coach just now.",
      );
      // Drop the optimistic user turn so the transcript matches what was stored.
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
      setTurns(
        res.messages.map((m) => ({
          role: m.role,
          content: m.content,
          citations: m.citations,
          mode: m.mode,
        })),
      );
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
      <header>
        <h1 className="text-2xl font-semibold">Ask DolFin</h1>
        <p className="text-sm text-slate-500">
          Answers come from DolFin&apos;s own material and your own record — and every
          answer shows you what it was built from.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_16rem]">
        <Card className="flex min-h-[28rem] flex-col">
          <CardHeader
            title="Conversation"
            subtitle="Grounded in the concept library, the rule definitions, and your history"
            right={
              turns.length > 0 ? (
                <button
                  onClick={startNew}
                  className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  New
                </button>
              ) : undefined
            }
          />

          <div
            className="flex-1 space-y-4 overflow-y-auto"
            role="log"
            aria-live="polite"
            aria-label="Conversation with DolFin"
          >
            {turns.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-5">
                <p className="text-sm font-medium text-slate-700">
                  Ask anything about investing, or about your own record.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => void send(s)}
                      className="rounded-full bg-white px-3 py-1.5 text-xs text-slate-700 ring-1 ring-slate-200 hover:bg-indigo-50 hover:text-indigo-700"
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
                  <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2.5 text-sm text-white">
                    {turn.content}
                  </p>
                </div>
              ) : (
                <div key={i} className="max-w-[92%]">
                  <div
                    className={`rounded-2xl rounded-bl-sm border px-4 py-3 text-sm ${
                      turn.grounded === false
                        ? "border-slate-200 bg-slate-50 text-slate-700"
                        : "border-slate-200 bg-white text-slate-800"
                    }`}
                  >
                    <div className="mb-1.5 flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-500">DolFin</span>
                      {turn.mode && <AiBadge mode={turn.mode} />}
                    </div>
                    <p className="whitespace-pre-wrap">{turn.content}</p>

                    {turn.topics && turn.topics.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {turn.topics.map((t) => (
                          <span
                            key={t}
                            className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-600 ring-1 ring-slate-200"
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
              <p
                role="status"
                className="flex items-center gap-2 text-xs text-slate-500"
              >
                <span
                  className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500"
                  aria-hidden
                />
                Looking through the library and your record…
              </p>
            )}

            <div ref={endRef} />
          </div>

          {error && (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {error}
            </p>
          )}

          <AiDisclaimer />

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(draft);
            }}
            className="mt-4 flex gap-2 border-t border-slate-100 pt-4"
          >
            <label htmlFor="chat-input" className="sr-only">
              Your question
            </label>
            <input
              id="chat-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={500}
              placeholder="Why did DolFin warn me about that trade?"
              className="flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <button
              type="submit"
              disabled={busy || draft.trim().length === 0}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              Ask
            </button>
          </form>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Past questions" />
            {!sessions || sessions.length === 0 ? (
              <p className="text-sm text-slate-500">Nothing yet.</p>
            ) : (
              <ul className="space-y-1">
                {sessions.map((s) => (
                  <li key={s.id}>
                    <button
                      onClick={() => void openSession(s.id)}
                      className={`w-full rounded-lg px-2 py-1.5 text-left text-xs hover:bg-slate-50 ${
                        s.id === sessionId
                          ? "bg-indigo-50 font-medium text-indigo-800"
                          : "text-slate-600"
                      }`}
                    >
                      <span className="line-clamp-2">{s.title}</span>
                      <span className="text-slate-400">
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="bg-slate-50">
            <p className="text-xs leading-relaxed text-slate-600">
              <strong className="block text-slate-700">Why the sources matter</strong>
              DolFin answers only from its own concept library, its rule definitions, and
              your own trade record. If it has no material on your question it will say so
              rather than guess — which is why every answer here can be traced back to
              something you can go and read.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
