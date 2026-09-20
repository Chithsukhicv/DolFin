import Link from "next/link";

/**
 * Site footer.
 *
 * The disclaimer here is not boilerplate. DolFin shows live NSE prices and an AI
 * coach discussing a learner's portfolio, which is close enough to a real
 * brokerage that the distinction has to be stated plainly and permanently rather
 * than only inside the AI panels. Specific buy/sell guidance is regulated
 * investment advice in India; an educational simulator has to be visibly on the
 * other side of that line.
 */
export function Footer() {
  return (
    <footer className="mt-16 border-t border-hairline bg-elevated/60">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2">
              <Logo />
              <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-300">
                Practice
              </span>
            </div>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted">
              A behavioural investing simulator for first-time investors. Real market
              prices, simulated money, and a coach that explains the reasoning before
              you commit.
            </p>
          </div>

          <nav aria-label="Product" className="text-sm">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-subtle">
              Product
            </h2>
            <ul className="space-y-2 text-muted">
              <li><Link href="/dashboard" className="hover:text-white">Dashboard</Link></li>
              <li><Link href="/market" className="hover:text-white">Market</Link></li>
              <li><Link href="/scenarios" className="hover:text-white">Crash simulator</Link></li>
              <li><Link href="/readiness" className="hover:text-white">Readiness Score</Link></li>
            </ul>
          </nav>

          <nav aria-label="Learn" className="text-sm">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-subtle">
              Learn
            </h2>
            <ul className="space-y-2 text-muted">
              <li><Link href="/learn" className="hover:text-white">Concept library</Link></li>
              <li><Link href="/ask" className="hover:text-white">Ask DolFin</Link></li>
              <li><Link href="/coach" className="hover:text-white">Your patterns</Link></li>
            </ul>
          </nav>
        </div>

        <div className="hairline-gradient my-8" />

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <p className="max-w-2xl text-xs leading-relaxed text-subtle">
            <span className="font-semibold text-muted">
              Educational simulator. Not investment advice.
            </span>{" "}
            Every portfolio on DolFin is simulated and no real money is ever traded.
            Prices are delayed market data shown for practice only. AI-generated
            explanations can be wrong, so the sources behind each one are listed for
            you to check. Nothing here is a recommendation to buy or sell any security.
          </p>
          <p className="whitespace-nowrap text-xs text-subtle">
            Built for learners in India
          </p>
        </div>
      </div>
    </footer>
  );
}

/** Wordmark. Kept here and in the nav rather than as a shared file — it is six
 *  elements, and a component indirection for it would cost more than it saves. */
function Logo() {
  return (
    <span className="font-display text-lg font-extrabold tracking-tight text-white">
      <span className="bg-gradient-to-r from-indigo-400 to-cyan-300 bg-clip-text text-transparent">
        Dol
      </span>
      Fin
    </span>
  );
}
