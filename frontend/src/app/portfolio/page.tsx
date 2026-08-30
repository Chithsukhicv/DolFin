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
import Link from "next/link";

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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Portfolio</h1>

      {pfError && <ErrorState error={pfError} label="Couldn't load your portfolio" />}

      {pf && pf.stale_price_count > 0 && (
        <p
          role="status"
          className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          Some prices below are from cache because the live feed didn&apos;t respond. Rows are
          marked, and values may be slightly behind.
        </p>
      )}

      <Card>
        <CardHeader
          title="Your holdings"
          subtitle={
            pf
              ? `${pf.holdings.length} positions · market value ${rupees(pf.market_value)}`
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
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
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
              <thead className="text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2">Stock</th>
                  <th>
                    <Term name="sector">Sector</Term>
                  </th>
                  <th className="text-right">Qty</th>
                  <th className="text-right">
                    <Term name="avg_cost">Avg cost</Term>
                  </th>
                  <th className="text-right">Live</th>
                  <th className="text-right">
                    <Term name="market_value">Value</Term>
                  </th>
                  <th className="text-right">
                    <Term name="unrealised_pnl">P&amp;L</Term>
                  </th>
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {pf?.holdings.map((h) => (
                  <tr key={h.symbol} className="border-t border-slate-100">
                    <td className="py-2">
                      <p className="font-medium">{h.name}</p>
                      <p className="text-xs text-slate-500">{h.symbol}</p>
                    </td>
                    <td className="text-slate-600">{h.sector}</td>
                    <td className="text-right">{h.quantity}</td>
                    <td className="text-right">{rupees(h.avg_cost)}</td>
                    <td className="text-right">
                      {rupees(h.live_price)}
                      {h.price_stale && <StaleBadge unavailable={h.price_unavailable} />}
                    </td>
                    <td className="text-right">{rupees(h.market_value)}</td>
                    <td
                      className={`text-right ${
                        h.unrealised_pnl >= 0 ? "text-emerald-600" : "text-red-600"
                      }`}
                    >
                      {rupees(h.unrealised_pnl)}
                      <span className="ml-1 text-xs">
                        ({pct(h.unrealised_pnl_pct)})
                      </span>
                    </td>
                    <td className="text-right">
                      <button
                        onClick={() => startSell(h)}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
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

      {/* Sell modal */}
      {selling && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelling(null);
          }}
        >
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="mb-1 text-lg font-semibold">Sell {selling.symbol}</h2>
            <p className="text-sm text-slate-500">
              You hold {selling.quantity} · live {rupees(selling.live_price)} · avg{" "}
              {rupees(selling.avg_cost)}
            </p>

            <div className="mt-4">
              <label className="text-xs font-medium text-slate-600">Quantity</label>
              <input
                type="number"
                min={1}
                max={selling.quantity}
                value={qty}
                onChange={(e) =>
                  setQty(
                    Math.min(
                      selling.quantity,
                      Math.max(1, parseInt(e.target.value || "1", 10)),
                    ),
                  )
                }
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <p className="mt-1 text-xs text-slate-500">
                Proceeds: {rupees(selling.live_price * qty)}
              </p>
            </div>

            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setSelling(null)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handlePreview}
                disabled={busy}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
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
