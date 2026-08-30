"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher, type Readiness } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";
import { LearningPath } from "@/components/LearningPath";

const SUB_LABELS: Record<string, { label: string; help: string }> = {
  diversification: {
    label: "Diversification",
    help: "Spread across stocks and sectors. Penalised if any one stock > 20% or sector > 40%.",
  },
  discipline: {
    label: "Discipline",
    help: "Low panic-sell rate, low FOMO-buy rate. Heeded warnings boost this.",
  },
  goal_alignment: {
    label: "Goal alignment",
    help: "Are your trades consistent with your goal horizon (long, medium, short)?",
  },
  autonomy: {
    label: "Autonomy",
    help: "Share of recent trades made without a warn/critical intervention firing.",
  },
  engagement: {
    label: "Engagement",
    help: "Sanity floor — practising with at least a handful of trades and holdings.",
  },
};

export default function ReadinessPage() {
  const userId = useRequireUser();

  const { data } = useSWR<Readiness>(
    userId ? `/readiness/${userId}` : null,
    fetcher,
    { refreshInterval: 8000 },
  );

  if (!userId) return null;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Investment Readiness</h1>
        <p className="text-sm text-slate-500">
          A 0-100 score across five dimensions. Aim for 80+ before using real money.
        </p>
      </header>

      <Card>
        {data && !data.is_active ? (
          <div className="py-8 text-center">
            <p className="text-xs uppercase tracking-wide text-slate-500">Your score</p>
            <p className="mt-1 text-6xl font-bold text-slate-300">
              —<span className="text-2xl font-medium">/100</span>
            </p>
            <p className="mx-auto mt-3 max-w-md text-sm text-slate-600">
              You haven&apos;t placed any practice trades yet. Your Readiness Score starts
              measuring as soon as you make your first trade.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Link
                href="/market"
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
              >
                Browse the market →
              </Link>
              <Link
                href="/learn"
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Learn the basics first
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid items-center gap-6 md:grid-cols-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Your score</p>
              <p className="mt-1 text-6xl font-bold">
                {data ? data.score.toFixed(0) : "—"}
                <span className="text-2xl font-medium text-slate-400">/100</span>
              </p>
              {data?.graduated ? (
                <p className="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-800">
                  ⭐ Graduated — you&apos;re ready to start with real money
                </p>
              ) : (
                <p className="mt-2 text-sm text-slate-600">
                  Graduation threshold: {data?.graduation_threshold ?? 80}+
                </p>
              )}

              {/* Being explicit that an early score is provisional matters:
                  presenting a two-trade number as final would mislead exactly
                  the beginners this product exists to help. */}
              {data?.provisional && (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  <p className="font-medium">This score is still provisional</p>
                  <p className="mt-1">
                    Readiness measures habits, and habits need a track record. We&apos;re{" "}
                    {Math.round(data.confidence * 100)}% confident so far.
                    {data.evidence_needed.trades > 0 && (
                      <> {data.evidence_needed.trades} more trades</>
                    )}
                    {data.evidence_needed.trades > 0 &&
                      data.evidence_needed.holdings > 0 &&
                      " and"}
                    {data.evidence_needed.holdings > 0 && (
                      <> {data.evidence_needed.holdings} more holdings</>
                    )}{" "}
                    will give a reliable reading.
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-3">
              {data &&
                Object.entries(data.breakdown).map(([key, value]) => {
                  const meta = SUB_LABELS[key] ?? { label: key, help: "" };
                  const weight = (data.weights[key] ?? 0) * 100;
                  return (
                    <div key={key}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span className="font-medium">
                          {meta.label}{" "}
                          <span className="text-xs font-normal text-slate-500">
                            (weight {weight.toFixed(0)}%)
                          </span>
                        </span>
                        <span className="font-semibold">{value.toFixed(0)}/100</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-indigo-500"
                          style={{ width: `${value}%` }}
                        />
                      </div>
                      {meta.help && (
                        <p className="mt-1 text-xs text-slate-500">{meta.help}</p>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="How to improve"
          subtitle="Each suggestion maps to one of the five sub-scores"
        />
        <ul className="space-y-2 text-sm text-slate-700">
          <li>
            <strong>Diversification:</strong> hold 4–5 sectors and keep any single stock under
            20% of your portfolio.{" "}
            <Link href="/learn/diversification" className="text-indigo-600 underline">
              Read more
            </Link>
          </li>
          <li>
            <strong>Discipline:</strong> when a warning fires, choose{" "}
            <em>Cancel &amp; reflect</em> rather than overriding. Passing a concept quiz also
            counts.
          </li>
          <li>
            <strong>Discipline:</strong> hold through a simulated crash instead of selling into
            it.{" "}
            <Link href="/learn/panic_selling" className="text-indigo-600 underline">
              Why this matters
            </Link>
          </li>
          <li>
            <strong>Autonomy:</strong> make trades that don&apos;t trigger warnings in the first
            place.
          </li>
          <li>
            <strong>Goal alignment:</strong> avoid selling within 7 days of buying if your goal
            is long-term.
          </li>
        </ul>
        <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
          Penalties count immediately, but credit for good conduct builds up as your track
          record grows. That&apos;s deliberate — two clean trades isn&apos;t yet a habit.
        </p>
      </Card>

      <Card>
        <LearningPath userId={userId} />
      </Card>
    </div>
  );
}
