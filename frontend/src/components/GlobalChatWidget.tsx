
"use client";

import { useEffect, useRef, useState } from "react";
import { ai, ApiError, type ChatAnswer, type ChatMessage } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";

interface Turn {
  role: "user" | "assistant";
  content: string;
  citations: ChatMessage["citations"];
  mode: ChatMessage["mode"];
  grounded?: boolean;
  topics?: string[];
}

const SUGGESTIONS = [
  "What is a P/E ratio?",
  "Explain the risks of investing.",
  "Why did DolFin warn me about a trade?",
];

export default function GlobalChatWidget() {
  const userId = useRequireUser();

  const [isOpen, setIsOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (turns.length > 0) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [turns.length, busy]);

  if (!userId) return null;
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
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't reach DolFin right now."
      );
      setTurns((prev) => prev.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  function startNew() {
    setSessionId(null);
    setTurns([]);
    setError(null);
  }

  return (
    <>
      {/* Floating launcher */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          aria-label="Open DolFin AI assistant"
          className="fixed bottom-6 right-6 z-[100] flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-2xl text-white shadow-xl transition hover:scale-105 hover:bg-indigo-500"
        >
          ✦
        </button>
      )}

      {/* Chat window */}
      {isOpen && (
        <section
          aria-label="DolFin AI assistant"
          className="fixed bottom-5 right-5 z-[100] flex h-[min(620px,calc(100dvh-40px))] w-[min(390px,calc(100vw-32px))] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#10121d] shadow-2xl"
        >
          {/* Header */}
          <header className="flex items-center justify-between border-b border-white/10 bg-[#171a29] px-4 py-3">
            <div>
              <h2 className="font-semibold text-white">
                ✦ Ask DolFin
              </h2>
              <p className="text-xs text-slate-400">
                Your AI investing assistant
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={startNew}
                title="New conversation"
                className="rounded-lg px-2 py-1 text-xs text-slate-300 hover:bg-white/10"
              >
                New
              </button>

              <button
                onClick={() => setIsOpen(false)}
                aria-label="Close chat"
                className="rounded-lg px-2 py-1 text-lg text-slate-300 hover:bg-white/10"
              >
                ×
              </button>
            </div>
          </header>

          {/* Messages */}
          <div
            className="flex-1 space-y-3 overflow-y-auto p-4"
            role="log"
            aria-live="polite"
          >
            {turns.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-300">
                  Hi! I&apos;m DolFin. Ask me anything about investing,
                  your portfolio, or your learning journey.
                </p>

                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => void send(suggestion)}
                    className="block w-full rounded-xl border border-white/10 bg-white/5 p-3 text-left text-xs text-slate-300 transition hover:border-indigo-400/50 hover:bg-indigo-500/10"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}

            {turns.map((turn, index) =>
              turn.role === "user" ? (
                <div key={index} className="flex justify-end">
                  <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-3 py-2 text-sm text-white">
                    {turn.content}
                  </p>
                </div>
              ) : (
                <div key={index} className="max-w-[95%]">
                  <div className="rounded-2xl rounded-bl-sm border border-white/10 bg-white/5 px-3 py-3 text-sm text-slate-200">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-xs font-semibold text-indigo-300">
                        DolFin
                      </span>
                      {turn.mode && <AiBadge mode={turn.mode} />}
                    </div>

                    <p className="whitespace-pre-wrap">{turn.content}</p>

                    {turn.topics && turn.topics.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {turn.topics.map((topic) => (
                          <span
                            key={topic}
                            className="rounded-full bg-white/10 px-2 py-1 text-xs text-slate-300"
                          >
                            {topic}
                          </span>
                        ))}
                      </div>
                    )}

                    <Citations citations={turn.citations} />
                  </div>
                </div>
              )
            )}

            {busy && (
              <p className="animate-pulse text-xs text-slate-400">
                DolFin is thinking...
              </p>
            )}

            <div ref={endRef} />
          </div>

          {/* Error and disclaimer */}
          {error && (
            <p role="alert" className="px-4 text-xs text-red-400">
              {error}
            </p>
          )}

          <div className="px-4">
            <AiDisclaimer />
          </div>

          {/* Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(draft);
            }}
            className="flex gap-2 border-t border-white/10 p-3"
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={500}
              placeholder="Ask DolFin anything..."
              className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500 focus:border-indigo-500"
            />

            <button
              type="submit"
              disabled={busy || !draft.trim()}
              className="rounded-xl bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </section>
      )}
    </>
  );
}
