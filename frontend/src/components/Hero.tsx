"use client";

import Link from "next/link";

export function Hero() {
  return (
    <div className="relative">
      <div className="aurora" aria-hidden />

      <div className="relative grid items-center gap-14 lg:grid-cols-[1.02fr_0.98fr] lg:gap-10">
        <div className="animate-rise">
          <Badge />

          <h1 className="mt-6 font-display text-[2.6rem] font-extrabold leading-[1.04] tracking-tight sm:text-[3.4rem]">
            <span className="text-white">The costliest</span>
            <br />
            <span className="text-white">beginner mistake</span>
            <br />
            <span className="bg-gradient-to-r from-indigo-400 via-cyan-300 to-indigo-400 bg-clip-text text-transparent">
              isn&apos;t the wrong stock.
            </span>
          </h1>

          <p className="mt-6 max-w-lg text-[15px] leading-relaxed text-muted">
            It&apos;s selling the right one in a panic. DolFin hands you{" "}
            <span className="metric font-bold text-white">₹1,00,000</span> of practice
            money at live NSE prices, then deliberately crashes the market on you — so the
            first time you feel that urge to sell, it costs you nothing.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link href="#get-started" className="btn-primary rounded-xl px-6 py-3 text-sm font-semibold">
              Start practising — free
            </Link>
            <Link href="/learn" className="btn-ghost rounded-xl px-6 py-3 text-sm font-semibold">
              Read the concepts
            </Link>
          </div>

          <p className="mt-4 text-xs text-subtle">No card. No real money. Nothing to lose.</p>
        </div>

        <TerminalPanel />
      </div>

      <StatStrip />
    </div>
  );
}

function Badge() {
  return (
    <div className="inline-flex items-center gap-2.5 rounded-full border border-hairline-strong bg-surface/70 px-3.5 py-1.5">
      <span className="live-dot h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden />
      <span className="label !text-[10px] !tracking-[0.12em] text-emerald-300">Live NSE data</span>
      <span className="h-3 w-px bg-hairline-strong" aria-hidden />
      <span className="text-xs text-muted">Simulated money</span>
    </div>
  );
}

function TerminalPanel() {
  return (
    <div className="scene animate-rise hidden lg:block" style={{ animationDelay: "120ms" }}>
      <div className="tilt relative">
        <div
          aria-hidden
          className="absolute -inset-8 rounded-[2rem] opacity-60 blur-3xl"
          style={{ background: "radial-gradient(50% 50% at 50% 50%, rgb(99 102 241 / 0.32), transparent 70%)" }}
        />
        <div className="card relative overflow-hidden rounded-2xl p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-rose-400/70" />
              <span className="h-2 w-2 rounded-full bg-amber-400/70" />
              <span className="h-2 w-2 rounded-full bg-emerald-400/70" />
              <span className="label ml-2">coach_check.log</span>
            </div>
            <span className="label">9 rules</span>
          </div>

          <div className="rounded-xl border border-rose-500/25 bg-rose-500/[0.07] p-3.5">
            <div className="flex items-center gap-2">
              <span className="rounded bg-rose-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-rose-300">
                critical
              </span>
              <span className="font-mono text-[11px] text-subtle">panic_sell</span>
            </div>
            <p className="mt-2 text-sm font-semibold text-white">Selling into a falling market</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              A paper loss only becomes real when you sell. This is the rehearsal that makes the real thing survivable.
            </p>
          </div>

          <div className="mt-3 rounded-xl border border-violet-500/25 bg-violet-500/[0.07] p-3.5">
            <div className="flex items-center gap-2">
              <span className="rounded bg-violet-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-300">
                ai coach
              </span>
              <span className="font-mono text-[11px] text-subtle">grounded in your history</span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              &ldquo;You&apos;ve overridden this warning twice before. Your diversification is genuinely
              good — the issue is what you do when prices fall.&rdquo;
            </p>
          </div>

          <div className="mt-3 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.07] p-3">
            <p className="font-mono text-[11px] text-subtle">learner typed:</p>
            <p className="mt-1 text-xs italic text-muted">
              &ldquo;The business hasn&apos;t changed, only the price has.&rdquo;
            </p>
            <div className="mt-2 flex items-center gap-2">
              <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                sound reasoning
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatStrip() {
  const items = [
    { v: "9", l: "risk rules", h: "checked before every trade" },
    { v: "0–100", l: "readiness score", h: "earned on habits, not luck" },
    { v: "−30%", l: "crash rehearsal", h: "survive it on paper first" },
    { v: "2", l: "RAG corpora", h: "our material + your record" },
  ];
  return (
    <dl className="stagger mt-16 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-hairline bg-hairline sm:grid-cols-4">
      {items.map((s) => (
        <div key={s.l} className="bg-surface p-5">
          <dt className="metric text-2xl font-bold text-white">{s.v}</dt>
          <dd className="label mt-2">{s.l}</dd>
          <dd className="mt-1 text-[11px] leading-snug text-subtle">{s.h}</dd>
        </div>
      ))}
    </dl>
  );
}
