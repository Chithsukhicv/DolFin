"use client";

import Link from "next/link";
import useSWR from "swr";
import { ai } from "@/lib/api";
import { Card, CardHeader } from "@/components/Card";

/**
 * Concepts the learner attempted and did not pass.
 *
 * The seeded bank holds three questions per concept, so a second or third
 * attempt measures whether they remember the answers rather than whether they
 * understand the idea. These links go straight to freshly generated questions
 * drawn from the same concept material, which is the only way a retest means
 * anything.
 *
 * Renders nothing when there is nothing to retest — an empty "well done" card on
 * every page load is noise.
 */
export function RetestPanel({ userId }: { userId: string }) {
  const { data } = useSWR(
    userId ? ["retest", userId] : null,
    () => ai.adaptiveTargets(userId),
    { revalidateOnFocus: false },
  );

  const concepts = data?.concepts ?? [];
  if (concepts.length === 0) return null;

  return (
    <Card className="border-amber-200 bg-amber-50/50">
      <CardHeader
        title="Worth re-testing"
        subtitle="You've attempted these and not passed yet — these links give you new questions, not the same ones"
      />
      <div className="flex flex-wrap gap-2">
        {concepts.map((concept) => (
          <Link
            key={concept}
            href={`/coach/quiz/${concept}`}
            className="rounded-full bg-white px-3 py-1.5 text-sm capitalize text-slate-700 ring-1 ring-amber-200 hover:bg-amber-100"
          >
            {concept.replaceAll("_", " ")} →
          </Link>
        ))}
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Passing any one of these raises your Discipline sub-score. Each distinct
        concept counts once, so there&apos;s nothing to gain from repeating one you
        already passed.
      </p>
    </Card>
  );
}
