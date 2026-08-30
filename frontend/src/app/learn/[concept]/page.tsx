"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { fetcher, type Concept } from "@/lib/api";
import { ErrorState, LoadingCard } from "@/components/States";

export default function ConceptPage() {
  const params = useParams<{ concept: string }>();
  const key = params?.concept;

  const { data, error, isLoading } = useSWR<Concept>(
    key ? `/learn/concepts/${key}` : null,
    fetcher,
  );

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl">
        <LoadingCard lines={6} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl">
        <ErrorState error={error} label="Couldn't load this concept" />
        <Link href="/learn" className="mt-4 inline-block text-sm text-indigo-600 underline">
          Back to the library
        </Link>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="mx-auto max-w-3xl">
      <nav aria-label="Breadcrumb" className="mb-6 text-sm">
        <Link href="/learn" className="text-indigo-600 hover:underline">
          Concept library
        </Link>
        <span className="mx-2 text-slate-400">/</span>
        <span className="text-slate-600">{data.title}</span>
      </nav>

      <header className="mb-8">
        <h1 className="text-3xl font-semibold text-slate-900">{data.title}</h1>
        <p className="mt-2 text-lg text-slate-600">{data.one_liner}</p>
        <p className="mt-3 text-xs uppercase tracking-wide text-slate-400">
          {data.difficulty} · {data.read_minutes} min read
        </p>
      </header>

      <article className="space-y-7">
        {data.body.map((section) => (
          <section key={section.heading}>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">{section.heading}</h2>
            <p className="leading-relaxed text-slate-700">{section.text}</p>
          </section>
        ))}
      </article>

      {/* Misconceptions get their own block because naming the wrong belief
          explicitly is more effective than only stating the right one. */}
      <section className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-amber-800">
          Common misconception
        </h2>
        <p className="text-sm font-medium text-amber-900">
          &ldquo;{data.misconception.myth}&rdquo;
        </p>
        <p className="mt-2 text-sm text-amber-800">{data.misconception.reality}</p>
      </section>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Worth remembering
        </h2>
        <ul className="space-y-2">
          {data.takeaways.map((t) => (
            <li key={t} className="flex gap-2 text-sm text-slate-700">
              <span aria-hidden="true" className="text-indigo-500">
                •
              </span>
              <span>{t}</span>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-8 flex flex-wrap gap-3">
        {data.quiz && (
          <Link
            href={`/coach/quiz/${data.quiz}`}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Take the {data.title.toLowerCase()} quiz
          </Link>
        )}
        <Link
          href="/market"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Practise in the market
        </Link>
      </div>

      {data.related_rules.length > 0 && (
        <p className="mt-6 text-xs text-slate-500">
          DolFin will warn you about this automatically when it matters — this concept is
          linked to the{" "}
          {data.related_rules.map((r) => r.replaceAll("_", " ")).join(" and ")}{" "}
          {data.related_rules.length === 1 ? "rule" : "rules"}.
        </p>
      )}
    </div>
  );
}
