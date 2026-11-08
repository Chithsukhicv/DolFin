"use client";

import { useEffect } from "react";
import Link from "next/link";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import {
  fetcher,
  type Portfolio,
  type Readiness,
  type Transaction,
  type User,
} from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { rupees, pct } from "@/lib/format";
import { EquityCurve } from "@/components/EquityCurve";
import { LearningPath } from "@/components/LearningPath";
import { ReadinessGauge } from "@/components/ReadinessGauge3D";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

const SECTOR_COLOURS = [
  "#A855F7", "#22D3EE", "#4F7CFF", "#10D9A0",
  "#F25767", "#F5A623", "#7C3AED", "#06B6D4",
  "#8B5CF6", "#34D399", "#FB923C", "#E879F9",
];

function GlowMetric({
  label,
  value,
  sub,
  tone = "purple",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "purple" | "cyan" | "green" | "red";
}) {
  const colours = {
    purple: { accent: "#A855F7", glow: "rgb(168 85 247 / 0.25)", border: "rgb(168 85 247 / 0.2)" },
    cyan:   { accent: "#22D3EE", glow: "rgb(34 211 238 / 0.2)",  border: "rgb(34 211 238 / 0.2)" },
    green:  { accent: "#10D9A0", glow: "rgb(16 217 160 / 0.2)",  border: "rgb(16 217 160 / 0.2)" },
    red:    { accent: "#F25767", glow: "rgb(242 87 103 / 0.2)",  border: "rgb(242 87 103 / 0.2)" },
  }[tone];

  return (
    <div
      className="relative overflow-hidden rounded-2xl p-5 flex flex-col justify-between"
      style={{
        background: "rgb(11 11 27 / 0.85)",
        border: `1px solid ${colours.border}`,
        boxShadow: `0 0 24px -8px ${colours.glow}, inset 0 1px 0 ${colours.border}`,
      }}
    >
      {/* Top edge glow */}
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: `linear-gradient(90deg, transparent, ${colours.accent}, transparent)` }}
        aria-hidden
      />
      <p className="label" style={{ color: colours.accent }}>{label}</p>
      <p
        className="metric mt-3 font-bold"
        style={{
          fontSize: "clamp(1.6rem, 2.5vw, 2.2rem)",
          color: "#F8FAFC",
          textShadow: `0 0 24px ${colours.glow}`,
        }}
      >
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const userId = useRequireUser();

  const { data: user, error: userError } = useSWR<User>(
    userId ? `/users/${userId}` : null,
    fetcher,
  );

  useEffect(() => {
    if (userError) router.replace("/");
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

  const readinessScore = readiness?.is_active ? readiness.score : 0;
  const pnlPositive = (pf?.unrealised_pnl ?? 0) >= 0;

  return (
    <div className="space-y-8">
      {/* ── Page Header ── */}
      <header className="animate-rise flex items-center justify-between gap-4">
        <div>
          <p className="label mb-1" style={{ color: "#A855F7" }}>Command Centre</p>
          <h1 className="font-display text-2xl font-bold text-white">
            Hi {user?.display_name || "there"} 👋
          </h1>
          <p className="mt-1 text-sm text-muted">
            Practising as <span className="font-medium text-white capitalize">{user?.persona}</span>
            {" · "}risk{" "}
            <span className="font-medium capitalize" style={{ color: "#A855F7" }}>{user?.risk_appetite}</span>
          </p>
        </div>
        <Link
          href="/market"
          className="btn-primary hidden sm:inline-flex items-center gap-2 rounded-2xl px-5 py-2.5 text-sm font-semibold"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          Trade
        </Link>
      </header>

      {/* ── Learning Path ── */}
      <div className="animate-rise" style={{ animationDelay: "60ms" }}>
        <LearningPath userId={userId} compact />
      </div>

      {/* ── Stale warning ── */}
      {pf && pf.stale_price_count > 0 && (
        <div
          role="status"
          className="rounded-xl px-4 py-3 text-sm"
          style={{
            background: "rgb(245 166 35 / 0.08)",
            border: "1px solid rgb(245 166 35 / 0.25)",
            color: "#F5A623",
          }}
        >
          {pf.stale_price_count === 1
            ? "One holding is priced from cache"
            : `${pf.stale_price_count} holdings are priced from cache`}{" "}
          — values may be slightly behind.
        </div>
      )}

      {/* ── Primary Metrics Row ── */}
      <div className="stagger grid gap-4 md:grid-cols-3">
        <GlowMetric
          label="Total Portfolio Value"
          value={pf ? rupees(pf.total_value) : "—"}
          sub={
            pf
              ? `Unrealised P&L: ${rupees(pf.unrealised_pnl)}`
              : "Loading…"
          }
          tone={pnlPositive ? "green" : "red"}
        />
        <GlowMetric
          label="Cash Available"
          value={pf ? rupees(pf.cash) : "—"}
          sub={pf ? `Invested: ${rupees(pf.invested)}` : "Loading…"}
          tone="cyan"
        />
        <div
          className="relative overflow-hidden rounded-2xl p-5 flex flex-col items-center justify-center gap-2"
          style={{
            background: "rgb(11 11 27 / 0.85)",
            border: "1px solid rgb(168 85 247 / 0.2)",
            boxShadow: "0 0 32px -8px rgb(168 85 247 / 0.2), inset 0 1px 0 rgb(168 85 247 / 0.1)",
          }}
        >
          <div
            className="absolute inset-x-0 top-0 h-px"
            style={{ background: "linear-gradient(90deg, transparent, #A855F7, transparent)" }}
            aria-hidden
          />
          <ReadinessGauge
            score={readinessScore}
            size={140}
            label="Readiness"
          />
          {readiness && !readiness.is_active && (
            <p className="text-xs text-muted text-center">Make your first trade to start tracking</p>
          )}
          {readiness?.is_active && (
            <Link
              href="/readiness"
              className="mt-1 text-xs font-medium transition"
              style={{ color: "#22D3EE" }}
            >
              View full breakdown →
            </Link>
          )}
          {readiness?.graduated && (
            <span
              className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
              style={{
                background: "rgb(16 217 160 / 0.15)",
                border: "1px solid rgb(16 217 160 / 0.3)",
                color: "#10D9A0",
              }}
            >
              ⭐ Ready for real money
            </span>
          )}
        </div>
      </div>

      {/* ── Equity Curve ── */}
      <div
        className="animate-rise relative overflow-hidden rounded-2xl p-5"
        style={{
          background: "rgb(11 11 27 / 0.85)",
          border: "1px solid rgb(124 58 237 / 0.2)",
          boxShadow: "0 0 24px -8px rgb(124 58 237 / 0.15)",
          animationDelay: "120ms",
        }}
      >
        <div
          className="absolute inset-x-0 top-0 h-px"
          style={{ background: "linear-gradient(90deg, transparent, #7C3AED 30%, #22D3EE 70%, transparent)" }}
          aria-hidden
        />
        <div className="mb-4">
          <p className="label mb-1" style={{ color: "#A855F7" }}>Performance</p>
          <h3 className="font-display text-base font-bold text-white">Portfolio Value Over Time</h3>
          <p className="mt-0.5 text-xs text-muted">Every trade and scenario change recorded here</p>
        </div>
        <EquityCurve userId={userId} />
      </div>

      {/* ── Allocation + Activity row ── */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Sector Allocation */}
        <div
          className="relative overflow-hidden rounded-2xl p-5"
          style={{
            background: "rgb(11 11 27 / 0.85)",
            border: "1px solid rgb(34 211 238 / 0.15)",
            boxShadow: "0 0 24px -8px rgb(34 211 238 / 0.08)",
          }}
        >
          <div
            className="absolute inset-x-0 top-0 h-px"
            style={{ background: "linear-gradient(90deg, transparent, #22D3EE, transparent)" }}
            aria-hidden
          />
          <div className="mb-4 flex items-start justify-between">
            <div>
              <p className="label mb-1" style={{ color: "#22D3EE" }}>Allocation</p>
              <h3 className="font-display text-base font-bold text-white">Sector Breakdown</h3>
              <p className="text-xs text-muted">Spread lowers single-industry risk</p>
            </div>
            <Link href="/portfolio" className="text-sm font-medium" style={{ color: "#22D3EE" }}>
              Holdings →
            </Link>
          </div>
          {sectorData.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-8">
              <div
                className="flex h-12 w-12 items-center justify-center rounded-full"
                style={{ background: "rgb(34 211 238 / 0.1)", border: "1px solid rgb(34 211 238 / 0.2)" }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style={{ color: "#22D3EE" }}>
                  <path d="M12 2v20M2 12h20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-white">No holdings yet</p>
                <p className="mt-1 text-xs text-muted">
                  Buy your first stock from the{" "}
                  <Link href="/market" style={{ color: "#22D3EE" }}>Market page</Link>
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-6">
              <div className="h-44 w-44 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={sectorData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={40}
                      outerRadius={72}
                      stroke="rgb(11 11 27 / 0.9)"
                      strokeWidth={2}
                    >
                      {sectorData.map((_, i) => (
                        <Cell key={i} fill={SECTOR_COLOURS[i % SECTOR_COLOURS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v) => `${Number(v).toFixed(1)}%`}
                      contentStyle={{
                        background: "#0B0B1B",
                        border: "1px solid rgb(124 58 237 / 0.3)",
                        borderRadius: "8px",
                        fontSize: "12px",
                        color: "#F8FAFC",
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
                    <span className="flex-1 text-muted truncate">{s.name}</span>
                    <span className="metric text-xs font-semibold text-white">{pct(s.value, 1)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div
          className="relative overflow-hidden rounded-2xl p-5"
          style={{
            background: "rgb(11 11 27 / 0.85)",
            border: "1px solid rgb(168 85 247 / 0.15)",
            boxShadow: "0 0 24px -8px rgb(168 85 247 / 0.08)",
          }}
        >
          <div
            className="absolute inset-x-0 top-0 h-px"
            style={{ background: "linear-gradient(90deg, transparent, #A855F7, transparent)" }}
            aria-hidden
          />
          <div className="mb-4 flex items-start justify-between">
            <div>
              <p className="label mb-1" style={{ color: "#A855F7" }}>Activity</p>
              <h3 className="font-display text-base font-bold text-white">Recent Trades</h3>
            </div>
            <Link href="/coach" className="text-sm font-medium" style={{ color: "#A855F7" }}>
              See all →
            </Link>
          </div>
          {txns && txns.length > 0 ? (
            <ul className="space-y-1">
              {txns.map((t) => (
                <li
                  key={t.id}
                  className="flex items-center justify-between rounded-xl px-3 py-2.5 transition"
                  style={{ background: "rgb(124 58 237 / 0.04)" }}
                >
                  <span className="flex items-center gap-2.5">
                    <span
                      className="rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                      style={
                        t.side === "buy"
                          ? {
                              background: "rgb(16 217 160 / 0.15)",
                              border: "1px solid rgb(16 217 160 / 0.3)",
                              color: "#10D9A0",
                            }
                          : {
                              background: "rgb(242 87 103 / 0.15)",
                              border: "1px solid rgb(242 87 103 / 0.3)",
                              color: "#F25767",
                            }
                      }
                    >
                      {t.side}
                    </span>
                    <span className="text-sm text-white">
                      {t.quantity} <span className="font-mono text-xs text-muted">{t.symbol}</span>
                    </span>
                  </span>
                  <span className="metric text-sm font-semibold text-white">{rupees(t.price)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 py-8">
              <p className="text-sm text-muted">No trades yet.</p>
              <Link
                href="/market"
                className="rounded-xl px-4 py-2 text-sm font-semibold"
                style={{
                  background: "rgb(168 85 247 / 0.12)",
                  border: "1px solid rgb(168 85 247 / 0.25)",
                  color: "#A855F7",
                }}
              >
                Browse Market →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
