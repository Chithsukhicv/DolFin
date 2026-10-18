"use client";

import Link from "next/link";
import useSWR from "swr";
import dynamic from "next/dynamic";
import { fetcher, type ConceptProgress, type InterventionLogItem } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState } from "@/components/States";
import { PatternPanel } from "@/components/PatternPanel";
import { ReflectionHistory } from "@/components/ReflectionHistory";
import { RetestPanel } from "@/components/RetestPanel";
import { severityClasses } from "@/lib/format";
import { LazyCanvas } from "@/components/three/LazyCanvas";

const CoachOrbScene = dynamic(
  () => import("@/components/three/CoachOrbScene").then((m) => m.CoachOrbScene),
  { ssr: false }
);

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

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-5">
        <LazyCanvas
          className="h-[90px] w-[90px] shrink-0"
          camera={{ position: [0, 0, 3.5], fov: 50 }}
        >
          <CoachOrbScene isThinking={false} />
        </LazyCanvas>
        <div>
          <h1 className="font-display text-2xl font-bold text-white">Coach History</h1>
          <p className="mt-1 text-sm text-muted">
            Every warning the coach fired and what you did with it.
          </p>
        </div>
      </header>

      <PatternPanel userId={userId} />
      <RetestPanel userId={userId} />
      <ReflectionHistory userId={userId} />

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
                className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-hairline bg-elev-2 p-3 transition hover:border-hairline-strong"
              >
                <div className="min-w-[9rem] flex-1">
                  <Link
                    href={`/learn/${p.concept}`}
                    className="text-sm font-medium capitalize text-fg hover:text-brand hover:underline"
                  >
                    {p.concept.replaceAll("_", " ")}
                  </Link>
                  <p className="text-xs text-subtle">
                    fired {p.fired}× · heeded {p.heeded} · overridden {p.ignored}
                  </p>
                </div>

                {p.heed_rate !== null && (
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                      p.heed_rate >= 50
                        ? "border-pos/25 bg-pos/10 text-pos"
                        : "border-warn/25 bg-warn/10 text-warn"
                    }`}
                  >
                    {p.heed_rate.toFixed(0)}% heeded
                  </span>
                )}

                {p.quiz_passed ? (
                  <span className="rounded-full border border-pos/25 bg-pos/10 px-2 py-0.5 text-xs font-medium text-pos">
                    quiz passed
                  </span>
                ) : (
                  <Link
                    href={`/coach/quiz/${p.concept}`}
                    className="rounded-full border border-brand/25 bg-brand/10 px-3 py-1 text-xs font-medium text-brand hover:bg-brand/20"
                  >
                    take quiz →
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {!progress?.length && !logs?.length && (
        <Card>
          <CardHeader
            title="Nothing to review yet"
            subtitle="Warnings appear here once you start trading"
          />
          <p className="text-sm text-muted">
            You can get ahead of them in the{" "}
            <Link href="/learn" className="text-brand hover:underline">
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
          <p className="text-sm text-subtle">No interventions yet.</p>
        ) : (
          <ul className="divide-y divide-hairline text-sm">
            {logs.map((l) => {
              const cls = severityClasses(l.severity);
              return (
                <li key={l.id} className="py-3">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls.badge}`}>
                      {l.severity}
                    </span>
                    <strong className={cls.text}>{l.title}</strong>
                    <span className="text-xs text-subtle">
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
                            ? "bg-pos/10 text-pos"
                            : l.user_action === "ignored"
                            ? "bg-warn/10 text-warn"
                            : "bg-elev-3 text-subtle"
                        }`}
                      >
                        {l.user_action === "ignored" ? "overridden" : l.user_action}
                      </span>
                    )}
                  </div>
                  <p className="text-muted">{l.message}</p>
                  {l.concept && (
                    <Link
                      href={`/learn/${l.concept}`}
                      className="mt-1 inline-block text-xs text-brand hover:underline"
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
