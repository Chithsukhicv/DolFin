"use client";

import { useMemo, useState } from "react";
import useSWR, { mutate } from "swr";
import { api, fetcher, type PreviewResult, type Quote, type Stock } from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { rupees, pct } from "@/lib/format";
import { Card, CardHeader } from "@/components/Card";
import { InterventionModal } from "@/components/InterventionModal";
import { PriceChart } from "@/components/PriceChart";
import { ErrorState, StaleBadge } from "@/components/States";
import Link from "next/link";

const RISK_STYLES: Record<string, string> = {
  low:    "bg-pos/12 text-pos border-pos/25",
  medium: "bg-warn/12 text-warn border-warn/25",
  high:   "bg-neg/12 text-neg border-neg/25",
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
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      {/* ── Stock list ── */}
      <div className="space-y-4">
        <h1 className="font-display text-2xl font-bold text-white">Market</h1>

        {stocksError && <ErrorState error={stocksError} label="Couldn't load the catalogue" />}

        {/* Search + filter bar */}
        <div className="flex flex-wrap gap-2">
          <div className="flex-1">
            <label htmlFor="stock-search" className="sr-only">Search stocks</label>
            <div className="relative">
              <svg
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-subtle"
                width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round"
              >
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
              <input
                id="stock-search"
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name or symbol…"
                className="w-full rounded-xl border border-hairline-strong bg-elev-2 py-2.5 pl-9 pr-3 text-sm text-fg placeholder:text-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
              />
            </div>
          </div>
          <div>
            <label htmlFor="sector-filter" className="sr-only">Filter by sector</label>
            <select
              id="sector-filter"
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              className="rounded-xl border border-hairline-strong bg-elev-2 px-3 py-2.5 text-sm text-fg"
            >
              <option value="">All sectors</option>
              {sectors?.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {/* Results count */}
        <p aria-live="polite" className="sr-only">{filtered.length} instruments match</p>

        <Card className="overflow-hidden !p-0">
          <ul className="divide-y divide-hairline">
            {filtered.map((s) => {
              const isFund = s.sector === "Index Fund";
              const isSelected = selected?.symbol === s.symbol;
              const riskStyle = RISK_STYLES[s.risk_level?.toLowerCase() ?? ""] ?? RISK_STYLES.medium;
              return (
                <li key={s.symbol}>
                  <button
                    type="button"
                    onClick={() => setSelected(s)}
                    aria-pressed={isSelected}
                    className={`flex w-full items-center justify-between gap-3 px-5 py-3 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
                      isSelected
                        ? "bg-brand/10 border-l-2 border-l-brand"
                        : "hover:bg-elev-2"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-semibold text-fg">{s.name}</p>
                        {isFund && (
                          <span className="rounded bg-blue-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300">
                            fund
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 flex items-center gap-2 text-xs text-subtle">
                        <span className="font-mono font-medium text-muted">{s.symbol}</span>
                        <span>·</span>
                        <span>{s.sector}</span>
                        {!isFund && (
                          <>
                            <span>·</span>
                            <span className={`rounded-full border px-1.5 py-px text-[10px] font-semibold uppercase ${riskStyle}`}>
                              {s.risk_level}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <span aria-hidden="true" className={`shrink-0 text-xs transition ${isSelected ? "text-brand" : "text-subtle"}`}>
                      →
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {filtered.length === 0 && !stocksError && (
            <p className="py-8 text-center text-sm text-subtle">
              No matches. Try clearing the sector filter.
            </p>
          )}
        </Card>

        <p className="text-xs text-subtle">
          Index funds hold dozens of companies at once — one purchase is already diversified.{" "}
          <Link href="/learn/index_funds" className="text-brand hover:underline">
            How index funds work →
          </Link>
        </p>
      </div>

      {/* ── Buy panel ── */}
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
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-elev-3">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="text-subtle">
                  <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>
                </svg>
              </div>
              <p className="text-sm font-medium text-fg">Select a stock</p>
              <p className="mt-1 text-xs text-subtle">
                Pick one from the list to see its price chart and place a practice trade.
              </p>
            </div>
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
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const riskStyle = RISK_STYLES[stock.risk_level?.toLowerCase() ?? ""] ?? RISK_STYLES.medium;
  const dayUp = (quote?.day_change_pct ?? 0) >= 0;

  return (
    <Card className="sticky top-24">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-lg font-bold text-white truncate">{stock.name}</h2>
          <div className="mt-0.5 flex items-center gap-2 text-xs">
            <span className="font-mono text-muted">{stock.symbol}</span>
            <span className="text-subtle">·</span>
            <span className="text-muted">{stock.sector}</span>
          </div>
        </div>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${riskStyle}`}>
          {stock.risk_level}
        </span>
      </div>

      {/* Price display */}
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
            <p className={`mt-1 text-sm font-medium ${dayUp ? "text-pos" : "text-neg"}`}>
              <span aria-hidden>{dayUp ? "▲" : "▼"}</span>{" "}
              {pct(quote.day_change_pct)}
              {quote.day_change !== null && quote.day_change !== undefined && (
                <span className="ml-1 opacity-70">({rupees(quote.day_change)})</span>
              )}
              <span className="sr-only">{dayUp ? " up" : " down"} today</span>
            </p>
          )}
          {quote.scenario && (
            <p className="mt-1 text-xs text-warn">
              Simulated {quote.scenario.kind}: ×{quote.scenario_multiplier?.toFixed(3)} applied.
            </p>
          )}
        </div>
      ) : (
        <div className="mb-4 h-12 rounded-lg bg-elev-2 animate-pulse" />
      )}

      {/* Price chart */}
      <div className="border-t border-hairline pt-3">
        <PriceChart symbol={stock.symbol} />
      </div>

      {/* Trade form */}
      <div className="mt-4 space-y-3">
        <div>
          <label htmlFor="trade-qty" className="label block mb-1.5">Quantity</label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setQty(q => Math.max(1, q - 1))}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline-strong bg-elev-2 text-lg text-fg hover:bg-elev-3"
            >−</button>
            <input
              id="trade-qty"
              type="number"
              min={1}
              step={1}
              value={qty}
              onChange={(e) => setQty(Math.max(1, parseInt(e.target.value || "1", 10)))}
              className="w-full rounded-lg border border-hairline-strong bg-elev-3 px-3 py-2 text-center text-sm text-fg outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
            />
            <button
              type="button"
              onClick={() => setQty(q => q + 1)}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline-strong bg-elev-2 text-lg text-fg hover:bg-elev-3"
            >+</button>
          </div>
          {quote && (
            <p className="mt-1.5 text-xs text-subtle">
              Estimated cost:{" "}
              <span className="font-mono text-fg">{rupees(quote.price * qty)}</span>{" "}
              <span className="text-faint">(plus 0.05% fee)</span>
            </p>
          )}
        </div>

        {error && <p role="alert" className="text-sm text-neg">{error}</p>}

        <button
          onClick={handleBuy}
          disabled={busy || !quote}
          className="btn-primary w-full rounded-xl px-4 py-3 font-semibold disabled:opacity-50"
        >
          {busy ? "Checking…" : "Preview practice buy"}
        </button>

        <p className="text-center text-[10px] text-faint">
          This is a simulated trade — no real money is involved.
        </p>
      </div>

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
