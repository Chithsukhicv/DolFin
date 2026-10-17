"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher, type Readiness } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";
import { LearningPath } from "@/components/LearningPath";

const SUB_LABELS: Record<string, { label: string; help: string; icon: string }> = {
  diversification: {
    label: "Diversification",
    help: "Spread across stocks and sectors. Penalised if any one stock > 20% or sector > 40%.",
    icon: "🌐",
  },
  discipline: {
    label: "Discipline",
    help: "Low panic-sell rate, low FOMO-buy rate. Heeded warnings boost this.",
    icon: "🛡️",
  },
  goal_alignment: {
    label: "Goal alignment",
    help: "Are your trades consistent with your goal horizon (long, medium, short)?",
    icon: "🎯",
  },
  autonomy: {
    label: "Autonomy",
    help: "Share of recent trades made without a warn/critical intervention firing.",
    icon: "⚡",
  },
  engagement: {
    label: "Engagement",
    help: "Sanity floor — practising with at least a handful of trades and holdings.",
    icon: "📈",
  },
  consistency: {
    label: "Consistency",
    help: "Regular activity across multiple sessions over time.",
    icon: "🔄",
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

  const score = data?.score ?? 0;
  const isActive = data?.is_active ?? false;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-bold text-white">Investment Readiness</h1>
        <p className="mt-1 text-sm text-muted">
          A 0–100 score across five dimensions. Aim for 80+ before using real money.
        </p>
      </header>

      {/* ── Main score card ── */}
      <Card className="overflow-hidden">
        {data && !isActive ? (
          <div className="py-8 text-center">
            <p className="label mb-2">Your score</p>
            <div className="mx-auto my-4 flex h-40 w-40 items-center justify-center">
              <ScoreGauge score={0} inactive />
            </div>
            <p className="mx-auto mt-3 max-w-md text-sm text-muted">
              You haven&apos;t placed any practice trades yet. Your Readiness Score starts
              measuring as soon as you make your first trade.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Link href="/market" className="btn-primary rounded-lg px-4 py-2 text-sm font-semibold">
                Browse the market →
              </Link>
              <Link href="/learn" className="btn-ghost rounded-lg px-4 py-2 text-sm font-medium">
                Learn the basics first
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid items-center gap-8 md:grid-cols-2">
            {/* Left: big score gauge */}
            <div className="flex flex-col items-center py-4">
              <p className="label mb-4">Your score</p>
              <ScoreGauge score={score} />
              <div className="mt-4 text-center">
                {data?.graduated ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-pos/30 bg-pos/10 px-3 py-1 text-sm font-medium text-pos">
                    🎓 Graduated — ready for real money
                  </span>
                ) : (
                  <p className="text-sm text-muted">
                    Target: <span className="font-medium text-fg">{data?.graduation_threshold ?? 80}+</span>
                  </p>
                )}
                {data?.provisional && (
                  <div className="mt-3 rounded-xl border border-warn/25 bg-warn/8 p-3 text-xs text-warn">
                    <p className="font-semibold">Provisional score</p>
                    <p className="mt-1 text-warn/80">
                      {Math.round((data.confidence ?? 0) * 100)}% confident so far.
                      {data.evidence_needed.trades > 0 && <> {data.evidence_needed.trades} more trades</>}
                      {data.evidence_needed.trades > 0 && data.evidence_needed.holdings > 0 && " and"}
                      {data.evidence_needed.holdings > 0 && <> {data.evidence_needed.holdings} more holdings</>}
                      {" "}will give a reliable reading.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Right: dimension bars */}
            <div className="space-y-4">
              {data &&
                Object.entries(data.breakdown).map(([key, value]) => {
                  const meta = SUB_LABELS[key] ?? { label: key, help: "", icon: "•" };
                  const weight = (data.weights[key] ?? 0) * 100;
                  const barColour =
                    value >= 70 ? "#00D6A0" : value >= 40 ? "#6C63FF" : "#FF6B6B";
                  return (
                    <div key={key}>
                      <div className="mb-1.5 flex justify-between text-sm">
                        <span className="flex items-center gap-1.5 font-medium text-fg">
                          <span aria-hidden>{meta.icon}</span>
                          {meta.label}
                          <span className="text-xs font-normal text-subtle">
                            ({weight.toFixed(0)}%)
                          </span>
                        </span>
                        <span className="font-mono text-sm font-semibold" style={{ color: barColour }}>
                          {value.toFixed(0)}
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-elev-3">
                        <div
                          className="h-full rounded-full transition-all duration-700 ease-out"
                          style={{
                            width: `${value}%`,
                            background: barColour,
                            boxShadow: `0 0 8px ${barColour}60`,
                          }}
                        />
                      </div>
                      {meta.help && (
                        <p className="mt-1 text-xs text-subtle">{meta.help}</p>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </Card>

      {/* ── How to improve ── */}
      <Card>
        <CardHeader
          title="How to improve"
          subtitle="Each suggestion maps to one of the five sub-scores"
        />
        <ul className="space-y-3 text-sm">
          {[
            {
              dim: "Diversification",
              text: "Hold 4–5 sectors and keep any single stock under 20% of your portfolio.",
              href: "/learn/diversification",
            },
            {
              dim: "Discipline",
              text: 'When a warning fires, choose "Cancel & reflect" rather than overriding. Passing a concept quiz also counts.',
            },
            {
              dim: "Discipline",
              text: "Hold through a simulated crash instead of selling into it.",
              href: "/learn/panic_selling",
            },
            {
              dim: "Autonomy",
              text: "Make trades that don't trigger warnings in the first place.",
            },
            {
              dim: "Goal alignment",
              text: "Avoid selling within 7 days of buying if your goal is long-term.",
            },
          ].map((tip, i) => (
            <li key={i} className="flex gap-3">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand/15 text-[10px] font-bold text-brand">
                {i + 1}
              </span>
              <span className="text-muted">
                <strong className="text-fg">{tip.dim}:</strong> {tip.text}
                {tip.href && (
                  <>
                    {" "}
                    <Link href={tip.href} className="text-brand hover:underline">
                      Read more →
                    </Link>
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-4 rounded-xl border border-hairline bg-elev-2 p-3 text-xs text-subtle">
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

/* ── Score Gauge SVG ── */
function ScoreGauge({ score, inactive = false }: { score: number; inactive?: boolean }) {
  const size = 160;
  const r = 66;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const arcLen = circumference * 0.75; // 270°
  const offset = inactive ? arcLen : arcLen - (score / 100) * arcLen;

  const colour = inactive
    ? "rgba(255,255,255,0.1)"
    : score >= 80
    ? "#00D6A0"
    : score >= 50
    ? "#6C63FF"
    : "#FF6B6B";

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-label={inactive ? "Score not available" : `Readiness score ${score.toFixed(0)} out of 100`}
      role="img"
    >
      {/* Glow filter */}
      <defs>
        <filter id="gaugeGlow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      {/* Track */}
      <circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke="rgba(255,255,255,0.07)"
        strokeWidth={10}
        strokeDasharray={`${arcLen} ${circumference}`}
        strokeLinecap="round"
        transform={`rotate(135 ${cx} ${cy})`}
      />
      {/* Fill */}
      {!inactive && (
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={colour}
          strokeWidth={10}
          strokeDasharray={`${arcLen} ${circumference}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(135 ${cx} ${cy})`}
          filter="url(#gaugeGlow)"
          style={{
            transition: "stroke-dashoffset 1.4s cubic-bezier(0.16,1,0.3,1)",
          }}
        />
      )}
      {/* Score text */}
      {inactive ? (
        <text x={cx} y={cy + 8} textAnchor="middle" fontSize="28" fontWeight="700"
          fontFamily="var(--font-mono)" fill="rgba(255,255,255,0.2)">—</text>
      ) : (
        <>
          <text x={cx} y={cy + 5} textAnchor="middle" fontSize="36" fontWeight="800"
            fontFamily="var(--font-mono)" fill={colour}>
            {score.toFixed(0)}
          </text>
          <text x={cx} y={cy + 22} textAnchor="middle" fontSize="13"
            fontFamily="var(--font-mono)" fill="rgba(255,255,255,0.35)">/100</text>
        </>
      )}
    </svg>
  );
}
