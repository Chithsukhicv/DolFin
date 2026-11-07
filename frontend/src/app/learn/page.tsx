"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher, type ConceptSummary, type GlossaryTerm } from "@/lib/api";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState, LoadingCard } from "@/components/States";

const DIFFICULTY_STYLES: Record<string, string> = {
  beginner: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/25",
  intermediate: "bg-amber-500/15 text-amber-300 ring-amber-500/25",
};

export default function LearnIndexPage() {
  const { data: concepts, error, isLoading } = useSWR<ConceptSummary[]>(
    "/learn/concepts",
    fetcher,
  );
  const { data: glossary } = useSWR<GlossaryTerm[]>("/learn/glossary", fetcher);

  return (
    <div>
      <header className="mb-8 animate-rise">
        <p className="label mb-1" style={{ color: "#22D3EE" }}>Education</p>
        <h1 className="font-display text-2xl font-bold text-white">Concept Library</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Every idea DolFin coaches you on, explained before you need it. Nothing here costs
          money or affects your portfolio — read in any order.
        </p>
      </header>

      {error && <ErrorState error={error} label="Couldn't load the library" />}
      {isLoading && <LoadingCard lines={4} />}

      <div className="grid gap-4 sm:grid-cols-2">
        {concepts?.map((c) => (
          <Link
            key={c.key}
            href={`/learn/${c.key}`}
            className="group relative overflow-hidden rounded-2xl p-5 transition"
            style={{
              background: "rgb(11 11 27 / 0.85)",
              border: "1px solid rgb(34 211 238 / 0.15)",
              boxShadow: "0 0 20px -8px rgb(34 211 238 / 0.08)",
            }}
          >
            <div
              className="absolute inset-x-0 top-0 h-px transition-opacity opacity-0 group-hover:opacity-100"
              style={{ background: "linear-gradient(90deg, transparent, #22D3EE, transparent)" }}
              aria-hidden
            />
            <div className="mb-2 flex items-center gap-2">
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                style={
                  c.difficulty === "beginner"
                    ? { background: "rgb(16 217 160 / 0.12)", color: "#10D9A0", border: "1px solid rgb(16 217 160 / 0.25)" }
                    : { background: "rgb(245 166 35 / 0.12)", color: "#F5A623", border: "1px solid rgb(245 166 35 / 0.25)" }
                }
              >
                {c.difficulty}
              </span>
              <span className="text-xs text-muted">{c.read_minutes} min read</span>
            </div>
            <h2 className="font-semibold text-white transition-colors group-hover:text-cyan-300">{c.title}</h2>
            <p className="mt-1 text-sm text-muted">{c.one_liner}</p>
            {c.quiz && (
              <p className="mt-3 text-xs font-medium" style={{ color: "#22D3EE" }}>Includes a quiz →</p>
            )}
          </Link>
        ))}
      </div>

      {glossary && glossary.length > 0 && (
        <section className="mt-10">
          <Card>
            <CardHeader
              title="Glossary"
              subtitle={`${glossary.length} terms, in plain language`}
            />
            <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
              {glossary.map((t) => (
                <div key={t.term}>
                  <dt className="text-sm font-semibold text-fg">{t.label}</dt>
                  <dd className="mt-0.5 text-sm text-muted">{t.definition}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </section>
      )}
    </div>
  );
}
