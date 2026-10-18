"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import dynamic from "next/dynamic";
import {
  api,
  fetcher,
  type Scenario,
  type ScenarioPreset,
} from "@/lib/api";
import { useRequireUser } from "@/lib/useSession";
import { Card, CardHeader } from "@/components/Card";
import { LazyCanvas } from "@/components/three/LazyCanvas";

const ScenarioScene = dynamic(
  () => import("@/components/three/ScenarioScene").then((m) => m.ScenarioScene),
  { ssr: false }
);

/* Colour config per scenario kind */
const SCENARIO_STYLES: Record<string, {
  bg: string; border: string; text: string;
  icon: string; cardClass: string; badge: string;
}> = {
  crash: {
    bg: "rgba(239,68,68,0.08)",
    border: "rgba(239,68,68,0.35)",
    text: "#ef4444",
    icon: "📉",
    cardClass: "scenario-card scenario-card-crash",
    badge: "bg-red-500/15 text-red-300 border-red-500/25",
  },
  bear: {
    bg: "rgba(220,38,38,0.08)",
    border: "rgba(220,38,38,0.35)",
    text: "#dc2626",
    icon: "🐻",
    cardClass: "scenario-card scenario-card-bear",
    badge: "bg-red-600/15 text-red-200 border-red-600/25",
  },
  bull: {
    bg: "rgba(0,214,160,0.08)",
    border: "rgba(0,214,160,0.35)",
    text: "#00D6A0",
    icon: "🚀",
    cardClass: "scenario-card scenario-card-bull",
    badge: "bg-pos/15 text-pos border-pos/25",
  },
  sideways: {
    bg: "rgba(64,217,255,0.06)",
    border: "rgba(64,217,255,0.25)",
    text: "#40D9FF",
    icon: "↔️",
    cardClass: "scenario-card scenario-card-side",
    badge: "bg-cyan-500/15 text-cyan-300 border-cyan-500/25",
  },
  correction: {
    bg: "rgba(253,214,99,0.07)",
    border: "rgba(253,214,99,0.3)",
    text: "#fdd663",
    icon: "⚠️",
    cardClass: "scenario-card scenario-card-mild",
    badge: "bg-warn/15 text-warn border-warn/25",
  },
};

function getStyle(kind: string) {
  const k = kind.toLowerCase();
  if (k.includes("crash")) return SCENARIO_STYLES.crash;
  if (k.includes("bear")) return SCENARIO_STYLES.bear;
  if (k.includes("bull")) return SCENARIO_STYLES.bull;
  if (k.includes("side")) return SCENARIO_STYLES.sideways;
  return SCENARIO_STYLES.correction;
}

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

  const activeStyle = active?.kind ? getStyle(active.kind) : null;
  const progressPct = active ? Math.round(active.progress * 100) : 0;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-bold text-white">Market Scenarios</h1>
        <p className="mt-1 text-sm text-muted">
          Practise reacting to crashes, rallies and sideways markets — without losing real money.
        </p>
      </header>

      {/* ── 3D Scenario visualization ── */}
      <div className="relative overflow-hidden rounded-2xl border border-hairline">
        <LazyCanvas
          className="h-[200px] w-full"
          camera={{ position: [0, 0, 4.5], fov: 55 }}
        >
          <ScenarioScene
            kind={
              active?.is_active
                ? (active.kind?.toLowerCase() as "crash" | "bull" | "correction" | "sideways" | "bear" | null)
                : null
            }
          />
        </LazyCanvas>
        {active?.is_active && (
          <div className="absolute bottom-2 left-3 rounded bg-black/60 px-2 py-0.5 text-xs font-semibold backdrop-blur-sm" style={{ color: "#FF6B6B" }}>
            {active.kind} scenario active
          </div>
        )}
      </div>

      {/* ── Active scenario ── */}
      {active?.is_active && activeStyle && (
        <div
          className="animate-rise rounded-2xl border p-5"
          style={{ background: activeStyle.bg, borderColor: activeStyle.border }}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-1 flex items-center gap-2">
                <span className="text-xl" aria-hidden>{activeStyle.icon}</span>
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${activeStyle.badge}`}
                >
                  Live scenario
                </span>
              </div>
              <h2 className="font-display text-lg font-bold" style={{ color: activeStyle.text }}>
                {active.kind} · severity {active.severity}
              </h2>
              {active.narrative && (
                <p className="mt-1 max-w-lg text-sm text-muted">{active.narrative}</p>
              )}
            </div>
            <button
              onClick={stop}
              disabled={busy !== null}
              className="btn-ghost shrink-0 rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-50"
            >
              {busy === "stop" ? "Stopping..." : "Stop scenario"}
            </button>
          </div>

          {/* Progress bar */}
          <div className="mt-4">
            <div className="mb-1 flex justify-between text-xs text-subtle">
              <span>Progress</span>
              <span className="font-mono font-medium" style={{ color: activeStyle.text }}>
                {progressPct}%
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-black/30">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${progressPct}%`, background: activeStyle.text }}
              />
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
            {[
              { label: "Multiplier", val: active.current_multiplier.toFixed(3) },
              { label: "Progress", val: `${progressPct}%` },
              { label: "Drawdown days", val: String(active.duration_days) },
              { label: "Recovery days", val: String(active.recovery_days) },
            ].map((m) => (
              <div key={m.label} className="rounded-xl border border-white/8 bg-black/20 p-3">
                <p className="label mb-1">{m.label}</p>
                <p className="metric text-lg font-bold text-white">{m.val}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Preset cards ── */}
      <Card>
        <CardHeader
          title="Simulation presets"
          subtitle="Tap one to start a simulated market move on your portfolio"
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {presets?.map((p) => {
            const style = getStyle(p.kind);
            return (
              <button
                key={p.label}
                onClick={() => startPreset(p)}
                disabled={busy !== null || !!active?.is_active}
                className={`${style.cardClass} w-full text-left disabled:cursor-not-allowed disabled:opacity-40`}
              >
                <div className="mb-2 flex items-center gap-2">
                  <span className="text-xl" aria-hidden>{style.icon}</span>
                  <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: style.text }}>
                    {p.kind}
                  </span>
                </div>
                <p className="font-display text-sm font-bold text-white">{p.label}</p>
                <p className="mt-1.5 text-xs text-subtle">
                  {p.duration_days}d drawdown · {p.recovery_days}d recovery
                </p>
                {busy === p.label && (
                  <p className="mt-2 text-xs font-medium" style={{ color: style.text }}>
                    Starting…
                  </p>
                )}
              </button>
            );
          })}
        </div>
        {!!active?.is_active && (
          <p className="mt-3 text-xs text-subtle">
            Stop the active scenario before starting a new one.
          </p>
        )}
        {error && <p role="alert" className="mt-3 text-sm text-neg">{error}</p>}
      </Card>

      {/* ── Why this matters ── */}
      <Card>
        <CardHeader
          title="Why this matters"
          subtitle="The hardest part of investing isn't picking stocks — it's not panic-selling when prices fall."
        />
        <ul className="space-y-2.5 text-sm text-muted">
          {[
            "A simulated −30% crash overlays your real portfolio prices.",
            "Try selling during the crash — the coach will fire a critical warning.",
            "If you cancel and reflect, your Discipline sub-score goes up.",
            "The scenario auto-recovers, mirroring how real markets behave.",
          ].map((s, i) => (
            <li key={i} className="flex gap-3">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand/15 text-[10px] font-bold text-brand">
                {i + 1}
              </span>
              {s}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
