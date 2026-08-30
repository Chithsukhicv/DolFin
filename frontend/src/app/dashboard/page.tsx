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
  "#6366f1",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#0ea5e9",
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

  // If the cached user ID no longer exists in the backend, kick back to /
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

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">
          Hi {user?.display_name || "there"} 👋
        </h1>
        <p className="text-sm text-slate-500">
          Practising as <span className="font-medium capitalize">{user?.persona}</span>{" "}
          · risk: <span className="font-medium capitalize">{user?.risk_appetite}</span>
        </p>
      </header>

      {/* The single most useful thing on this page for a beginner: what to do next. */}
      <LearningPath userId={userId} compact />

      {pf && pf.stale_price_count > 0 && (
        <p
          role="status"
          className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          {pf.stale_price_count === 1
            ? "One holding is priced from cache"
            : `${pf.stale_price_count} holdings are priced from cache`}{" "}
          because the live market feed didn&apos;t respond. Values may be slightly behind.
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Total portfolio value
          </p>
          <p className="mt-1 text-3xl font-semibold">
            {pf ? rupees(pf.total_value) : "—"}
          </p>
          {pf && (
            <p
              className={`mt-1 text-sm ${
                pf.unrealised_pnl >= 0 ? "text-emerald-600" : "text-red-600"
              }`}
            >
              Unrealised P&amp;L: {rupees(pf.unrealised_pnl)}
            </p>
          )}
        </Card>

        <Card>
          <p className="text-xs uppercase tracking-wide text-slate-500">Cash</p>
          <p className="mt-1 text-3xl font-semibold">
            {pf ? rupees(pf.cash) : "—"}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Invested: {pf ? rupees(pf.invested) : "—"}
          </p>
        </Card>

        <Card>
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Investment Readiness
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <p className="text-3xl font-semibold">
              {readiness ? (readiness.is_active ? readiness.score.toFixed(0) : "—") : "—"}
            </p>
            <p className="text-sm text-slate-500">/ 100</p>
          </div>
          {readiness && !readiness.is_active ? (
            <p className="mt-1 text-xs text-slate-500">
              Make your first trade to start tracking
            </p>
          ) : (
            <>
              {/* A score built on two trades is a guess, and presenting it as
                  final would mislead exactly the people we're trying to help. */}
              {readiness?.provisional && (
                <p className="mt-1 text-xs text-amber-700">
                  Provisional —{" "}
                  {readiness.evidence_needed.trades > 0 && (
                    <>{readiness.evidence_needed.trades} more trades</>
                  )}
                  {readiness.evidence_needed.trades > 0 &&
                    readiness.evidence_needed.holdings > 0 &&
                    " and "}
                  {readiness.evidence_needed.holdings > 0 && (
                    <>{readiness.evidence_needed.holdings} more holdings</>
                  )}{" "}
                  for a confident score
                </p>
              )}
              <Link
                href="/readiness"
                className="mt-1 inline-block text-sm text-indigo-600 hover:underline"
              >
                View breakdown →
              </Link>
            </>
          )}
          {readiness?.graduated && (
            <p className="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
              ⭐ Graduated — ready for real money
            </p>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Portfolio value over time"
          subtitle="Every trade and scenario change is recorded here"
        />
        <EquityCurve userId={userId} />
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Sector allocation"
            subtitle="Spread across sectors lowers single-industry risk"
            right={
              <Link
                href="/portfolio"
                className="text-sm text-indigo-600 hover:underline"
              >
                Holdings →
              </Link>
            }
          />
          {sectorData.length === 0 ? (
            <p className="text-sm text-slate-500">
              No holdings yet. Buy your first stock from the{" "}
              <Link href="/market" className="text-indigo-600 hover:underline">
                Market page
              </Link>
              .
            </p>
          ) : (
            <div className="flex items-center gap-6">
              <div className="h-48 w-48">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={sectorData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={45}
                      outerRadius={75}
                      stroke="white"
                      strokeWidth={2}
                    >
                      {sectorData.map((_, i) => (
                        <Cell
                          key={i}
                          fill={SECTOR_COLOURS[i % SECTOR_COLOURS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v) => `${Number(v).toFixed(1)}%`}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="flex-1 space-y-1 text-sm">
                {sectorData.map((s, i) => (
                  <li key={s.name} className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{
                        backgroundColor: SECTOR_COLOURS[i % SECTOR_COLOURS.length],
                      }}
                    />
                    <span className="flex-1">{s.name}</span>
                    <span className="font-medium">{pct(s.value, 1)}</span>
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
              <Link
                href="/coach"
                className="text-sm text-indigo-600 hover:underline"
              >
                See all →
              </Link>
            }
          />
          {txns && txns.length > 0 ? (
            <ul className="divide-y divide-slate-100 text-sm">
              {txns.map((t) => (
                <li
                  key={t.id}
                  className="flex items-center justify-between py-2"
                >
                  <span>
                    <span
                      className={`mr-2 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase ${
                        t.side === "buy"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {t.side}
                    </span>
                    {t.quantity} {t.symbol}
                  </span>
                  <span className="text-slate-600">{rupees(t.price)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No trades yet.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
