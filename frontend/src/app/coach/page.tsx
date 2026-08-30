"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher, type ConceptProgress, type InterventionLogItem } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState } from "@/components/States";
import { severityClasses } from "@/lib/format";

export default function CoachPage() {
  const userId = useRequireUser();

  const { data: logs, error: logsError } = useSWR<InterventionLogItem[]>(
    userId ? `/history/interventions/${userId}?limit=50` : null,
    fetcher,
  );
  const { data: progress } = useSWR<ConceptProgress[]>(
    userId ? `/history/interventions/${userId}/summary` : null,
    fetcher,
  );

  if (!userId) return null;

  const concepts = Array.from(
    new Set(logs?.map((l) => l.concept).filter(Boolean) as string[]),
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Coach history</h1>
        <p className="text-sm text-slate-500">
          Every warning the coach fired and what you did with it.
        </p>
      </header>

      {/* Which lessons are landing and which keep tripping them up. This is the
          learner's own behavioural mirror, not just a list of past events. */}
      {progress && progress.length > 0 && (
        <Card>
          <CardHeader
            title="Your concepts"
            subtitle="How often each warning fired, and whether you acted on it"
          />
          <ul className="space-y-3">
            {progress.map((p) => (
              <li
                key={p.concept}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-slate-200 p-3"
              >
                <div className="min-w-[9rem] flex-1">
                  <Link
                    href={`/learn/${p.concept}`}
                    className="text-sm font-medium capitalize text-slate-900 hover:text-indigo-700 hover:underline"
                  >
                    {p.concept.replaceAll("_", " ")}
                  </Link>
                  <p className="text-xs text-slate-500">
                    fired {p.fired}× · heeded {p.heeded} · overridden {p.ignored}
                  </p>
                </div>

                {p.heed_rate !== null && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      p.heed_rate >= 50
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {p.heed_rate.toFixed(0)}% heeded
                  </span>
                )}

                {p.quiz_passed ? (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                    quiz passed
                  </span>
                ) : (
                  <Link
                    href={`/coach/quiz/${p.concept}`}
                    className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                  >
                    take quiz →
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {concepts.length === 0 && (!progress || progress.length === 0) && (
        <Card>
          <CardHeader
            title="Nothing to review yet"
            subtitle="Warnings appear here once you start trading"
          />
          <p className="text-sm text-slate-600">
            You can get ahead of them in the{" "}
            <Link href="/learn" className="text-indigo-600 underline">
              concept library
            </Link>
            , which covers every idea DolFin coaches on.
          </p>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Past interventions"
          subtitle="Heeded means you backed out after reading the warning"
        />
        {logsError ? (
          <ErrorState error={logsError} label="Couldn't load your history" />
        ) : !logs || logs.length === 0 ? (
          <p className="text-sm text-slate-500">No interventions yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {logs.map((l) => {
              const cls = severityClasses(l.severity);
              return (
                <li key={l.id} className="py-3">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls.badge}`}
                    >
                      {l.severity}
                    </span>
                    <strong className={cls.text}>{l.title}</strong>
                    <span className="text-xs text-slate-400">
                      {new Date(l.created_at).toLocaleString()}
                    </span>
                    {l.user_action && (
                      <span
                        title={
                          l.user_action === "heeded"
                            ? "You cancelled the trade after reading this"
                            : l.user_action === "ignored"
                            ? "You went ahead with the trade"
                            : "You closed the dialog without trading"
                        }
                        className={`ml-auto rounded-full px-2 py-0.5 text-[10px] uppercase ${
                          l.user_action === "heeded"
                            ? "bg-emerald-100 text-emerald-700"
                            : l.user_action === "ignored"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {l.user_action === "ignored" ? "overridden" : l.user_action}
                      </span>
                    )}
                  </div>
                  <p className="text-slate-700">{l.message}</p>
                  {l.concept && (
                    <Link
                      href={`/learn/${l.concept}`}
                      className="mt-1 inline-block text-xs text-indigo-600 hover:underline"
                    >
                      Learn about {l.concept.replaceAll("_", " ")} →
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
