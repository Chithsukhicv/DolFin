"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import {
  ai,
  api,
  fetcher,
  type AdaptiveQuiz,
  type AdaptiveQuizResult,
  type Citation,
  type QuizQuestion,
  type QuizResult,
} from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState, LoadingCard } from "@/components/States";
import { AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";

export default function QuizPage() {
  const router = useRouter();
  const params = useParams<{ concept: string }>();
  const concept = decodeURIComponent(params.concept);
  const userId = useRequireUser();

  const [fresh, setFresh] = useState(false);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<QuizResult | AdaptiveQuizResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const seeded = useSWR<{ concept: string; questions: QuizQuestion[] }>(
    fresh ? null : `/quizzes/${encodeURIComponent(concept)}`,
    fetcher,
  );

  const [attempt, setAttempt] = useState(0);
  const generated = useSWR<AdaptiveQuiz>(
    fresh && userId ? ["adaptive-quiz", userId, concept, attempt] : null,
    () => ai.adaptiveQuiz(userId!, concept),
    { revalidateOnFocus: false },
  );

  const loading = fresh ? generated.isLoading : seeded.isLoading;
  const error = fresh ? generated.error : seeded.error;
  const questions = fresh
    ? (generated.data?.questions ?? [])
    : (seeded.data?.questions ?? []);

  function reset(nextFresh = fresh) {
    setResult(null);
    setAnswers({});
    setSubmitError(null);
    if (nextFresh !== fresh) setFresh(nextFresh);
    if (nextFresh) setAttempt((n) => n + 1);
  }

  async function submit() {
    if (!userId || questions.length === 0) return;
    setBusy(true);
    setSubmitError(null);
    try {
      const arr = questions.map((q) => answers[q.index] ?? -1);
      if (fresh && generated.data) {
        setResult(
          await ai.submitAdaptiveQuiz({
            user_id: userId,
            concept,
            question_ids: generated.data.question_ids,
            answers: arr,
          }),
        );
      } else {
        setResult(
          await api.post<QuizResult>("/quizzes/submit", {
            user_id: userId,
            concept,
            answers: arr,
          }),
        );
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Couldn't score your answers.");
    } finally {
      setBusy(false);
    }
  }

  if (!userId) return null;

  if (error) {
    return (
      <div className="space-y-4">
        <ErrorState
          error={error}
          label={
            fresh
              ? "Couldn't put together fresh questions for this concept"
              : "No quiz found for this concept"
          }
        />
        <div className="flex gap-3 text-sm">
          {fresh && (
            <button onClick={() => reset(false)} className="text-brand underline">
              Use the standard questions
            </button>
          )}
          <Link href="/learn" className="text-brand underline">
            Browse the concept library
          </Link>
        </div>
      </div>
    );
  }

  const allAnswered =
    questions.length > 0 && questions.every((q) => answers[q.index] !== undefined);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-bold capitalize text-white">
          Quiz: {concept.replaceAll("_", " ")}
        </h1>
        <p className="mt-1 text-sm text-muted">
          Pass with 80%+ to give your discipline sub-score a boost.
        </p>
      </header>

      {/* Question set toggle */}
      {!result && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-hairline bg-elev-1 p-3 text-sm">
          <span className="text-muted">Question set:</span>
          <button
            onClick={() => reset(false)}
            aria-pressed={!fresh}
            className={`rounded-lg px-3 py-1 text-xs font-medium transition ${
              !fresh
                ? "bg-brand/20 text-brand border border-brand/30"
                : "bg-elev-2 text-muted border border-hairline hover:bg-elev-3"
            }`}
          >
            Standard
          </button>
          <button
            onClick={() => reset(true)}
            aria-pressed={fresh}
            className={`rounded-lg px-3 py-1 text-xs font-medium transition ${
              fresh
                ? "bg-ai/15 text-ai border border-ai/30"
                : "bg-elev-2 text-muted border border-hairline hover:bg-elev-3"
            }`}
          >
            Fresh questions
          </button>
          {fresh && generated.data && (
            <span className="ml-auto flex items-center gap-2 text-xs text-subtle">
              <AiBadge mode={generated.data.generated_count > 0 ? "generated" : "offline"} />
              {generated.data.generated_count > 0
                ? `${generated.data.generated_count} new · ${generated.data.seeded_count} from the bank`
                : "Generation unavailable — using the standard bank"}
            </span>
          )}
          {fresh && (generated.data?.generated_count ?? 0) > 0 && (
            <div className="w-full">
              <AiDisclaimer compact />
            </div>
          )}
        </div>
      )}

      {loading && <LoadingCard lines={5} />}

      {result ? (
        <Card>
          <CardHeader
            title={`You scored ${result.score_pct.toFixed(0)}%`}
            subtitle={
              result.passed
                ? "Passed — your Discipline sub-score has gone up"
                : "Below the 80% pass mark — read the explanations and try again"
            }
          />

          <ol className="space-y-3 text-sm">
            {result.answers.map((a) => (
              <li
                key={a.index}
                className={`rounded-xl border p-4 ${
                  a.is_correct
                    ? "border-pos/25 bg-pos/8"
                    : "border-neg/25 bg-neg/8"
                }`}
              >
                <div className="mb-2 flex items-start gap-2">
                  <span
                    aria-hidden="true"
                    className={`mt-0.5 text-sm font-bold ${
                      a.is_correct ? "text-pos" : "text-neg"
                    }`}
                  >
                    {a.is_correct ? "✓" : "✕"}
                  </span>
                  <p className="font-medium text-fg">{a.question}</p>
                </div>

                {!a.is_correct && a.given >= 0 && (
                  <p className="mb-1 text-neg">
                    <span className="font-medium">You chose:</span> {a.options[a.given]}
                  </p>
                )}
                <p className={a.is_correct ? "text-pos" : "text-muted"}>
                  <span className="font-medium">
                    {a.is_correct ? "Correct: " : "Correct answer: "}
                  </span>
                  {a.options[a.correct_answer]}
                </p>

                {a.explanation && (
                  <p className="mt-2 border-t border-hairline pt-2 text-muted">
                    {a.explanation}
                  </p>
                )}

                <Citations citations={(a as { citations?: Citation[] }).citations ?? []} />
              </li>
            ))}
          </ol>

          <div className="mt-5 flex flex-wrap gap-2">
            <button
              onClick={() => reset()}
              className="btn-ghost rounded-lg px-3 py-1.5 text-sm"
            >
              {fresh ? "New questions" : "Try again"}
            </button>
            {!fresh && (
              <button
                onClick={() => reset(true)}
                className="rounded-lg border border-ai/30 bg-ai/10 px-3 py-1.5 text-sm text-ai hover:bg-ai/20"
              >
                Try fresh questions
              </button>
            )}
            <Link
              href={`/learn/${concept}`}
              className="btn-ghost rounded-lg px-3 py-1.5 text-sm"
            >
              Read the full concept
            </Link>
            <button
              onClick={() => router.push("/coach")}
              className="btn-primary rounded-lg px-3 py-1.5 text-sm font-semibold"
            >
              Back to coach
            </button>
          </div>
        </Card>
      ) : (
        !loading && (
          <>
            <ol className="space-y-4">
              {questions.map((q) => (
                <Card key={q.index}>
                  <p className="font-medium text-fg">
                    {q.index + 1}. {q.question}
                  </p>
                  <ul className="mt-3 space-y-2 text-sm">
                    {q.options.map((opt, i) => {
                      const selected = answers[q.index] === i;
                      return (
                        <li key={i}>
                          <label
                            className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 transition ${
                              selected
                                ? "border-brand/40 bg-brand/10 text-fg"
                                : "border-hairline hover:bg-elev-2 text-muted"
                            }`}
                          >
                            <input
                              type="radio"
                              name={`q${q.index}`}
                              checked={selected}
                              onChange={() =>
                                setAnswers((a) => ({ ...a, [q.index]: i }))
                              }
                              className="h-4 w-4 accent-[var(--brand)]"
                            />
                            {opt}
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </Card>
              ))}
            </ol>

            {submitError && (
              <p role="alert" className="text-sm text-neg">{submitError}</p>
            )}

            <button
              onClick={submit}
              disabled={!allAnswered || busy}
              className="btn-primary rounded-xl px-6 py-2.5 font-semibold disabled:opacity-50"
            >
              {busy ? "Scoring…" : "Submit answers"}
            </button>
            {!allAnswered && (
              <p className="text-xs text-subtle">Answer every question to submit.</p>
            )}
          </>
        )
      )}
    </div>
  );
}
