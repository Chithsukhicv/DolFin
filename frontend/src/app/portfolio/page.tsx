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
import { InterventionModal } from "@/components/InterventionModal";
import { EmptyState, ErrorState, LoadingCard, StaleBadge } from "@/components/States";
import { Term } from "@/components/Term";
import Link from "next/link";

const SECTOR_COLOURS: Record<string, string> = {
  Technology: "#A855F7",
  Finance: "#22D3EE",
  Healthcare: "#10D9A0",
  Consumer: "#4F7CFF",
  Energy: "#F5A623",
  Materials: "#F25767",
};
function sectorColour(s: string) {
  return SECTOR_COLOURS[s] ?? "#A1A1B5";
}

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
    setPreview(null);
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

  const totalValue = pf?.market_value ?? 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <header className="animate-rise">
        <p className="label mb-1" style={{ color: "#22D3EE" }}>Holdings</p>
        <h1 className="font-display text-2xl font-bold text-white">Portfolio</h1>
        {pf && (
          <p className="mt-1 text-sm text-muted">
            {pf.holdings.length} positions ·{" "}
            <span className="metric font-semibold text-white">{rupees(pf.market_value)}</span>
            {" "}market value
          </p>
        )}
      </header>

      {pfError && <ErrorState error={pfError} label="Couldn't load your portfolio" />}

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
          Some prices below are from cache — rows are marked, values may be slightly behind.
        </div>
      )}

      {/* Summary metrics row */}
      {pf && (
        <div className="stagger grid gap-4 sm:grid-cols-3">
          {[
            { label: "Market Value", value: rupees(pf.market_value), tone: "#22D3EE" },
            { label: "Cash Available", value: rupees(pf.cash), tone: "#A855F7" },
            {
              label: "Unrealised P&L",
              value: rupees(pf.unrealised_pnl),
              tone: pf.unrealised_pnl >= 0 ? "#10D9A0" : "#F25767",
            },
          ].map((m) => (
            <div
              key={m.label}
              className="relative overflow-hidden rounded-2xl p-4"
              style={{
                background: "rgb(11 11 27 / 0.85)",
                border: `1px solid ${m.tone}28`,
                boxShadow: `0 0 20px -8px ${m.tone}40`,
              }}
            >
              <div
                className="absolute inset-x-0 top-0 h-px"
                style={{ background: `linear-gradient(90deg, transparent, ${m.tone}, transparent)` }}
                aria-hidden
              />
              <p className="label" style={{ color: m.tone }}>{m.label}</p>
              <p className="metric mt-2 text-xl font-bold text-white">{m.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Holdings table */}
      <div
        className="relative overflow-hidden rounded-2xl"
        style={{
          background: "rgb(11 11 27 / 0.85)",
          border: "1px solid rgb(124 58 237 / 0.2)",
          boxShadow: "0 0 24px -8px rgb(124 58 237 / 0.1)",
        }}
      >
        <div
          className="absolute inset-x-0 top-0 h-px"
          style={{ background: "linear-gradient(90deg, transparent, #7C3AED 30%, #22D3EE 70%, transparent)" }}
          aria-hidden
        />
        <div className="p-5">
          <h3 className="font-display text-base font-bold text-white">Your Holdings</h3>
        </div>

        {!pf && !pfError ? (
          <div className="p-5 pt-0">
            <LoadingCard lines={3} />
          </div>
        ) : pf && pf.holdings.length === 0 ? (
          <div className="p-5 pt-0">
            <EmptyState
              title="No holdings yet"
              action={
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
              }
            >
              Buy your first practice position and it will appear here with live P&amp;L.
            </EmptyState>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-left text-xs"
                  style={{ borderBottom: "1px solid rgb(124 58 237 / 0.15)" }}
                >
                  {["Stock", "Sector", "Qty", "Avg Cost", "Live", "Value", "P&L", ""].map(
                    (h) => (
                      <th
                        key={h}
                        className={`px-4 py-3 font-medium ${h === "Qty" || h === "Avg Cost" || h === "Live" || h === "Value" || h === "P&L" ? "text-right" : ""}`}
                        style={{ color: "#6b6b85" }}
                      >
                        {h === "P&L" ? <Term name="unrealised_pnl">P&amp;L</Term> : h === "Avg Cost" ? <Term name="avg_cost">{h}</Term> : h === "Value" ? <Term name="market_value">{h}</Term> : h === "Sector" ? <Term name="sector">{h}</Term> : h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {pf?.holdings.map((h) => {
                  const weight = totalValue > 0 ? (h.market_value / totalValue) * 100 : 0;
                  return (
                    <tr
                      key={h.symbol}
                      className="transition"
                      style={{ borderBottom: "1px solid rgb(124 58 237 / 0.08)" }}
                    >
                      <td className="px-4 py-3">
                        <p className="font-semibold text-white">{h.name}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <p className="font-mono text-[11px] text-muted">{h.symbol}</p>
                          {/* weight bar */}
                          <div className="h-1 w-16 overflow-hidden rounded-full" style={{ background: "rgb(124 58 237 / 0.15)" }}>
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${Math.min(100, weight)}%`,
                                background: `linear-gradient(90deg, #7C3AED, #22D3EE)`,
                              }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="rounded-md px-2 py-0.5 text-[10px] font-medium"
                          style={{
                            background: `${sectorColour(h.sector)}18`,
                            color: sectorColour(h.sector),
                            border: `1px solid ${sectorColour(h.sector)}30`,
                          }}
                        >
                          {h.sector}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right metric text-sm text-white">{h.quantity}</td>
                      <td className="px-4 py-3 text-right metric text-sm text-muted">{rupees(h.avg_cost)}</td>
                      <td className="px-4 py-3 text-right">
                        <span className="metric text-sm text-white">{rupees(h.live_price)}</span>
                        {h.price_stale && <StaleBadge unavailable={h.price_unavailable} />}
                      </td>
                      <td className="px-4 py-3 text-right metric text-sm text-white">{rupees(h.market_value)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex flex-col items-end gap-0.5">
                          <span
                            className="metric text-sm font-semibold"
                            style={{ color: h.unrealised_pnl >= 0 ? "#10D9A0" : "#F25767" }}
                          >
                            {rupees(h.unrealised_pnl)}
                          </span>
                          <span
                            className="text-[10px]"
                            style={{ color: h.unrealised_pnl >= 0 ? "#10D9A0" : "#F25767" }}
                          >
                            {pct(h.unrealised_pnl_pct)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => startSell(h)}
                          className="rounded-xl px-3 py-1.5 text-xs font-semibold transition"
                          style={{
                            background: "rgb(242 87 103 / 0.1)",
                            border: "1px solid rgb(242 87 103 / 0.25)",
                            color: "#F25767",
                          }}
                        >
                          Sell
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Sell modal */}
      {selling && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center p-4"
          style={{ background: "rgb(5 5 16 / 0.85)", backdropFilter: "blur(8px)" }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelling(null);
          }}
        >
          <div
            className="relative w-full max-w-md overflow-hidden rounded-2xl p-6"
            style={{
              background: "#0B0B1B",
              border: "1px solid rgb(242 87 103 / 0.3)",
              boxShadow: "0 24px 64px -12px rgb(242 87 103 / 0.2)",
            }}
          >
            <div
              className="absolute inset-x-0 top-0 h-px"
              style={{ background: "linear-gradient(90deg, transparent, #F25767, transparent)" }}
              aria-hidden
            />
            <h2 className="font-display text-lg font-bold text-white mb-1">
              Sell <span style={{ color: "#F25767" }}>{selling.symbol}</span>
            </h2>
            <p className="text-sm text-muted mb-4">
              You hold {selling.quantity} · live {rupees(selling.live_price)} · avg{" "}
              {rupees(selling.avg_cost)}
            </p>

            <div className="mb-4">
              <label className="label mb-1.5 block">Quantity</label>
              <input
                type="number"
                min={1}
                max={selling.quantity}
                value={qty}
                onChange={(e) =>
                  setQty(Math.min(selling.quantity, Math.max(1, parseInt(e.target.value || "1", 10))))
                }
                className="w-full rounded-xl px-3.5 py-2.5 text-sm text-white"
                style={{
                  background: "rgb(124 58 237 / 0.06)",
                  border: "1px solid rgb(124 58 237 / 0.3)",
                  outline: "none",
                }}
              />
              <p className="mt-1.5 text-xs text-muted">
                Proceeds: <span className="text-white font-semibold">{rupees(selling.live_price * qty)}</span>
              </p>
            </div>

            {error && (
              <p className="mb-3 rounded-lg px-3 py-2 text-sm" style={{ background: "rgb(242 87 103 / 0.1)", color: "#F25767", border: "1px solid rgb(242 87 103 / 0.25)" }}>
                {error}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setSelling(null)}
                className="rounded-xl px-4 py-2 text-sm font-semibold transition"
                style={{ background: "rgb(255 255 255 / 0.04)", border: "1px solid rgb(255 255 255 / 0.1)", color: "#A1A1B5" }}
              >
                Cancel
              </button>
              <button
                onClick={handlePreview}
                disabled={busy}
                className="rounded-xl px-4 py-2 text-sm font-semibold transition disabled:opacity-50"
                style={{
                  background: "linear-gradient(135deg, #be123c, #f25767)",
                  color: "#fff",
                  boxShadow: "0 4px 16px -4px rgb(242 87 103 / 0.4)",
                }}
              >
                {busy ? "Checking…" : "Preview sell"}
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
