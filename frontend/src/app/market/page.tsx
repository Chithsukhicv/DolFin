"use client";

import { useMemo, useState } from "react";
import useSWR, { mutate } from "swr";
import {
  api,
  fetcher,
  type PreviewResult,
  type Quote,
  type Stock,
} from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { rupees, pct } from "@/lib/format";
import { Card, CardHeader } from "@/components/Card";
import { InterventionModal } from "@/components/InterventionModal";
import { PriceChart } from "@/components/PriceChart";
import { ErrorState, StaleBadge } from "@/components/States";
import Link from "next/link";

export default function MarketPage() {
  const userId = useRequireUser();

  const { data: stocks, error: stocksError } = useSWR<Stock[]>("/catalog/stocks", fetcher);
  const { data: sectors } = useSWR<string[]>("/catalog/sectors", fetcher);

  const [search, setSearch] = useState("");
  const [sector, setSector] = useState<string>("");
  const [selected, setSelected] = useState<Stock | null>(null);

  const filtered = useMemo(() => {
    if (!stocks) return [];
    return stocks.filter((s) => {
      if (sector && s.sector !== sector) return false;
      if (search) {
        const q = search.toUpperCase();
        if (!s.symbol.includes(q) && !s.name.toUpperCase().includes(q)) return false;
      }
      return true;
    });
  }, [stocks, sector, search]);

  if (!userId) return null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Market</h1>

        {stocksError && <ErrorState error={stocksError} label="Couldn't load the catalogue" />}

        <Card>
          <div className="mb-4 flex flex-wrap gap-2">
            <div className="flex-1">
              <label htmlFor="stock-search" className="sr-only">
                Search stocks by name or symbol
              </label>
              <input
                id="stock-search"
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name or symbol"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-indigo-500 focus:ring-2"
              />
            </div>
            <div>
              <label htmlFor="sector-filter" className="sr-only">
                Filter by sector
              </label>
              <select
                id="sector-filter"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">All sectors</option>
                {sectors?.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <p aria-live="polite" className="sr-only">
            {filtered.length} instruments match
          </p>

          <ul className="divide-y divide-slate-100">
            {filtered.map((s) => {
              const isFund = s.sector === "Index Fund";
              return (
                <li key={s.symbol}>
                  {/* A button rather than a clickable <li> so the list is
                      reachable by keyboard. */}
                  <button
                    type="button"
                    onClick={() => setSelected(s)}
                    aria-pressed={selected?.symbol === s.symbol}
                    className={`flex w-full items-center justify-between gap-3 py-2 text-left transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                      selected?.symbol === s.symbol ? "bg-indigo-50/60" : ""
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {s.name}
                        {isFund && (
                          <span className="ml-2 rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sky-700">
                            fund
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-slate-500">
                        {s.symbol} · {s.sector}
                        {!isFund && ` · ${s.market_cap_band}-cap`} · {s.risk_level} risk
                      </p>
                    </div>
                    <span aria-hidden="true" className="text-xs text-indigo-600">
                      View →
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {filtered.length === 0 && !stocksError && (
            <p className="py-6 text-center text-sm text-slate-500">
              No matches. Try clearing the sector filter.
            </p>
          )}
        </Card>

        <p className="text-xs text-slate-500">
          Index funds hold dozens of companies at once, so one purchase is already diversified.{" "}
          <Link href="/learn/index_funds" className="text-indigo-600 underline">
            How index funds work →
          </Link>
        </p>
      </div>

      <div>
        {selected ? (
          <BuyPanel
            userId={userId}
            stock={selected}
            onTradeDone={() => {
              mutate(`/portfolio/${userId}`);
              mutate(`/users/${userId}`);
            }}
          />
        ) : (
          <Card>
            <p className="text-sm text-slate-500">
              Pick a stock from the list to see details and place a practice trade.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}

function BuyPanel({
  userId,
  stock,
  onTradeDone,
}: {
  userId: string;
  stock: Stock;
  onTradeDone: () => void;
}) {
  const { data: quote, error: quoteError } = useSWR<Quote>(
    `/market/quote/${encodeURIComponent(stock.symbol)}`,
    fetcher,
    { refreshInterval: 30000 },
  );

  const [qty, setQty] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);

  async function handleBuy() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<PreviewResult>("/portfolio/preview", {
        user_id: userId,
        symbol: stock.symbol,
        side: "buy",
        quantity: qty,
      });
      // Always show the modal so the user sees the coach explanation,
      // even when nothing fired.
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="sticky top-24">
      <CardHeader title={stock.name} subtitle={`${stock.symbol} · ${stock.sector}`} />

      {quoteError ? (
        <ErrorState error={quoteError} label="Couldn't fetch this price" />
      ) : quote ? (
        <>
          <p className="text-3xl font-semibold">
            {rupees(quote.price)}
            {quote.stale && <StaleBadge />}
          </p>
          {quote.day_change_pct !== null && quote.day_change_pct !== undefined && (
            <p
              className={`mt-1 text-sm ${
                quote.day_change_pct >= 0 ? "text-emerald-600" : "text-red-600"
              }`}
            >
              <span aria-hidden="true">{quote.day_change_pct >= 0 ? "▲" : "▼"}</span>{" "}
              {pct(quote.day_change_pct)}
              {quote.day_change !== null &&
                quote.day_change !== undefined &&
                ` (${rupees(quote.day_change)})`}
              <span className="sr-only">
                {quote.day_change_pct >= 0 ? " up" : " down"} today
              </span>
            </p>
          )}
          {quote.scenario && (
            <p className="mt-1 text-xs text-amber-700">
              Simulated {quote.scenario.kind}: ×{quote.scenario_multiplier?.toFixed(3)}{" "}
              adjustment applied to your prices.
            </p>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-500">Loading price…</p>
      )}

      {/* Real history, so the learner can see this company's actual volatility
          before committing simulated money to it. */}
      <div className="mt-4 border-t border-slate-100 pt-3">
        <PriceChart symbol={stock.symbol} />
      </div>

      <div className="mt-4 space-y-2">
        <label htmlFor="trade-qty" className="block text-xs font-medium text-slate-600">
          Quantity
        </label>
        <input
          id="trade-qty"
          type="number"
          min={1}
          step={1}
          value={qty}
          onChange={(e) => setQty(Math.max(1, parseInt(e.target.value || "1", 10)))}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        {quote && (
          <p className="text-xs text-slate-500">
            Estimated cost: {rupees(quote.price * qty)}{" "}
            <span className="text-slate-400">(plus 0.05% fee)</span>
          </p>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {error}
        </p>
      )}

      <button
        onClick={handleBuy}
        disabled={busy || !quote}
        className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {busy ? "Checking..." : "Preview buy"}
      </button>

      {preview && (
        <InterventionModal
          userId={userId}
          preview={preview}
          side="buy"
          symbol={stock.symbol}
          quantity={qty}
          onCancel={() => setPreview(null)}
          onConfirmed={() => {
            setPreview(null);
            onTradeDone();
          }}
        />
      )}
    </Card>
  );
}
