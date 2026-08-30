"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import {
  api,
  fetcher,
  type Scenario,
  type ScenarioPreset,
} from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";

export default function ScenariosPage() {
  const userId = useRequireUser();

  const { data: presets } = useSWR<ScenarioPreset[]>("/scenarios/presets", fetcher);
  const { data: active } = useSWR<Scenario | null>(
    userId ? `/scenarios/active/${userId}` : null,
    fetcher,
    { refreshInterval: 5000 },
  );

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function startPreset(p: ScenarioPreset) {
    if (!userId) return;
    setBusy(p.label);
    setError(null);
    try {
      await api.post("/scenarios/start", {
        user_id: userId,
        kind: p.kind,
        severity: p.severity,
        duration_days: p.duration_days,
        recovery_days: p.recovery_days,
      });
      mutate(`/scenarios/active/${userId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  async function stop() {
    if (!userId) return;
    setBusy("stop");
    setError(null);
    try {
      await api.post("/scenarios/stop", { user_id: userId });
      mutate(`/scenarios/active/${userId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  if (!userId) return null;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Market scenarios</h1>
        <p className="text-sm text-slate-500">
          Practise reacting to crashes, rallies and sideways markets without losing real money.
        </p>
      </header>

      {active?.is_active && (
        <Card className="border-amber-300 bg-amber-50">
          <CardHeader
            title={`Active: ${active.kind} (severity ${active.severity})`}
            subtitle={active.narrative ?? ""}
            right={
              <button
                onClick={stop}
                disabled={busy !== null}
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
              >
                {busy === "stop" ? "Stopping..." : "Stop scenario"}
              </button>
            }
          />
          <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
            <div>
              <p className="text-xs text-slate-500">Multiplier</p>
              <p className="font-semibold">{active.current_multiplier.toFixed(3)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Progress</p>
              <p className="font-semibold">{(active.progress * 100).toFixed(0)}%</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Drawdown days</p>
              <p className="font-semibold">{active.duration_days}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Recovery days</p>
              <p className="font-semibold">{active.recovery_days}</p>
            </div>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Quick presets"
          subtitle="Tap one to start a simulated market move on your portfolio"
        />
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {presets?.map((p) => (
            <button
              key={p.label}
              onClick={() => startPreset(p)}
              disabled={busy !== null || !!active?.is_active}
              className="rounded-xl border border-slate-200 p-4 text-left transition hover:border-indigo-400 hover:bg-indigo-50 disabled:opacity-50"
            >
              <p className="text-sm font-semibold">{p.label}</p>
              <p className="mt-1 text-xs text-slate-500">
                {p.kind} · {p.duration_days}d drawdown · {p.recovery_days}d recovery
              </p>
              {busy === p.label && (
                <p className="mt-1 text-xs text-indigo-600">Starting...</p>
              )}
            </button>
          ))}
        </div>
        {!!active?.is_active && (
          <p className="mt-3 text-xs text-slate-500">
            Stop the active scenario before starting a new one.
          </p>
        )}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </Card>

      <Card>
        <CardHeader
          title="Why this matters"
          subtitle="The hardest part of investing isn't picking stocks — it's not panic-selling when prices fall."
        />
        <ul className="space-y-2 text-sm text-slate-700">
          <li>● A simulated -30% crash overlays your real portfolio prices.</li>
          <li>● Try selling during the crash — the coach will fire a critical warning.</li>
          <li>● If you cancel and reflect, your Discipline sub-score goes up.</li>
          <li>● The scenario auto-recovers, mirroring how real markets behave.</li>
        </ul>
      </Card>
    </div>
  );
}
