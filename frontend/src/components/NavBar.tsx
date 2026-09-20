"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearUserId } from "@/lib/session";
import { useUserId } from "@/lib/useSession";

/**
 * Primary navigation.
 *
 * Ten destinations is too many for one row on a phone, so below `lg` this
 * collapses to a sheet. The previous version wrapped onto three lines on a
 * narrow screen and pushed the actual page content below the fold.
 *
 * "Ask" carries a small AI dot because it behaves differently from every other
 * tab — it is the only one that generates rather than displays.
 */

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/learn", label: "Learn" },
  { href: "/market", label: "Market" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/scenarios", label: "Scenarios" },
  { href: "/readiness", label: "Readiness" },
  { href: "/coach", label: "Coach" },
  { href: "/ask", label: "Ask", ai: true },
];

export default function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const hasUser = !!useUserId();
  const [open, setOpen] = useState(false);

  function isActive(href: string) {
    // Exact match for the root-ish tabs, prefix match for nested routes like
    // /learn/diversification and /coach/quiz/fomo.
    return pathname === href || pathname?.startsWith(`${href}/`);
  }

  function signOut() {
    clearUserId();
    setOpen(false);
    router.push("/");
  }

  return (
    <header className="glass sticky top-0 z-40 border-b border-hairline">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="group flex shrink-0 items-center gap-2">
          <span className="font-display text-xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-indigo-400 to-cyan-300 bg-clip-text text-transparent">
              Dol
            </span>
            <span className="text-white">Fin</span>
          </span>
          <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-300 ring-1 ring-inset ring-indigo-500/20">
            Practice
          </span>
        </Link>

        {hasUser && (
          <>
            {/* Desktop */}
            <nav aria-label="Main" className="hidden items-center gap-0.5 lg:flex">
              {LINKS.map((l) => {
                const active = isActive(l.href);
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    aria-current={active ? "page" : undefined}
                    className={`relative rounded-lg px-3 py-1.5 text-sm transition ${
                      active
                        ? "bg-indigo-500/15 font-semibold text-indigo-300"
                        : "text-muted hover:bg-surface-hover hover:text-white"
                    }`}
                  >
                    {l.label}
                    {l.ai && (
                      <span
                        aria-hidden
                        title="AI-powered"
                        className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-violet-500 align-super"
                      />
                    )}
                  </Link>
                );
              })}
              <button
                onClick={signOut}
                className="ml-2 rounded-lg px-3 py-1.5 text-sm text-subtle transition hover:bg-surface-hover hover:text-white"
              >
                Sign out
              </button>
            </nav>

            {/* Mobile trigger */}
            <button
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              aria-controls="mobile-nav"
              aria-label={open ? "Close menu" : "Open menu"}
              className="rounded-lg p-2 text-muted transition hover:bg-surface-hover lg:hidden"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
                {open ? (
                  <path
                    d="M5 5l10 10M15 5L5 15"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                ) : (
                  <path
                    d="M3 6h14M3 10h14M3 14h14"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                )}
              </svg>
            </button>
          </>
        )}
      </div>

      {/* Mobile sheet */}
      {hasUser && open && (
        <nav
          id="mobile-nav"
          aria-label="Main"
          className="animate-rise border-t border-hairline bg-surface px-4 py-3 lg:hidden"
        >
          <ul className="grid grid-cols-2 gap-1">
            {LINKS.map((l) => {
              const active = isActive(l.href);
              return (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    onClick={() => setOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={`block rounded-lg px-3 py-2 text-sm ${
                      active
                        ? "bg-indigo-500/15 font-semibold text-indigo-300"
                        : "text-muted hover:bg-surface-hover"
                    }`}
                  >
                    {l.label}
                    {l.ai && (
                      <span
                        aria-hidden
                        className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-violet-500 align-super"
                      />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
          <button
            onClick={signOut}
            className="mt-2 w-full rounded-lg px-3 py-2 text-left text-sm text-subtle hover:bg-surface-hover"
          >
            Sign out
          </button>
        </nav>
      )}
    </header>
  );
}
