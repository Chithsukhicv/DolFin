"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetcher, type PriceBar } from "@/lib/api";
import { rupees } from "@/lib/format";

/**
 * Real price history for a symbol.
 *
 * The backend has exposed OHLCV data all along but nothing rendered it, so a
 * learner could read that "markets fall about 10% roughly once a year" without
 * ever seeing what that looks like. Real history makes the volatility concrete
 * before they put simulated money behind it.
 */

const RANGES = [
  { label: "1M", period: "1mo", interval: "1d" },
  { label: "6M", period: "6mo", interval: "1d" },
  { label: "1Y", period: "1y", interval: "1d" },
  { label: "5Y", period: "5y", interval: "1wk" },
] as const;

export function PriceChart({ symbol }: { symbol: string }) {
  const [range, setRange] = useState<(typeof RANGES)[number]>(RANGES[1]);

  const { data, error, isLoading } = useSWR<PriceBar[]>(
    symbol
      ? `/market/history/${encodeURIComponent(symbol)}?period=${range.period}&interval=${range.interval}`
      : null,
    fetcher,
  );

  const bars = data ?? [];
  const first = bars[0]?.close;
  const last = bars[bars.length - 1]?.close;
  const changePct = first && last ? ((last - first) / first) * 100 : 0;
  const up = changePct >= 0;

  // Largest peak-to-trough fall in the window. This is the number that teaches
  // a beginner what "normal volatility" actually means for a real company.
  let peak = -Infinity;
  let maxDrawdown = 0;
  for (const b of bars) {
    peak = Math.max(peak, b.close);
    if (peak > 0) maxDrawdown = Math.min(maxDrawdown, (b.close - peak) / peak);
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1" role="group" aria-label="Chart time range">
          {RANGES.map((r) => (
            <button
              key={r.label}
              onClick={() => setRange(r)}
              aria-pressed={range.label === r.label}
              className={`rounded px-2 py-1 text-xs font-medium transition ${
                range.label === r.label
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        {bars.length > 1 && (
          <span className={`text-xs font-medium ${up ? "text-emerald-600" : "text-red-600"}`}>
            {up ? "+" : ""}
            {changePct.toFixed(1)}% over {range.label}
          </span>
        )}
      </div>

      <div className="h-40 w-full">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-xs text-slate-400">
            Loading price history…
          </div>
        ) : error || bars.length < 2 ? (
          <div className="flex h-full items-center justify-center px-4 text-center text-xs text-slate-400">
            Price history isn&apos;t available for this symbol right now.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={bars} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "#94a3b8" }}
                tickFormatter={(d: string) =>
                  new Date(d).toLocaleDateString("en-IN", { month: "short", year: "2-digit" })
                }
                minTickGap={40}
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fontSize: 10, fill: "#94a3b8" }}
                tickFormatter={(v) => String(Math.round(Number(v)))}
                width={44}
              />
              <Tooltip
                formatter={(v) => [rupees(Number(v ?? 0)), "Close"]}
                labelFormatter={(d) =>
                  new Date(String(d)).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })
                }
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
              />
              <Line
                type="monotone"
                dataKey="close"
                stroke={up ? "#059669" : "#dc2626"}
                strokeWidth={1.75}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {bars.length > 1 && maxDrawdown < -0.02 && (
        <p className="mt-1.5 text-xs text-slate-500">
          Biggest fall in this period: {(maxDrawdown * 100).toFixed(1)}%. Swings like this are
          normal — it&apos;s the selling during them that costs people money.
        </p>
      )}
    </div>
  );
}
