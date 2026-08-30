"use client";

import { useId, useState } from "react";
import useSWR from "swr";
import { fetcher, type GlossaryTerm } from "@/lib/api";

/**
 * An inline glossary term with a definition on hover, focus or tap.
 *
 * A beginner reading "unrealised P&L" or "avg cost" has two options without
 * this: guess, or leave the page to look it up. Both lose them. Definitions
 * come from the backend glossary so there is one source of truth shared with
 * the concept library.
 *
 * Deliberately a <button>, not a <span> with a title attribute: title text is
 * invisible to keyboard users and unreliable on touch devices.
 */
export function Term({
  name,
  children,
}: {
  /** Glossary key, e.g. "unrealised_pnl". */
  name: string;
  children?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();

  // Shared SWR key means the glossary is fetched once and reused everywhere.
  const { data } = useSWR<GlossaryTerm[]>("/learn/glossary", fetcher, {
    revalidateOnFocus: false,
  });

  const entry = data?.find((t) => t.term === name);
  const label = children ?? entry?.label ?? name.replaceAll("_", " ");

  if (!entry) {
    // Unknown key or glossary still loading: render plain text rather than a
    // control that would explain nothing.
    return <>{label}</>;
  }

  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="cursor-help border-b border-dotted border-slate-400 text-inherit hover:border-indigo-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
      >
        {label}
      </button>

      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-0 z-40 mb-1.5 block w-64 rounded-lg bg-slate-900 px-3 py-2 text-xs font-normal leading-relaxed text-white shadow-lg"
        >
          {entry.definition}
        </span>
      )}
    </span>
  );
}
