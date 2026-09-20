"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { ai, type BehaviourPattern, type PatternAnalysis } from "@/lib/api";
import { Card, CardHeader } from "@/components/Card";
import { AdvisoryNote, AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";
import { EmptyState, ErrorState, LoadingCard } from "@/components/States";

/**
 * The habit, named.
 *
 * Everything else on the coach page is a list of individual events. This reads
 * across the whole record and says the thing a per-trade warning cannot:
 * "you've sold four times in three weeks, every one within two days of a dip —
 * your stock picking is fine, small dips make you flinch."
 *
 * The counted facts the analysis was built from are shown alongside it, on
 * purpose. A learner should be able to check the claim rather than take it on
 * faith, and every number in a pattern comes from that list.
 */

export function PatternPanel({ userId }: { userId: string }) {
  const [refreshing, setRefreshing] = useState(false);
  const { data, error, mutate, isLoading } = useSWR<PatternAnalysis>(
    userId ? ["patterns", userId] : null,
    () => ai.patterns(userId),
    { revalidateOnFocus: false },
  );

  async function recompute() {
    setRefreshing(true);
    try {
      await mutate(() => ai.patterns(userId, true), { revalidate: false });
    } finally {
      setRefreshing(false);
    }
  }

  if (isLoading) return <LoadingCard lines={4} />;
  if (error) {
    return <ErrorState error={error} label="Couldn't read your patterns" onRetry={() => mutate()} />;
  }
  if (!data) return null;

  if (data.status === "insufficient_activity") {
    return (
      <Card>
        <CardHeader
          title="Your patterns"
          subtitle="What you keep doing, across your whole history"
        />
        <EmptyState title="Not enough history yet">
          <p>{data.message}</p>
          {typeof data.trades_needed === "number" && data.trades_needed > 0 && (
            <p className="mt-1">
              About {data.trades_needed} more trade{data.trades_needed === 1 ? "" : "s"} should
              be enough.
            </p>
          )}
        </EmptyState>
      </Card>
    );
  }

  if (data.status === "unavailable") {
    return (
      <Card>
        <CardHeader title="Your patterns" subtitle="Temporarily unavailable" />
        <p className="text-sm text-slate-600">{data.message}</p>
      </Card>
    );
  }

  // Strengths last: the thing to work on belongs at the top, but nobody should
  // reach the end of this panel having read only criticism.
  const ordered = [...data.patterns].sort(
    (a, b) => Number(a.is_strength) - Number(b.is_strength),
  );

  return (
    <Card>
      <CardHeader
        title="Your patterns"
        subtitle="What you keep doing, read across your whole history"
        right={
          <div className="flex items-center gap-2">
            <AiBadge mode={data.mode} />
            <button
              onClick={recompute}
              disabled={refreshing}
              className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              {refreshing ? "Rethinking…" : "Recompute"}
            </button>
          </div>
        }
      />

      <div className="space-y-3">
        {ordered.map((p) => (
          <PatternCard key={p.label} pattern={p} />
        ))}
      </div>

      {hasEvidence(data.evidence) && <EvidenceDetails evidence={data.evidence} />}
      <AdvisoryNote />
      <AiDisclaimer />
    </Card>
  );
}

/** The backend sends `{}` when it couldn't compute the counts at all. */
function hasEvidence(
  evidence: PatternAnalysis["evidence"],
): evidence is import("@/lib/api").PatternEvidence {
  return "trades" in evidence;
}

function PatternCard({ pattern }: { pattern: BehaviourPattern }) {
  const tone = pattern.is_strength
    ? "border-emerald-200 bg-emerald-50"
    : "border-amber-200 bg-amber-50";

  return (
    <div className={`rounded-xl border p-4 ${tone}`}>
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
            pattern.is_strength
              ? "bg-emerald-200 text-emerald-800"
              : "bg-amber-200 text-amber-900"
          }`}
        >
          {pattern.is_strength ? "doing well" : "worth working on"}
        </span>
        <strong className="text-slate-900">{pattern.label}</strong>
      </div>

      <p className="text-sm text-slate-800">{pattern.insight}</p>

      {pattern.evidence.length > 0 && (
        <ul className="mt-2 space-y-1">
          {pattern.evidence.map((e, i) => (
            <li key={i} className="text-xs text-slate-600">
              · {e}
            </li>
          ))}
        </ul>
      )}

      {pattern.next_action && (
        <p className="mt-2 text-sm font-medium text-slate-800">
          Next: {pattern.next_action}
        </p>
      )}

      {pattern.concept && (
        <Link
          href={`/learn/${pattern.concept}`}
          className="mt-2 inline-block text-xs font-medium text-indigo-700 underline underline-offset-2"
        >
          Read about {pattern.concept.replaceAll("_", " ")} →
        </Link>
      )}

      <Citations citations={pattern.citations ?? []} />
    </div>
  );
}

/** The raw counts, collapsed. Lets a learner audit any number in a pattern. */
function EvidenceDetails({
  evidence,
}: {
  evidence: import("@/lib/api").PatternEvidence;
}) {
  const [open, setOpen] = useState(false);

  const rows: Array<[string, string]> = [
    ["Trades", `${evidence.trades} (${evidence.buys} buys, ${evidence.sells} sells)`],
    [
      "Activity span",
      evidence.activity_span_days === null
        ? "—"
        : `${evidence.activity_span_days} days`,
    ],
    ["Sells during a simulated event", String(evidence.sells_during_a_scenario)],
    ["Sells within 7 days of buying", String(evidence.sells_within_7_days)],
    [
      "Holdings",
      `${evidence.holdings} across ${evidence.distinct_sectors} sector${
        evidence.distinct_sectors === 1 ? "" : "s"
      }`,
    ],
    [
      "Warnings",
      `${evidence.warnings_fired} fired · ${evidence.warnings_resolved} resolved · ${evidence.warnings_heeded} heeded`,
    ],
    ["Quizzes passed", evidence.quizzes_passed.join(", ") || "none"],
  ];

  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-700"
      >
        <span aria-hidden>{open ? "▾" : "▸"}</span>
        The numbers this was computed from
      </button>

      {open && (
        <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-3">
              <dt className="text-slate-500">{label}</dt>
              <dd className="text-right font-medium text-slate-700">{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
