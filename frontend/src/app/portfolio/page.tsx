"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import {
  api,
  fetcher,
  type Holding,
  type Portfolio,
  type PreviewResult,
} from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { rupees, pct } from "@/lib/format";
import { Card, CardHeader } from "@/components/Card";
import { InterventionModal } from "@/components/InterventionModal";
import { EmptyState, ErrorState, LoadingCard, StaleBadge } from "@/components/States";
import { Term } from "@/components/Term";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import Link from "next/link";

const SECTOR_COLOURS = [
  "#6C63FF", "#40D9FF", "#00D6A0", "#f59e0b", "#ef4444",
  "#a855f7", "#14b8a6", "#f97316", "#84cc16", "#ec4899",
];

export default function PortfolioPage() {
  const userId = useRequireUser();

  const { data: pf, error: pfError } = useSWR<Portfolio>(
    userId ? `/portfolio/${userId}` : null,
    fetcher,
    { refreshInterval: 10000 },
  );

  const [selling, setSelling] = useState<Holding | null>(null);
  const [qty, setQty] = useState(1);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!userId) return null;

  async function startSell(h: Holding) {
    setSelling(h);
    setQty(1);
    setError(null);
  }

  async function handlePreview() {
    if (!selling || !userId) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<PreviewResult>("/portfolio/preview", {
        user_id: userId,
        symbol: selling.symbol,
        side: "sell",
        quantity: qty,
      });
      setPreview(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const sectorData = pf
    ? Object.entries(pf.sector_allocation_pct).map(([name, value]) => ({
        name,
        value: Math.round(value * 10) / 10,
      }))
    : [];

  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold text-white">Portfolio</h1>

      {pfError && <ErrorState error={pfError} label="Couldn't load your portfolio" />}

      {pf && pf.stale_price_count > 0 && (
        <p role="status" className="rounded-xl border border-warn/30 bg-warn/8 px-4 py-3 text-sm text-warn">
          Some prices below are from cache. Rows are marked — values may be slightly behind.
        </p>
      )}

      {/* Allocation donut + holdings table */}
      {pf && sectorData.length > 0 && (
        <Card>
          <CardHeader
            title="Allocation"
            subtitle="How your portfolio is spread across sectors"
          />
          <div className="flex flex-wrap items-center gap-8">
            <div className="h-52 w-52 shrink-0">
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={sectorData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={52}
                    outerRadius={82}
                    stroke="rgba(255,255,255,0.05)"
                    strokeWidth={2}
                    paddingAngle={3}
                  >
                    {sectorData.map((_, i) => (
                      <Cell key={i} fill={SECTOR_COLOURS[i % SECTOR_COLOURS.length]} />
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
            <ul className="flex-1 space-y-2 text-sm">
              {sectorData.map((s, i) => (
                <li key={s.name} className="flex items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: SECTOR_COLOURS[i % SECTOR_COLOURS.length] }}
                  />
                  <span className="flex-1 text-muted">{s.name}</span>
                  <span className="font-mono text-xs font-semibold text-fg">{pct(s.value, 1)}</span>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Your holdings"
          subtitle={
            pf
              ? `${pf.holdings.length} position${pf.holdings.length !== 1 ? "s" : ""} · market value ${rupees(pf.market_value)}`
              : ""
          }
        />
        {!pf && !pfError ? (
          <LoadingCard lines={3} />
        ) : pf && pf.holdings.length === 0 ? (
          <EmptyState
            title="No holdings yet"
            action={
              <Link
                href="/market"
                className="btn-primary rounded-lg px-4 py-2 text-sm font-medium"
              >
                Browse the market →
              </Link>
            }
          >
            Buy your first practice position and it will appear here with live P&amp;L.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left">
                <tr>
                  <th className="py-2 text-xs font-medium text-subtle">Stock</th>
                  <th className="text-xs font-medium text-subtle">
                    <Term name="sector">Sector</Term>
                  </th>
                  <th className="text-right text-xs font-medium text-subtle">Qty</th>
                  <th className="text-right text-xs font-medium text-subtle">
                    <Term name="avg_cost">Avg cost</Term>
                  </th>
                  <th className="text-right text-xs font-medium text-subtle">Live</th>
                  <th className="text-right text-xs font-medium text-subtle">
                    <Term name="market_value">Value</Term>
                  </th>
                  <th className="text-right text-xs font-medium text-subtle">
                    <Term name="unrealised_pnl">P&amp;L</Term>
                  </th>
                  <th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {pf?.holdings.map((h) => (
                  <tr key={h.symbol} className="row-hover border-t border-hairline">
                    <td className="py-3 pr-3">
                      <p className="font-medium text-fg">{h.name}</p>
                      <p className="text-xs text-subtle">{h.symbol}</p>
                    </td>
                    <td className="text-muted">{h.sector}</td>
                    <td className="text-right font-mono text-fg">{h.quantity}</td>
                    <td className="text-right font-mono text-fg">{rupees(h.avg_cost)}</td>
                    <td className="text-right font-mono text-fg">
                      {rupees(h.live_price)}
                      {h.price_stale && <StaleBadge unavailable={h.price_unavailable} />}
                    </td>
                    <td className="text-right font-mono text-fg">{rupees(h.market_value)}</td>
                    <td className={`text-right font-mono font-medium ${h.unrealised_pnl >= 0 ? "text-pos" : "text-neg"}`}>
                      {rupees(h.unrealised_pnl)}
                      <span className="ml-1 text-xs opacity-70">
                        ({pct(h.unrealised_pnl_pct)})
                      </span>
                    </td>
                    <td className="pl-3 text-right">
                      <button
                        onClick={() => startSell(h)}
                        className="rounded-lg border border-hairline-strong bg-elev-2 px-2.5 py-1 text-xs text-muted transition hover:border-neg/40 hover:bg-neg/10 hover:text-neg"
                      >
                        Sell
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Sell modal — dark theme ── */}
      {selling && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelling(null);
          }}
        >
          <div className="card-raised w-full max-w-md animate-rise rounded-2xl p-6">
            <div className="mb-1 flex items-start justify-between">
              <div>
                <h2 className="font-display text-lg font-bold text-white">
                  Sell {selling.symbol}
                </h2>
                <p className="text-sm text-muted">
                  Holding {selling.quantity} · live{" "}
                  <span className="font-mono text-fg">{rupees(selling.live_price)}</span>
                  {" · "}avg{" "}
                  <span className="font-mono text-fg">{rupees(selling.avg_cost)}</span>
                </p>
              </div>
              <button
                onClick={() => setSelling(null)}
                aria-label="Close"
                className="ml-4 rounded-lg p-1.5 text-subtle transition hover:bg-elev-3 hover:text-fg"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M4 4l8 8M12 4L4 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                </svg>
              </button>
            </div>

            <div className="mt-5">
              <label className="label block">Quantity</label>
              <div className="mt-1.5 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setQty(q => Math.max(1, q - 1))}
                  className="rounded-lg border border-hairline-strong bg-elev-2 px-3 py-2 text-sm text-fg hover:bg-elev-3"
                >−</button>
                <input
                  type="number"
                  min={1}
                  max={selling.quantity}
                  value={qty}
                  onChange={(e) =>
                    setQty(Math.min(selling.quantity, Math.max(1, parseInt(e.target.value || "1", 10))))
                  }
                  className="w-full rounded-lg border border-hairline-strong bg-elev-3 px-3 py-2 text-center text-sm text-fg outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
                />
                <button
                  type="button"
                  onClick={() => setQty(q => Math.min(selling.quantity, q + 1))}
                  className="rounded-lg border border-hairline-strong bg-elev-2 px-3 py-2 text-sm text-fg hover:bg-elev-3"
                >+</button>
              </div>
              <p className="mt-1.5 text-xs text-subtle">
                Proceeds: <span className="font-mono text-fg">{rupees(selling.live_price * qty)}</span>
              </p>
            </div>

            {error && <p role="alert" className="mt-3 text-sm text-neg">{error}</p>}

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setSelling(null)}
                className="btn-ghost rounded-lg px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handlePreview}
                disabled={busy}
                className="btn-primary rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50"
              >
                {busy ? "Checking..." : "Preview sell"}
              </button>
            </div>
          </div>
        </div>
      )}

      {preview && selling && userId && (
        <InterventionModal
          userId={userId}
          preview={preview}
          side="sell"
          symbol={selling.symbol}
          quantity={qty}
          onCancel={() => {
            setPreview(null);
            setSelling(null);
          }}
          onConfirmed={() => {
            setPreview(null);
            setSelling(null);
            mutate(`/portfolio/${userId}`);
          }}
        />
      )}
    </div>
  );
}
