"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher, type ConceptSummary, type GlossaryTerm } from "@/lib/api";
import { Card, CardHeader } from "@/components/Card";
import { ErrorState, LoadingCard } from "@/components/States";

const DIFFICULTY_STYLES: Record<string, string> = {
  beginner: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  intermediate: "bg-amber-50 text-amber-700 ring-amber-200",
};

export default function LearnIndexPage() {
  const { data: concepts, error, isLoading } = useSWR<ConceptSummary[]>(
    "/learn/concepts",
    fetcher,
  );
  const { data: glossary } = useSWR<GlossaryTerm[]>("/learn/glossary", fetcher);

  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-900">Concept library</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
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
            className="group rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-indigo-300 hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <div className="mb-2 flex items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ${
                  DIFFICULTY_STYLES[c.difficulty] ?? DIFFICULTY_STYLES.beginner
                }`}
              >
                {c.difficulty}
              </span>
              <span className="text-xs text-slate-500">{c.read_minutes} min read</span>
            </div>
            <h2 className="font-semibold text-slate-900 group-hover:text-indigo-700">
              {c.title}
            </h2>
            <p className="mt-1 text-sm text-slate-600">{c.one_liner}</p>
            {c.quiz && (
              <p className="mt-3 text-xs font-medium text-indigo-600">
                Includes a quiz →
              </p>
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
                  <dt className="text-sm font-medium text-slate-900">{t.label}</dt>
                  <dd className="mt-0.5 text-sm text-slate-600">{t.definition}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </section>
      )}
    </div>
  );
}
