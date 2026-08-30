"use client";

import useSWR from "swr";
import { fetcher, type Scenario } from "@/lib/api";
import { useUserId } from "@/lib/useSession";

export function ScenarioBanner() {
  const userId = useUserId();

  const { data } = useSWR<Scenario | null>(
    userId ? `/scenarios/active/${userId}` : null,
    fetcher,
    { refreshInterval: 5000 },
  );

  if (!data || !data.is_active) return null;

  const dropPct = ((1 - data.current_multiplier) * 100).toFixed(1);
  const isCrash = data.kind === "crash" || data.kind === "correction";

  return (
    <div
      className={`border-b ${
        isCrash
          ? "border-red-300 bg-red-50 text-red-900"
          : data.kind === "rally"
          ? "border-emerald-300 bg-emerald-50 text-emerald-900"
          : "border-slate-200 bg-slate-100 text-slate-700"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-2 text-sm">
        <span>
          <strong className="uppercase tracking-wide">
            Simulated {data.kind}
          </strong>{" "}
          — {data.narrative ?? `severity ${data.severity}`}
        </span>
        <span className="rounded-full bg-white/60 px-2 py-0.5 text-xs font-medium">
          {isCrash ? `−${dropPct}%` : `${(data.current_multiplier - 1) * 100 > 0 ? "+" : ""}${(
            (data.current_multiplier - 1) * 100
          ).toFixed(1)}%`}
        </span>
      </div>
    </div>
  );
}
