"use client";

import { useMemo, useState } from "react";
import useSWR, { mutate } from "swr";
import { api, fetcher, type PreviewResult, type Quote, type Stock } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { rupees, pct } from "@/lib/format";
import { InterventionModal } from "@/components/InterventionModal";
import { PriceChart } from "@/components/PriceChart";
import { ErrorState, StaleBadge } from "@/components/States";
import Link from "next/link";

const RISK_COLOUR: Record<string, string> = {
  low: "#10D9A0",
  medium: "#F5A623",
  high: "#F25767",
};

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
    <div className="space-y-6">
      {/* Header */}
      <header className="animate-rise">
        <p className="label mb-1" style={{ color: "#22D3EE" }}>Terminal</p>
        <h1 className="font-display text-2xl font-bold text-white">Market</h1>
        <p className="mt-1 text-sm text-muted">
          Live NSE prices · Practice money only
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        {/* Stock list panel */}
        <div
          className="relative overflow-hidden rounded-2xl"
          style={{
            background: "rgb(11 11 27 / 0.9)",
            border: "1px solid rgb(34 211 238 / 0.2)",
            boxShadow: "0 0 24px -8px rgb(34 211 238 / 0.1)",
          }}
        >
          <div
            className="absolute inset-x-0 top-0 h-px"
            style={{ background: "linear-gradient(90deg, transparent, #22D3EE, transparent)" }}
            aria-hidden
          />

          {/* Filters */}
          <div className="p-4 flex flex-wrap gap-3" style={{ borderBottom: "1px solid rgb(34 211 238 / 0.1)" }}>
            <div className="flex-1 min-w-[160px]">
              <label htmlFor="stock-search" className="sr-only">Search stocks</label>
              <div className="relative">
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2"
                  width="14" height="14" viewBox="0 0 24 24" fill="none"
                  style={{ color: "#6b6b85" }}
                  aria-hidden
                >
                  <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
                  <path d="m21 21-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
                <input
                  id="stock-search"
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search name or symbol…"
                  className="w-full rounded-xl pl-9 pr-3 py-2 text-sm text-white placeholder:text-muted outline-none"
                  style={{
                    background: "rgb(124 58 237 / 0.06)",
                    border: "1px solid rgb(124 58 237 / 0.2)",
                  }}
                />
              </div>
            </div>
            <div>
              <label htmlFor="sector-filter" className="sr-only">Filter by sector</label>
              <select
                id="sector-filter"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="rounded-xl px-3 py-2 text-sm text-white outline-none"
                style={{
                  background: "rgb(124 58 237 / 0.06)",
                  border: "1px solid rgb(124 58 237 / 0.2)",
                  color: sector ? "#A855F7" : "#A1A1B5",
                }}
              >
                <option value="">All sectors</option>
                {sectors?.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {stocksError && <ErrorState error={stocksError} label="Couldn't load the catalogue" />}

          <p aria-live="polite" className="sr-only">{filtered.length} instruments match</p>

          <ul>
            {filtered.map((s) => {
              const isFund = s.sector === "Index Fund";
              const isSelected = selected?.symbol === s.symbol;
              const riskCol = RISK_COLOUR[s.risk_level] ?? "#A1A1B5";
              return (
                <li key={s.symbol}>
                  <button
                    type="button"
                    onClick={() => setSelected(s)}
                    aria-pressed={isSelected}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition focus:outline-none"
                    style={{
                      background: isSelected ? "rgb(34 211 238 / 0.07)" : undefined,
                      borderBottom: "1px solid rgb(124 58 237 / 0.07)",
                      borderLeft: isSelected ? "2px solid #22D3EE" : "2px solid transparent",
                    }}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-semibold text-white">{s.name}</p>
                        {isFund && (
                          <span
                            className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                            style={{
                              background: "rgb(79 124 255 / 0.15)",
                              border: "1px solid rgb(79 124 255 / 0.3)",
                              color: "#4F7CFF",
                            }}
                          >
                            FUND
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted">
                        <span className="font-mono">{s.symbol}</span> · {s.sector}
                        {!isFund && ` · ${s.market_cap_band}-cap`}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
                        style={{
                          background: `${riskCol}15`,
                          color: riskCol,
                          border: `1px solid ${riskCol}30`,
                        }}
                      >
                        {s.risk_level}
                      </span>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ color: isSelected ? "#22D3EE" : "#44445a" }}>
                        <path d="M9 18l6-6-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 && !stocksError && (
              <li className="py-8 text-center text-sm text-muted">
                No matches. Try clearing the sector filter.
              </li>
            )}
          </ul>
        </div>

        {/* Buy panel */}
        <div className="lg:sticky lg:top-24">
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
            <div
              className="flex flex-col items-center justify-center gap-4 rounded-2xl p-8"
              style={{
                background: "rgb(11 11 27 / 0.85)",
                border: "1px solid rgb(124 58 237 / 0.15)",
              }}
            >
              <div
                className="flex h-14 w-14 items-center justify-center rounded-full"
                style={{ background: "rgb(124 58 237 / 0.1)", border: "1px solid rgb(124 58 237 / 0.2)" }}
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" style={{ color: "#7C3AED" }}>
                  <path d="M3 3h18M3 12h18M3 21h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
              <p className="text-center text-sm text-muted">
                Select a stock from the list to view its price and place a practice trade.
              </p>
            </div>
          )}
        </div>
      </div>

      <p className="text-xs text-muted">
        Index funds hold dozens of companies at once, so one purchase is already diversified.{" "}
        <Link href="/learn/index_funds" style={{ color: "#22D3EE" }}>
          How index funds work →
        </Link>
      </p>
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
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="relative overflow-hidden rounded-2xl p-5"
      style={{
        background: "rgb(11 11 27 / 0.9)",
        border: "1px solid rgb(168 85 247 / 0.2)",
        boxShadow: "0 0 32px -8px rgb(168 85 247 / 0.15)",
      }}
    >
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: "linear-gradient(90deg, transparent, #A855F7, #22D3EE, transparent)" }}
        aria-hidden
      />

      {/* Stock info */}
      <div className="mb-4">
        <p className="font-display text-base font-bold text-white">{stock.name}</p>
        <p className="text-xs text-muted">{stock.symbol} · {stock.sector}</p>
      </div>

      {quoteError ? (
        <ErrorState error={quoteError} label="Couldn't fetch this price" />
      ) : quote ? (
        <div className="mb-4">
          <div className="flex items-baseline gap-3">
            <span className="metric text-3xl font-bold text-white">
              {rupees(quote.price)}
            </span>
            {quote.stale && <StaleBadge />}
          </div>
          {quote.day_change_pct !== null && quote.day_change_pct !== undefined && (
            <p
              className="mt-1 text-sm font-semibold"
              style={{ color: quote.day_change_pct >= 0 ? "#10D9A0" : "#F25767" }}
            >
              <span aria-hidden>{quote.day_change_pct >= 0 ? "▲" : "▼"}</span>{" "}
              {pct(quote.day_change_pct)}
              {quote.day_change !== null && quote.day_change !== undefined &&
                ` (${rupees(quote.day_change)})`}
            </p>
          )}
          {quote.scenario && (
            <p
              className="mt-1 rounded-lg px-3 py-1.5 text-xs"
              style={{
                background: "rgb(245 166 35 / 0.08)",
                border: "1px solid rgb(245 166 35 / 0.2)",
                color: "#F5A623",
              }}
            >
              Simulated {quote.scenario.kind}: ×{quote.scenario_multiplier?.toFixed(3)} applied
            </p>
          )}
        </div>
      ) : (
        <p className="mb-4 text-sm text-muted">Loading price…</p>
      )}

      {/* Price chart */}
      <div
        className="mb-4 overflow-hidden rounded-xl p-3"
        style={{ background: "rgb(124 58 237 / 0.04)", border: "1px solid rgb(124 58 237 / 0.12)" }}
      >
        <PriceChart symbol={stock.symbol} />
      </div>

      {/* Quantity input */}
      <div className="mb-4">
        <label htmlFor="trade-qty" className="label mb-1.5 block">Quantity</label>
        <input
          id="trade-qty"
          type="number"
          min={1}
          step={1}
          value={qty}
          onChange={(e) => setQty(Math.max(1, parseInt(e.target.value || "1", 10)))}
          className="w-full rounded-xl px-3.5 py-2.5 text-sm text-white outline-none"
          style={{
            background: "rgb(124 58 237 / 0.06)",
            border: "1px solid rgb(124 58 237 / 0.25)",
          }}
        />
        {quote && (
          <p className="mt-1.5 text-xs text-muted">
            Estimated cost:{" "}
            <span className="metric font-semibold text-white">{rupees(quote.price * qty)}</span>
            {" "}<span style={{ color: "#44445a" }}>(+ 0.05% fee)</span>
          </p>
        )}
      </div>

      {error && (
        <p
          role="alert"
          className="mb-3 rounded-xl px-3 py-2 text-sm"
          style={{
            background: "rgb(242 87 103 / 0.08)",
            border: "1px solid rgb(242 87 103 / 0.25)",
            color: "#F25767",
          }}
        >
          {error}
        </p>
      )}

      <button
        onClick={handleBuy}
        disabled={busy || !quote}
        className="w-full rounded-xl px-4 py-3 font-bold text-sm transition disabled:opacity-50"
        style={{
          background: "linear-gradient(135deg, #10D9A0 0%, #059669 100%)",
          color: "#fff",
          boxShadow: "0 4px 20px -4px rgb(16 217 160 / 0.4)",
        }}
      >
        {busy ? "Checking…" : "Preview Buy"}
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
    </div>
  );
}
