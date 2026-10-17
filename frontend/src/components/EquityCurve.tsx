"use client";

import useSWR from "swr";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetcher, type EquityPoint } from "@/lib/api";
import { rupees } from "@/lib/format";
import { EmptyState } from "./States";

/**
 * Portfolio value over time.
 *
 * This chart is the payoff for the whole crash-simulator idea. Telling someone
 * "holding through a downturn beats selling" is an assertion; showing them the
 * dip and recovery on their own portfolio is evidence. Scenario boundaries are
 * marked so the crash is identifiable rather than just a wobble.
 */
export function EquityCurve({ userId }: { userId: string }) {
  const { data } = useSWR<EquityPoint[]>(
    userId ? `/history/equity/${userId}` : null,
    fetcher,
    { refreshInterval: 30_000 },
  );

  if (!data) return null;

  if (data.length < 2) {
    return (
      <EmptyState title="Not enough history yet">
        Your portfolio value gets recorded on every trade and whenever a scenario starts.
        Make a couple of trades and this becomes a chart.
      </EmptyState>
    );
  }

  const points = data.map((p, i) => ({
    ...p,
    i,
    label: new Date(p.at).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
    }),
  }));

  const values = points.map((p) => p.total_value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.1, 500);

  const first = points[0].total_value;
  const last = points[points.length - 1].total_value;
  const change = last - first;
  const changePct = first > 0 ? (change / first) * 100 : 0;
  const up = change >= 0;

  const scenarioStarts = points.filter((p) => p.reason === "scenario_start");
  const trough = points.reduce((lo, p) => (p.total_value < lo.total_value ? p : lo), points[0]);

  const strokeColor = up ? "#00D6A0" : "#FF6B6B";
  const fillId = up ? "equityFillUp" : "equityFillDown";

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="metric text-2xl font-bold text-white">{rupees(last)}</span>
        <span className={`text-sm font-medium ${up ? "text-pos" : "text-neg"}`}>
          {up ? "+" : ""}
          {rupees(change)} ({changePct.toFixed(1)}%)
        </span>
        <span className="text-xs text-subtle">since you started</span>
      </div>

      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="equityFillUp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00D6A0" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#00D6A0" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="equityFillDown" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FF6B6B" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#FF6B6B" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: "#949aa6" }}
              interval="preserveStartEnd"
              minTickGap={30}
              axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
              tickLine={false}
            />
            <YAxis
              domain={[min - pad, max + pad]}
              tick={{ fontSize: 11, fill: "#949aa6" }}
              tickFormatter={(v) => `${Math.round(v / 1000)}k`}
              width={44}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(v) => [rupees(Number(v ?? 0)), "Portfolio value"]}
              labelFormatter={(_, payload) => {
                const p = payload?.[0]?.payload as EquityPoint | undefined;
                if (!p) return "";
                const when = new Date(p.at).toLocaleString("en-IN", {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                });
                const why =
                  p.reason === "trade"
                    ? "after a trade"
                    : p.reason === "scenario_start"
                    ? "scenario started"
                    : p.reason === "scenario_stop"
                    ? "scenario ended"
                    : "";
                return why ? `${when} · ${why}` : when;
              }}
              contentStyle={{
                fontSize: 12,
                borderRadius: 10,
                background: "var(--elev-3)",
                border: "1px solid var(--hairline-strong)",
                color: "var(--fg)",
              }}
            />
            <Area
              type="monotone"
              dataKey="total_value"
              stroke={strokeColor}
              strokeWidth={2}
              fill={`url(#${fillId})`}
            />
            {scenarioStarts.map((p) => (
              <ReferenceDot
                key={p.at}
                x={p.label}
                y={p.total_value}
                r={4}
                fill="#fdd663"
                stroke="rgba(255,255,255,0.2)"
                strokeWidth={1.5}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-2 text-xs text-subtle">
        {scenarioStarts.length > 0 ? (
          <>
            Amber dots mark where you started a scenario. Lowest point so far:{" "}
            {rupees(trough.total_value)}.
          </>
        ) : (
          <>Each point is a trade or scenario change. Start a crash to see how a dip feels.</>
        )}
      </p>
    </div>
  );
}
