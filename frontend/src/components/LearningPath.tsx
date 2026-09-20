"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher, type LearningPath as Path } from "@/lib/api";

/**
 * The guided path.
 *
 * A new learner used to land on an empty dashboard with no idea what to do
 * next — the worst possible moment for someone who has never invested. This
 * always shows exactly one obvious next action, with the rest visible as
 * context so the journey has a shape.
 *
 * Once there is evidence to adapt to, the order changes: steps addressing the
 * concepts the learner has actually overridden or failed move to the top, and
 * each step explains which of their own records put it there. Someone who
 * diversifies well and panic-sells constantly should not be told to read about
 * diversification.
 */
export function LearningPath({ userId, compact = false }: { userId: string; compact?: boolean }) {
  const { data } = useSWR<Path>(userId ? `/learn/path/${userId}` : null, fetcher, {
    refreshInterval: 15_000,
  });

  if (!data) return null;

  const next = data.next_step;

  if (compact) {
    if (!next) {
      return (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <p className="text-sm font-medium text-emerald-900">
            You&apos;ve completed the whole learning path.
          </p>
          <p className="mt-1 text-sm text-emerald-700">
            Keep practising, or revisit any concept in the library.
          </p>
        </div>
      );
    }
    return (
      <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-5">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-medium uppercase tracking-wide text-indigo-700">
            Your next step · {data.completed} of {data.total} done
          </p>
        </div>
        <h3 className="mt-2 font-semibold text-indigo-950">{next.title}</h3>
        <p className="mt-1 text-sm text-indigo-800">{next.description}</p>
        {data.adaptive && next.rationale && (
          <p className="mt-1.5 text-xs text-indigo-600">{next.rationale}</p>
        )}
        <Link
          href={next.href}
          className="mt-3 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {next.action} →
        </Link>
      </div>
    );
  }

  return (
    <section aria-labelledby="path-heading">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 id="path-heading" className="text-lg font-semibold text-slate-900">
            Your learning path
          </h2>
          <p className="text-sm text-slate-600">
            {data.completed} of {data.total} steps complete
            {data.adaptive && (
              <span
                title="The order below reflects the warnings you've overridden and the quizzes you've failed."
                className="ml-2 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-800"
              >
                personalised
              </span>
            )}
          </p>
        </div>
        <span className="text-2xl font-semibold text-indigo-600">{data.percent}%</span>
      </div>

      {data.degraded && (
        <p
          role="status"
          className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
        >
          Progress couldn&apos;t be computed just now, so every step below reads as
          incomplete. Nothing you&apos;ve done has been lost.
        </p>
      )}

      <div
        role="progressbar"
        aria-valuenow={data.percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Learning path progress"
        className="mb-6 h-2 overflow-hidden rounded-full bg-slate-200"
      >
        <div
          className="h-full rounded-full bg-indigo-600 transition-all"
          style={{ width: `${data.percent}%` }}
        />
      </div>

      <ol className="space-y-3">
        {data.steps.map((step, idx) => {
          const isNext = next?.key === step.key;
          return (
            <li
              key={step.key}
              className={`rounded-xl border p-4 ${
                step.done
                  ? "border-emerald-200 bg-emerald-50/60"
                  : isNext
                  ? "border-indigo-300 bg-indigo-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                    step.done
                      ? "bg-emerald-600 text-white"
                      : isNext
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-200 text-slate-600"
                  }`}
                >
                  {step.done ? "✓" : idx + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">
                    {step.title}
                    {step.done && <span className="sr-only"> (complete)</span>}
                  </p>
                  <p className="mt-0.5 text-sm text-slate-600">{step.description}</p>

                  {/* Why this step, in the learner's own numbers. Shown only for
                      outstanding work — a rationale on something already done is
                      just clutter. */}
                  {data.adaptive && !step.done && step.rationale && (
                    <p className="mt-1 text-xs italic text-slate-500">{step.rationale}</p>
                  )}

                  {step.target !== undefined && !step.done && (
                    <p className="mt-2 text-xs font-medium text-slate-500">
                      {step.current} of {step.target}
                    </p>
                  )}

                  {!step.done && (
                    <Link
                      href={step.href}
                      className={`mt-2 inline-block text-sm font-medium ${
                        isNext ? "text-indigo-700 underline" : "text-slate-600 hover:underline"
                      }`}
                    >
                      {step.action} →
                    </Link>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
