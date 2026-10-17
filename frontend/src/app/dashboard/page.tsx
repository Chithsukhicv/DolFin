"use client";

import { useEffect } from "react";
import Link from "next/link";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { WebGLCanvas } from "@/components/three/WebGLCanvas";

const DashboardScene = dynamic(
  () => import("@/components/three/DashboardScene").then((m) => m.DashboardScene),
  { ssr: false }
);
import {
  fetcher,
  type Portfolio,
  type Readiness,
  type Transaction,
  type User,
} from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { rupees, pct } from "@/lib/format";
import { Card, CardHeader } from "@/components/Card";
import { EquityCurve } from "@/components/EquityCurve";
import { LearningPath } from "@/components/LearningPath";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

const SECTOR_COLOURS = [
  "#6C63FF",
  "#40D9FF",
  "#00D6A0",
  "#f59e0b",
  "#ef4444",
  "#a855f7",
  "#14b8a6",
  "#f97316",
  "#84cc16",
  "#ec4899",
  "#22d3ee",
  "#facc15",
];

export default function DashboardPage() {
  const router = useRouter();
  const userId = useRequireUser();

  const { data: user, error: userError } = useSWR<User>(
    userId ? `/users/${userId}` : null,
    fetcher,
  );

  useEffect(() => {
    if (userError) {
      router.replace("/");
    }
  }, [userError, router]);

  const { data: pf } = useSWR<Portfolio>(
    userId ? `/portfolio/${userId}` : null,
    fetcher,
    { refreshInterval: 10000 },
  );
  const { data: readiness } = useSWR<Readiness>(
    userId ? `/readiness/${userId}` : null,
    fetcher,
    { refreshInterval: 10000 },
  );
  const { data: txns } = useSWR<Transaction[]>(
    userId ? `/history/transactions/${userId}?limit=5` : null,
    fetcher,
  );

  if (!userId) return null;
  if (userError) return null;

  const sectorData = pf
    ? Object.entries(pf.sector_allocation_pct).map(([name, value]) => ({
        name,
        value: Math.round(value * 10) / 10,
      }))
    : [];

  const pnlUp = (pf?.unrealised_pnl ?? 0) >= 0;
  const scoreActive = readiness?.is_active;
  const scoreValue = readiness?.score ?? 0;

  return (
    <div className="space-y-6">
      {/* ── Hero header ── */}
      <header className="relative overflow-hidden rounded-2xl border border-hairline bg-gradient-to-br from-[#0D1220] to-[#0a0d16] p-6">
        <div className="aurora" aria-hidden />
        <div className="relative z-10">
          <p className="label mb-1">Welcome back</p>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-white">
            Hi {user?.display_name || "there"} 👋
          </h1>
          <p className="mt-1 text-sm text-muted">
            Practising as{" "}
            <span className="font-medium capitalize text-fg">{user?.persona}</span>
            {" · "}risk:{" "}
            <span className="font-medium capitalize text-fg">{user?.risk_appetite}</span>
          </p>
        </div>
        {/* Readiness badge floating right */}
        {scoreActive && (
          <div className="absolute right-6 top-1/2 hidden -translate-y-1/2 flex-col items-center lg:flex">
            <WebGLCanvas
              className="h-[220px] w-[220px]"
              camera={{ position: [0, 0, 6], fov: 55 }}
            >
              <DashboardScene score={scoreValue} />
            </WebGLCanvas>
          </div>
        )}
      </header>

      {/* ── Learning path nudge ── */}
      <LearningPath userId={userId} compact />

      {/* ── Stale price warning ── */}
      {pf && pf.stale_price_count > 0 && (
        <p
          role="status"
          className="rounded-xl border border-warn/30 bg-warn/8 px-4 py-3 text-sm text-warn"
        >
          {pf.stale_price_count === 1
            ? "One holding is priced from cache"
            : `${pf.stale_price_count} holdings are priced from cache`}{" "}
          — values may be slightly behind.
        </p>
      )}

      {/* ── Metric cards ── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total value"
          value={pf ? rupees(pf.total_value) : "—"}
          delta={pf ? `${pnlUp ? "+" : ""}${pct(pf.unrealised_pnl / (pf.total_value || 1))}` : undefined}
          tone={pnlUp ? "positive" : "negative"}
          hint="portfolio + cash"
        />
        <MetricCard
          label="Unrealised P&L"
          value={pf ? rupees(pf.unrealised_pnl) : "—"}
          tone={(pf?.unrealised_pnl ?? 0) >= 0 ? "positive" : "negative"}
          hint="on open positions"
        />
        <MetricCard
          label="Cash available"
          value={pf ? rupees(pf.cash) : "—"}
          hint={pf ? `Invested: ${rupees(pf.invested)}` : undefined}
        />
        <MetricCard
          label="Readiness"
          value={
            scoreActive
              ? `${scoreValue.toFixed(0)}`
              : "—"
          }
          suffix={scoreActive ? "/100" : undefined}
          hint={
            scoreActive
              ? readiness?.provisional
                ? "Provisional score"
                : readiness?.graduated
                ? "Graduated 🎓"
                : `Target: ${readiness?.graduation_threshold ?? 80}+`
              : "Make your first trade"
          }
          tone={
            !scoreActive
              ? "neutral"
              : scoreValue >= 80
              ? "positive"
              : scoreValue < 40
              ? "negative"
              : "neutral"
          }
          href="/readiness"
        />
      </div>

      {/* ── 3D Readiness Instrument ── */}
      {scoreActive && (
        <div className="relative overflow-hidden rounded-2xl border border-hairline bg-gradient-to-br from-[#0D1220] to-[#080B12]">
          <div className="flex flex-col items-center justify-between gap-4 p-4 md:flex-row">
            <div className="z-10 flex-1 md:pl-4">
              <p className="label mb-1 text-brand">Investment Readiness</p>
              <h2 className="font-display text-2xl font-bold text-white">
                Score: {scoreValue.toFixed(0)} / 100
              </h2>
              <p className="mt-1 text-sm text-muted">
                {readiness?.graduated
                  ? "🎓 Graduated — ready for real money"
                  : readiness?.provisional
                  ? "Provisional — keep trading to build confidence"
                  : "Keep practising to raise your score"}
              </p>
              <Link href="/readiness" className="mt-3 inline-block text-sm text-brand hover:underline">
                Full breakdown →
              </Link>
            </div>
            <WebGLCanvas
              className="h-[260px] w-full md:w-[260px]"
              camera={{ position: [0, 0, 6], fov: 55 }}
            >
              <DashboardScene score={scoreValue} />
            </WebGLCanvas>
          </div>
        </div>
      )}

      {/* ── Equity curve ── */}
      <Card>
        <CardHeader
          title="Portfolio value over time"
          subtitle="Every trade and scenario change is recorded here"
        />
        <EquityCurve userId={userId} />
      </Card>

      {/* ── Sector allocation + Recent activity ── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Sector allocation"
            subtitle="Spread across sectors lowers single-industry risk"
            right={
              <Link href="/portfolio" className="text-sm text-brand hover:underline">
                Holdings →
              </Link>
            }
          />
          {sectorData.length === 0 ? (
            <p className="text-sm text-muted">
              No holdings yet. Buy your first stock from the{" "}
              <Link href="/market" className="text-brand hover:underline">
                Market page
              </Link>
              .
            </p>
          ) : (
            <div className="flex items-center gap-6">
              <div className="h-48 w-48 shrink-0">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={sectorData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={45}
                      outerRadius={75}
                      stroke="rgba(255,255,255,0.06)"
                      strokeWidth={2}
                      paddingAngle={2}
                    >
                      {sectorData.map((_, i) => (
                        <Cell
                          key={i}
                          fill={SECTOR_COLOURS[i % SECTOR_COLOURS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v) => [`${Number(v).toFixed(1)}%`, "Allocation"]}
                      contentStyle={{
                        background: "var(--elev-3)",
                        border: "1px solid var(--hairline-strong)",
                        borderRadius: 10,
                        color: "var(--fg)",
                        fontSize: 12,
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="flex-1 space-y-1.5 text-sm">
                {sectorData.map((s, i) => (
                  <li key={s.name} className="flex items-center gap-2">
                    <span
                      className="inline-block h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: SECTOR_COLOURS[i % SECTOR_COLOURS.length] }}
                    />
                    <span className="flex-1 truncate text-muted">{s.name}</span>
                    <span className="font-mono text-xs font-medium text-fg">
                      {pct(s.value, 1)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Recent activity"
            right={
              <Link href="/coach" className="text-sm text-brand hover:underline">
                See all →
              </Link>
            }
          />
          {txns && txns.length > 0 ? (
            <ul className="divide-y divide-hairline text-sm">
              {txns.map((t) => (
                <li key={t.id} className="flex items-center justify-between py-2.5">
                  <div className="flex items-center gap-2.5">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                        t.side === "buy"
                          ? "bg-pos/15 text-pos"
                          : "bg-neg/15 text-neg"
                      }`}
                    >
                      {t.side}
                    </span>
                    <span className="text-fg">
                      {t.quantity} × {t.symbol}
                    </span>
                  </div>
                  <span className="font-mono text-sm text-muted">{rupees(t.price)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No trades yet.</p>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ── Inline metric card ── */
function MetricCard({
  label,
  value,
  delta,
  suffix,
  hint,
  tone = "neutral",
  href,
}: {
  label: string;
  value: string;
  delta?: string;
  suffix?: string;
  hint?: string;
  tone?: "neutral" | "positive" | "negative";
  href?: string;
}) {
  const accentClass = {
    neutral: "",
    positive: "text-pos",
    negative: "text-neg",
  }[tone];

  const deltaBg = {
    neutral: "bg-elev-3 text-muted border-hairline",
    positive: "bg-pos/10 text-pos border-pos/25",
    negative: "bg-neg/10 text-neg border-neg/25",
  }[tone];

  const inner = (
    <div className="card card-sheen hover-lift rounded-2xl p-5">
      <p className="label">{label}</p>
      <div className="mt-2 flex items-baseline gap-2">
        <span className={`metric text-2xl font-bold ${accentClass || "text-white"}`}>
          {value}
        </span>
        {suffix && <span className="text-sm text-subtle">{suffix}</span>}
        {delta && (
          <span className={`rounded-md border px-1.5 py-0.5 font-mono text-xs font-medium ${deltaBg}`}>
            {delta}
          </span>
        )}
      </div>
      {hint && <p className="mt-1.5 text-xs text-subtle">{hint}</p>}
    </div>
  );

  return href ? (
    <Link href={href} className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:rounded-2xl">
      {inner}
    </Link>
  ) : (
    inner
  );
}

/* ── Mini readiness gauge (SVG arc) ── */
function ReadinessGauge({ score, size = 80 }: { score: number; size?: number }) {
  const r = (size - 10) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  // Only fill 270° of the circle (leave a gap at the bottom)
  const arcLen = circumference * 0.75;
  const offset = arcLen - (score / 100) * arcLen;
  const colour = score >= 80 ? "#00D6A0" : score >= 50 ? "#6C63FF" : "#FF6B6B";

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-label={`Readiness score ${score.toFixed(0)} out of 100`}
      role="img"
    >
      {/* Track */}
      <circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke="rgba(255,255,255,0.08)"
        strokeWidth={6}
        strokeDasharray={`${arcLen} ${circumference}`}
        strokeLinecap="round"
        transform={`rotate(135 ${cx} ${cy})`}
      />
      {/* Fill */}
      <circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke={colour}
        strokeWidth={6}
        strokeDasharray={`${arcLen} ${circumference}`}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(135 ${cx} ${cy})`}
        className="gauge-arc"
        style={{
          ["--gauge-empty" as string]: arcLen,
          ["--gauge-offset" as string]: offset,
          transition: "stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1)",
        }}
      />
      {/* Label */}
      <text
        x={cx} y={cy + 5}
        textAnchor="middle"
        fontSize={size * 0.22}
        fontWeight="700"
        fontFamily="var(--font-mono)"
        fill={colour}
      >
        {score.toFixed(0)}
      </text>
    </svg>
  );
}
