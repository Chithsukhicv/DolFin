"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher, type Readiness } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { ReadinessGauge } from "@/components/ReadinessGauge3D";
import { LearningPath } from "@/components/LearningPath";

const SUB_LABELS: Record<string, { label: string; help: string; colour: string }> = {
  diversification: {
    label: "Diversification",
    help: "Spread across stocks and sectors. Penalised if any one stock > 20% or sector > 40%.",
    colour: "#22D3EE",
  },
  discipline: {
    label: "Discipline",
    help: "Low panic-sell rate, low FOMO-buy rate. Heeded warnings boost this.",
    colour: "#A855F7",
  },
  goal_alignment: {
    label: "Goal Alignment",
    help: "Are your trades consistent with your goal horizon?",
    colour: "#4F7CFF",
  },
  autonomy: {
    label: "Autonomy",
    help: "Share of recent trades made without a warn/critical intervention firing.",
    colour: "#10D9A0",
  },
  engagement: {
    label: "Engagement",
    help: "Practising with at least a handful of trades and holdings.",
    colour: "#F5A623",
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

  const score = data?.is_active ? (data?.score ?? 0) : 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <header className="animate-rise">
        <p className="label mb-1" style={{ color: "#A855F7" }}>Progress</p>
        <h1 className="font-display text-2xl font-bold text-white">Investment Readiness</h1>
        <p className="mt-1 text-sm text-muted">
          A 0–100 score across five dimensions. Aim for 80+ before using real money.
        </p>
      </header>

      {/* Main score + breakdown */}
      <div className="grid gap-6 lg:grid-cols-[auto_1fr]">
        {/* Gauge centrepiece */}
        <div
          className="relative flex flex-col items-center justify-center overflow-hidden rounded-2xl px-8 py-6"
          style={{
            background: "rgb(11 11 27 / 0.9)",
            border: "1px solid rgb(168 85 247 / 0.2)",
            boxShadow: "0 0 40px -12px rgb(168 85 247 / 0.25)",
            minWidth: "240px",
          }}
        >
          <div
            className="absolute inset-x-0 top-0 h-px"
            style={{ background: "linear-gradient(90deg, transparent, #A855F7, #22D3EE, transparent)" }}
            aria-hidden
          />
          <ReadinessGauge score={score} size={200} label="Readiness" />

          {data?.graduated && (
            <span
              className="mt-3 rounded-full px-3 py-1 text-xs font-bold"
              style={{
                background: "rgb(16 217 160 / 0.15)",
                border: "1px solid rgb(16 217 160 / 0.3)",
                color: "#10D9A0",
              }}
            >
              ⭐ Graduated — ready for real money
            </span>
          )}
          {!data?.is_active && (
            <p className="mt-3 text-center text-xs text-muted">
              Make your first trade to start tracking
            </p>
          )}
          {data?.provisional && (
            <div
              className="mt-3 rounded-xl px-3 py-2 text-center text-xs"
              style={{
                background: "rgb(245 166 35 / 0.08)",
                border: "1px solid rgb(245 166 35 / 0.2)",
                color: "#F5A623",
              }}
            >
              Provisional — {Math.round((data.confidence ?? 0) * 100)}% confidence
            </div>
          )}
        </div>

        {/* Sub-score breakdown */}
        <div
          className="relative overflow-hidden rounded-2xl p-5"
          style={{
            background: "rgb(11 11 27 / 0.85)",
            border: "1px solid rgb(124 58 237 / 0.2)",
          }}
        >
          <div
            className="absolute inset-x-0 top-0 h-px"
            style={{ background: "linear-gradient(90deg, transparent, #7C3AED, transparent)" }}
            aria-hidden
          />
          <h3 className="font-display text-base font-bold text-white mb-4">Score Breakdown</h3>

          {!data?.is_active ? (
            <div className="flex flex-col items-center justify-center gap-4 py-8">
              <p className="text-sm text-muted text-center">No score yet — make your first practice trade</p>
              <div className="flex gap-3">
                <Link
                  href="/market"
                  className="rounded-xl px-5 py-2.5 text-sm font-semibold"
                  style={{
                    background: "linear-gradient(135deg, #6d28d9, #7c3aed)",
                    color: "#fff",
                    boxShadow: "0 4px 16px -4px rgb(124 58 237 / 0.5)",
                  }}
                >
                  Browse Market →
                </Link>
                <Link
                  href="/learn"
                  className="rounded-xl px-5 py-2.5 text-sm font-semibold"
                  style={{
                    background: "rgb(255 255 255 / 0.04)",
                    border: "1px solid rgb(255 255 255 / 0.1)",
                    color: "#A1A1B5",
                  }}
                >
                  Learn First
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {data &&
                Object.entries(data.breakdown).map(([key, value]) => {
                  const meta = SUB_LABELS[key] ?? { label: key, help: "", colour: "#A855F7" };
                  const weight = (data.weights?.[key] ?? 0) * 100;
                  const v = Math.min(100, Math.max(0, value));
                  return (
                    <div key={key}>
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-sm font-semibold text-white">
                          {meta.label}
                          <span className="ml-2 text-xs font-normal text-muted">
                            {weight.toFixed(0)}% weight
                          </span>
                        </span>
                        <span
                          className="metric text-sm font-bold"
                          style={{ color: meta.colour }}
                        >
                          {v.toFixed(0)}<span className="text-xs text-muted font-normal">/100</span>
                        </span>
                      </div>
                      <div
                        className="h-2 w-full overflow-hidden rounded-full"
                        style={{ background: `${meta.colour}20` }}
                      >
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${v}%`,
                            background: `linear-gradient(90deg, ${meta.colour}80, ${meta.colour})`,
                            boxShadow: `0 0 8px ${meta.colour}60`,
                          }}
                        />
                      </div>
                      {meta.help && (
                        <p className="mt-1.5 text-xs text-muted">{meta.help}</p>
                      )}
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </div>

      {/* How to improve */}
      <div
        className="relative overflow-hidden rounded-2xl p-5"
        style={{
          background: "rgb(11 11 27 / 0.85)",
          border: "1px solid rgb(34 211 238 / 0.15)",
        }}
      >
        <div
          className="absolute inset-x-0 top-0 h-px"
          style={{ background: "linear-gradient(90deg, transparent, #22D3EE, transparent)" }}
          aria-hidden
        />
        <h3 className="font-display text-base font-bold text-white mb-4">How to Improve</h3>
        <ul className="space-y-3 text-sm text-muted">
          {[
            {
              key: "Diversification",
              tip: "Hold 4–5 sectors and keep any single stock under 20% of your portfolio.",
              link: "/learn/diversification",
              colour: "#22D3EE",
            },
            {
              key: "Discipline",
              tip: "When a warning fires, choose Cancel & reflect rather than overriding. Passing a quiz also counts.",
              colour: "#A855F7",
            },
            {
              key: "Discipline",
              tip: "Hold through a simulated crash instead of selling into it.",
              link: "/learn/panic_selling",
              colour: "#A855F7",
            },
            {
              key: "Autonomy",
              tip: "Make trades that don't trigger warnings in the first place.",
              colour: "#10D9A0",
            },
            {
              key: "Goal Alignment",
              tip: "Avoid selling within 7 days of buying if your goal is long-term.",
              colour: "#4F7CFF",
            },
          ].map((item, i) => (
            <li key={i} className="flex items-start gap-3">
              <span
                className="mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
                style={{
                  background: `${item.colour}15`,
                  border: `1px solid ${item.colour}30`,
                  color: item.colour,
                }}
              >
                {item.key}
              </span>
              <span className="text-muted">
                {item.tip}{" "}
                {item.link && (
                  <Link href={item.link} style={{ color: item.colour }}>
                    Read more →
                  </Link>
                )}
              </span>
            </li>
          ))}
        </ul>
        <div
          className="mt-4 rounded-xl px-3 py-2 text-xs text-muted"
          style={{ background: "rgb(124 58 237 / 0.06)", border: "1px solid rgb(124 58 237 / 0.12)" }}
        >
          Penalties count immediately, but credit for good conduct builds as your record grows. Two clean trades isn&apos;t a habit yet.
        </div>
      </div>

      {/* Learning path */}
      <div
        className="relative overflow-hidden rounded-2xl p-5"
        style={{
          background: "rgb(11 11 27 / 0.85)",
          border: "1px solid rgb(168 85 247 / 0.15)",
        }}
      >
        <div
          className="absolute inset-x-0 top-0 h-px"
          style={{ background: "linear-gradient(90deg, transparent, #A855F7, transparent)" }}
          aria-hidden
        />
        <LearningPath userId={userId} />
      </div>
    </div>
  );
}
