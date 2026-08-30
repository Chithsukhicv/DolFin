"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearUserId } from "@/lib/session";
import { useUserId } from "@/lib/useSession";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/learn", label: "Learn" },
  { href: "/market", label: "Market" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/scenarios", label: "Scenarios" },
  { href: "/readiness", label: "Readiness" },
  { href: "/coach", label: "Coach" },
];

export default function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const hasUser = !!useUserId();

  return (
    <nav className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl font-semibold tracking-tight">
            <span className="text-indigo-600">Dol</span>Fin
          </span>
          <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-indigo-700">
            Practice
          </span>
        </Link>

        {hasUser && (
          <div className="flex flex-wrap items-center gap-1">
            {links.map((l) => {
              const active = pathname?.startsWith(l.href);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-md px-3 py-1.5 text-sm transition ${
                    active
                      ? "bg-indigo-50 font-medium text-indigo-700"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
            <button
              onClick={() => {
                clearUserId();
                router.push("/");
              }}
              className="ml-2 rounded-md px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
