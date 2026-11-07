"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher, type LearningPath as Path } from "@/lib/api";

export function LearningPath({ userId, compact = false }: { userId: string; compact?: boolean }) {
  const { data } = useSWR<Path>(userId ? `/learn/path/${userId}` : null, fetcher, {
    refreshInterval: 15_000,
  });

  if (!data) return null;

  const next = data.next_step;

  if (compact) {
    if (!next) {
      return (
        <div className="rounded-2xl border border-pos/25 bg-pos/8 p-5">
          <p className="text-sm font-medium text-pos">
            You&apos;ve completed the whole learning path.
          </p>
          <p className="mt-1 text-sm text-muted">
            Keep practising, or revisit any concept in the library.
          </p>
        </div>
      );
    }
    return (
      <div className="rounded-2xl border border-brand/25 bg-brand/8 p-5">
        <div className="flex items-center justify-between gap-3">
          <p className="label text-brand">
            Your next step · {data.completed} of {data.total} done
          </p>
        </div>
        <h3 className="mt-2 font-display font-semibold text-white">{next.title}</h3>
        <p className="mt-1 text-sm text-muted">{next.description}</p>
        {data.adaptive && next.rationale && (
          <p className="mt-1.5 text-xs text-subtle">{next.rationale}</p>
        )}
        <Link
          href={next.href}
          className="btn-primary mt-3 inline-block rounded-lg px-4 py-2 text-sm font-medium"
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
          <h2 id="path-heading" className="font-display text-lg font-semibold text-white">
            Your learning path
          </h2>
          <p className="text-sm text-muted">
            {data.completed} of {data.total} steps complete
            {data.adaptive && (
              <span
                title="The order below reflects the warnings you've overridden and the quizzes you've failed."
                className="ml-2 rounded border border-ai/25 bg-ai/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ai"
              >
                personalised
              </span>
            )}
          </p>
        </div>
        <span className="metric text-2xl font-bold text-brand">{data.percent}%</span>
      </div>

      {data.degraded && (
        <p
          role="status"
          className="mb-4 rounded-lg border border-warn/25 bg-warn/8 px-3 py-2 text-xs text-warn"
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
        className="mb-6 h-2 overflow-hidden rounded-full bg-elev-3"
      >
        <div
          className="h-full rounded-full bg-brand transition-all duration-500"
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
                  ? "border-pos/20 bg-pos/6"
                  : isNext
                  ? "border-brand/30 bg-brand/8"
                  : "border-hairline bg-elev-1"
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                    step.done
                      ? "bg-pos/20 text-pos"
                      : isNext
                      ? "bg-brand/20 text-brand"
                      : "bg-elev-3 text-subtle"
                  }`}
                >
                  {step.done ? "✓" : idx + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-fg">
                    {step.title}
                    {step.done && <span className="sr-only"> (complete)</span>}
                  </p>
                  <p className="mt-0.5 text-sm text-muted">{step.description}</p>

                  {data.adaptive && !step.done && step.rationale && (
                    <p className="mt-1 text-xs italic text-subtle">{step.rationale}</p>
                  )}

                  {step.target !== undefined && !step.done && (
                    <p className="mt-2 text-xs font-medium text-subtle">
                      {step.current} of {step.target}
                    </p>
                  )}

                  {!step.done && (
                    <Link
                      href={step.href}
                      className={`mt-2 inline-block text-sm font-medium ${
                        isNext ? "text-brand underline" : "text-muted hover:text-fg hover:underline"
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
