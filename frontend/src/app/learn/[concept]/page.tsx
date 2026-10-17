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
        <Link href="/learn" className="mt-4 inline-block text-sm text-brand underline">
          Back to the library
        </Link>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="mx-auto max-w-3xl">
      <nav aria-label="Breadcrumb" className="mb-6 text-sm">
        <Link href="/learn" className="text-brand hover:underline">
          Concept library
        </Link>
        <span className="mx-2 text-subtle">/</span>
        <span className="text-muted">{data.title}</span>
      </nav>

      <header className="mb-8">
        <h1 className="font-display text-3xl font-bold text-white">{data.title}</h1>
        <p className="mt-2 text-lg text-muted">{data.one_liner}</p>
        <p className="mt-3 label">
          {data.difficulty} · {data.read_minutes} min read
        </p>
      </header>

      <article className="space-y-7">
        {data.body.map((section) => (
          <section key={section.heading}>
            <h2 className="mb-2 font-display text-lg font-semibold text-white">
              {section.heading}
            </h2>
            <p className="leading-relaxed text-muted">{section.text}</p>
          </section>
        ))}
      </article>

      {/* Misconception block */}
      <section className="mt-8 rounded-2xl border border-warn/25 bg-warn/8 p-5">
        <h2 className="mb-2 label text-warn">Common misconception</h2>
        <p className="text-sm font-medium text-fg">
          &ldquo;{data.misconception.myth}&rdquo;
        </p>
        <p className="mt-2 text-sm text-muted">{data.misconception.reality}</p>
      </section>

      {/* Takeaways */}
      <section className="mt-6 rounded-2xl border border-hairline bg-elev-1 p-5">
        <h2 className="mb-3 label">Worth remembering</h2>
        <ul className="space-y-2">
          {data.takeaways.map((t) => (
            <li key={t} className="flex gap-2 text-sm text-muted">
              <span aria-hidden="true" className="text-brand">•</span>
              <span>{t}</span>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-8 flex flex-wrap gap-3">
        {data.quiz && (
          <Link
            href={`/coach/quiz/${data.quiz}`}
            className="btn-primary rounded-lg px-4 py-2 text-sm font-semibold"
          >
            Take the {data.title.toLowerCase()} quiz
          </Link>
        )}
        <Link
          href="/market"
          className="btn-ghost rounded-lg px-4 py-2 text-sm font-medium"
        >
          Practise in the market
        </Link>
      </div>

      {data.related_rules.length > 0 && (
        <p className="mt-6 text-xs text-subtle">
          DolFin will warn you about this automatically when it matters — this concept is
          linked to the{" "}
          {data.related_rules.map((r) => r.replaceAll("_", " ")).join(" and ")}{" "}
          {data.related_rules.length === 1 ? "rule" : "rules"}.
        </p>
      )}
    </div>
  );
}
