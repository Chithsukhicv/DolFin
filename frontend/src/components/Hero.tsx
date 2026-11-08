"use client";

import Link from "next/link";
import dynamic from "next/dynamic";

const FinancialSphere = dynamic(
  () => import("./FinancialSphere").then((m) => m.FinancialSphere),
  { ssr: false, loading: () => <SphereLoader /> }
);

function SphereLoader() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div
        className="h-48 w-48 rounded-full opacity-30 animate-pulse"
        style={{ background: "radial-gradient(circle at center, #7C3AED 0%, #22D3EE 60%, transparent 80%)" }}
      />
    </div>
  );
}

export function Hero() {
  return (
    <div className="relative min-h-[90vh] flex flex-col justify-center overflow-hidden">
      {/* Atmospheric aurora */}
      <div className="aurora" aria-hidden />

      {/* Background accent orbs */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 75% 40%, rgb(124 58 237 / 0.12) 0%, transparent 70%), " +
            "radial-gradient(ellipse 50% 40% at 25% 60%, rgb(34 211 238 / 0.08) 0%, transparent 70%)",
        }}
      />

      {/* Hero grid */}
      <div className="relative z-10 grid items-center gap-12 lg:grid-cols-[1fr_1fr] lg:gap-6 py-16">
        {/* LEFT: Copy */}
        <div className="animate-rise">
          <LiveBadge />

          <h1 className="mt-7 font-display leading-[1.01] tracking-tight">
            <span
              className="block text-[clamp(2.6rem,6vw,4.2rem)] font-extrabold text-white"
            >
              Master the Market.
            </span>
            <span
              className="block text-[clamp(2.6rem,6vw,4.2rem)] font-extrabold"
              style={{
                background: "linear-gradient(135deg, #A855F7 0%, #22D3EE 50%, #4F7CFF 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              Before It Costs You.
            </span>
          </h1>

          <p className="mt-6 max-w-[480px] text-[15px] leading-[1.72] text-muted">
            DolFin gives you{" "}
            <span className="font-semibold text-white metric">₹1,00,000</span> in practice
            money at live NSE prices. Trade freely, survive simulated crashes, and let the
            AI coach spot your behavioural patterns — before any of it costs real money.
          </p>

          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Link
              href="#get-started"
              className="cta-primary inline-flex items-center gap-2.5 rounded-2xl px-8 py-4 text-base font-bold"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M13 7l5 5-5 5M6 12h12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Start Practising
            </Link>
            <Link
              href="/learn"
              className="inline-flex items-center gap-2 rounded-2xl border px-8 py-4 text-base font-semibold transition"
              style={{ borderColor: "rgb(168 85 247 / 0.3)", color: "#A855F7" }}
            >
              Explore DolFin
            </Link>
          </div>

          <p className="mt-4 text-xs text-subtle">No card. No real money. Nothing to lose.</p>

          {/* Feature chips */}
          <div className="mt-8 flex flex-wrap gap-2">
            {[
              { icon: "⚡", text: "Live NSE prices" },
              { icon: "🧠", text: "AI behaviour coach" },
              { icon: "📉", text: "Crash simulations" },
              { icon: "🛡️", text: "9 risk rules" },
            ].map((f) => (
              <span
                key={f.text}
                className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium"
                style={{
                  borderColor: "rgb(168 85 247 / 0.2)",
                  background: "rgb(168 85 247 / 0.06)",
                  color: "#A1A1B5",
                }}
              >
                <span>{f.icon}</span>
                {f.text}
              </span>
            ))}
          </div>
        </div>

        {/* RIGHT: 3D Sphere */}
        <div
          className="animate-rise hidden lg:flex items-center justify-center"
          style={{ animationDelay: "120ms" }}
        >
          <div className="relative w-full" style={{ height: "520px" }}>
            {/* Glow behind sphere */}
            <div
              aria-hidden
              className="absolute inset-0 m-auto rounded-full blur-3xl opacity-25 pointer-events-none"
              style={{
                width: "70%",
                height: "70%",
                background: "radial-gradient(circle at center, #7C3AED 0%, #22D3EE 70%, transparent 100%)",
              }}
            />
            <FinancialSphere className="absolute inset-0 w-full h-full" />
          </div>
        </div>
      </div>

      {/* Product highlights strip */}
      <div className="relative z-10 mt-8">
        <div className="hairline-gradient mb-8" />
        <dl className="stagger grid grid-cols-2 gap-px overflow-hidden rounded-2xl border sm:grid-cols-4"
          style={{ borderColor: "rgb(124 58 237 / 0.2)", background: "rgb(124 58 237 / 0.06)" }}>
          {[
            { v: "9", l: "Risk Rules", h: "Active before every trade" },
            { v: "0–100", l: "Readiness Score", h: "Earned on habits, not luck" },
            { v: "−30%", l: "Crash Rehearsal", h: "Survive it on paper first" },
            { v: "RAG", l: "AI Coach", h: "Grounded in your own history" },
          ].map((s) => (
            <div key={s.l} className="relative p-5 overflow-hidden"
              style={{ background: "rgb(11 11 27 / 0.9)" }}>
              <div
                className="absolute inset-x-0 top-0 h-px"
                style={{ background: "linear-gradient(90deg, transparent, rgb(168 85 247 / 0.4), transparent)" }}
              />
              <dt
                className="metric text-2xl font-bold"
                style={{
                  background: "linear-gradient(135deg, #A855F7, #22D3EE)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                {s.v}
              </dt>
              <dd className="label mt-2">{s.l}</dd>
              <dd className="mt-1 text-[11px] leading-snug text-subtle">{s.h}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

function LiveBadge() {
  return (
    <div
      className="inline-flex items-center gap-2.5 rounded-full border px-3.5 py-1.5 backdrop-blur-sm"
      style={{
        borderColor: "rgb(16 217 160 / 0.25)",
        background: "rgb(16 217 160 / 0.06)",
      }}
    >
      <span className="live-dot h-1.5 w-1.5 rounded-full" style={{ background: "#10D9A0" }} aria-hidden />
      <span className="label !text-[10px] !tracking-[0.12em]" style={{ color: "#10D9A0" }}>
        Live NSE Data
      </span>
      <span className="h-3 w-px" style={{ background: "rgb(16 217 160 / 0.25)" }} aria-hidden />
      <span className="text-xs text-muted">Simulated money</span>
    </div>
  );
}
