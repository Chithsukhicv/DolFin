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

/**
 * One quiz page, two question sources.
 *
 * The seeded bank has three questions per concept, which is fine the first time
 * and useless the third: by then the learner has memorised the answers rather
 * than the idea. "Fresh questions" generates new ones from the same Corpus A
 * material the concept page is written from, so the assessment tests
 * understanding instead of recall.
 *
 * Generated questions are validated server-side before they are ever shown —
 * four distinct options, exactly one answer, a real explanation — and anything
 * that fails is silently replaced by a seeded question. A slightly repetitive
 * quiz is a much better failure than a wrong one.
 */
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

  // Keyed on an attempt counter so "Try again" fetches a genuinely new set
  // rather than replaying the cached one.
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
      // Previously swallowed: a failed submit left the button spinning with no
      // explanation and the learner's answers apparently lost.
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
            <button onClick={() => reset(false)} className="text-indigo-600 underline">
              Use the standard questions
            </button>
          )}
          <Link href="/learn" className="text-indigo-600 underline">
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
        <h1 className="text-2xl font-semibold capitalize">
          Quiz: {concept.replaceAll("_", " ")}
        </h1>
        <p className="text-sm text-slate-500">
          Pass with 80%+ to give your discipline sub-score a boost.
        </p>
      </header>

      {!result && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
          <span className="text-slate-600">Question set:</span>
          <button
            onClick={() => reset(false)}
            aria-pressed={!fresh}
            className={`rounded-lg px-3 py-1 text-xs font-medium ${
              !fresh ? "bg-indigo-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
            }`}
          >
            Standard
          </button>
          <button
            onClick={() => reset(true)}
            aria-pressed={fresh}
            className={`rounded-lg px-3 py-1 text-xs font-medium ${
              fresh ? "bg-violet-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
            }`}
          >
            Fresh questions
          </button>
          {fresh && generated.data && (
            <span className="ml-auto flex items-center gap-2 text-xs text-slate-500">
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

          {/* The explanations are the point of the results screen. Reporting
              only "correct option: 2" told the learner nothing about why. */}
          <ol className="space-y-3 text-sm">
            {result.answers.map((a) => (
              <li
                key={a.index}
                className={`rounded-lg border p-4 ${
                  a.is_correct
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-red-200 bg-red-50"
                }`}
              >
                <div className="mb-2 flex items-start gap-2">
                  <span
                    aria-hidden="true"
                    className={`mt-0.5 text-xs font-bold ${
                      a.is_correct ? "text-emerald-700" : "text-red-700"
                    }`}
                  >
                    {a.is_correct ? "✓" : "✕"}
                  </span>
                  <p className="font-medium text-slate-900">{a.question}</p>
                </div>

                {!a.is_correct && a.given >= 0 && (
                  <p className="mb-1 text-red-800">
                    <span className="font-medium">You chose:</span> {a.options[a.given]}
                  </p>
                )}
                <p className={a.is_correct ? "text-emerald-900" : "text-slate-800"}>
                  <span className="font-medium">
                    {a.is_correct ? "Correct: " : "Correct answer: "}
                  </span>
                  {a.options[a.correct_answer]}
                </p>

                {a.explanation && (
                  <p className="mt-2 border-t border-black/5 pt-2 text-slate-700">
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
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
            >
              {fresh ? "New questions" : "Try again"}
            </button>
            {!fresh && (
              <button
                onClick={() => reset(true)}
                className="rounded-lg border border-violet-300 px-3 py-1.5 text-sm text-violet-700 hover:bg-violet-50"
              >
                Try fresh questions
              </button>
            )}
            <Link
              href={`/learn/${concept}`}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
            >
              Read the full concept
            </Link>
            <button
              onClick={() => router.push("/coach")}
              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
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
                  <p className="font-medium">
                    {q.index + 1}. {q.question}
                  </p>
                  <ul className="mt-3 space-y-2 text-sm">
                    {q.options.map((opt, i) => {
                      const selected = answers[q.index] === i;
                      return (
                        <li key={i}>
                          <label
                            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 ${
                              selected
                                ? "border-indigo-500 bg-indigo-50"
                                : "border-slate-200 hover:bg-slate-50"
                            }`}
                          >
                            <input
                              type="radio"
                              name={`q${q.index}`}
                              checked={selected}
                              onChange={() =>
                                setAnswers((a) => ({ ...a, [q.index]: i }))
                              }
                              className="h-4 w-4"
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
              <p role="alert" className="text-sm text-red-600">
                {submitError}
              </p>
            )}

            <button
              onClick={submit}
              disabled={!allAnswered || busy}
              className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {busy ? "Scoring..." : "Submit"}
            </button>
            {!allAnswered && (
              <p className="text-xs text-slate-500">Answer every question to submit.</p>
            )}
          </>
        )
      )}
    </div>
  );
}
