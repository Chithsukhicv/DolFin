"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearUserId } from "@/lib/session";
import { useUserId } from "@/lib/useSession";

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
    return pathname === href || pathname?.startsWith(`${href}/`);
  }

  function signOut() {
    clearUserId();
    setOpen(false);
    router.push("/");
  }

  return (
    <header
      className="glass sticky top-0 z-40"
      style={{ borderBottom: "1px solid rgb(124 58 237 / 0.2)" }}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        {/* Logo */}
        <Link href="/" className="group flex shrink-0 items-center gap-2.5">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-xl text-sm font-bold text-white"
            style={{
              background: "linear-gradient(135deg, #7C3AED, #22D3EE)",
              boxShadow: "0 0 16px rgb(124 58 237 / 0.5)",
            }}
          >
            D
          </div>
          <span className="font-display text-xl font-extrabold tracking-tight">
            <span
              style={{
                background: "linear-gradient(135deg, #A855F7, #22D3EE)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              Dol
            </span>
            <span className="text-white">Fin</span>
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider"
            style={{
              background: "rgb(124 58 237 / 0.15)",
              border: "1px solid rgb(124 58 237 / 0.3)",
              color: "#A855F7",
            }}
          >
            Practice
          </span>
        </Link>

        {hasUser && (
          <>
            {/* Desktop nav */}
            <nav aria-label="Main" className="hidden items-center gap-0.5 lg:flex">
              {LINKS.map((l) => {
                const active = isActive(l.href);
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    aria-current={active ? "page" : undefined}
                    className="relative rounded-xl px-3.5 py-1.5 text-sm transition"
                    style={
                      active
                        ? {
                            background: "rgb(124 58 237 / 0.15)",
                            color: "#A855F7",
                            fontWeight: 600,
                            border: "1px solid rgb(168 85 247 / 0.2)",
                          }
                        : {
                            color: "#A1A1B5",
                            fontWeight: 400,
                          }
                    }
                  >
                    {l.label}
                    {l.ai && (
                      <span
                        aria-hidden
                        className="ml-1 inline-block h-1.5 w-1.5 rounded-full align-super"
                        style={{ background: "#A855F7", boxShadow: "0 0 6px #A855F7" }}
                      />
                    )}
                    {active && (
                      <span
                        className="absolute bottom-0 inset-x-3 h-px rounded-full"
                        style={{ background: "linear-gradient(90deg, #7C3AED, #22D3EE)" }}
                        aria-hidden
                      />
                    )}
                  </Link>
                );
              })}
              <button
                onClick={signOut}
                className="ml-2 rounded-xl px-3.5 py-1.5 text-sm transition"
                style={{ color: "#6b6b85" }}
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
              className="rounded-xl p-2 transition lg:hidden"
              style={{ color: "#A1A1B5", background: "rgb(124 58 237 / 0.08)" }}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
                {open ? (
                  <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                ) : (
                  <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
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
          className="animate-rise px-4 py-3 lg:hidden"
          style={{ borderTop: "1px solid rgb(124 58 237 / 0.15)", background: "#0B0B1B" }}
        >
          <ul className="grid grid-cols-2 gap-1.5">
            {LINKS.map((l) => {
              const active = isActive(l.href);
              return (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    onClick={() => setOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className="block rounded-xl px-3 py-2.5 text-sm transition"
                    style={
                      active
                        ? {
                            background: "rgb(124 58 237 / 0.15)",
                            color: "#A855F7",
                            fontWeight: 600,
                          }
                        : { color: "#A1A1B5" }
                    }
                  >
                    {l.label}
                    {l.ai && (
                      <span
                        aria-hidden
                        className="ml-1 inline-block h-1.5 w-1.5 rounded-full align-super"
                        style={{ background: "#A855F7" }}
                      />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
          <button
            onClick={signOut}
            className="mt-2 w-full rounded-xl px-3 py-2 text-left text-sm"
            style={{ color: "#6b6b85" }}
          >
            Sign out
          </button>
        </nav>
      )}
    </header>
  );
}
