"use client";

import useSWR from "swr";
import { fetcher, type ReasoningClass, type StoredReflection } from "@/lib/api";
import { Card, CardHeader } from "@/components/Card";
import { AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";
import { EmptyState, ErrorState } from "@/components/States";

/**
 * Every time the learner talked themselves out of a trade, and what the coach
 * made of their reasoning.
 *
 * Worth its own panel because these are the moments the product exists to
 * create. The assessment used to live for exactly one screen — shown in the
 * modal, then gone — which meant the most useful feedback in the app could never
 * be revisited. Reading three of your own past reasons side by side is where the
 * pattern becomes obvious: two of them said "the business hasn't changed" and one
 * said "it'll bounce back", and you can see which habit is forming.
 */

const CLASS_COPY: Record<ReasoningClass, { label: string; tone: string; hint: string }> = {
  sound: {
    label: "Sound reasoning",
    tone: "border-emerald-200 bg-emerald-50",
    hint: "Didn't depend on guessing the price.",
  },
  partly_sound: {
    label: "Partly there",
    tone: "border-slate-200 bg-slate-50",
    hint: "A real reason mixed with a prediction, or too vague to stand alone.",
  },
  prediction_based: {
    label: "A prediction, not a reason",
    tone: "border-amber-200 bg-amber-50",
    hint: "The decision may have been right; the justification was a forecast.",
  },
};

export function ReflectionHistory({ userId }: { userId: string }) {
  const { data, error, mutate } = useSWR<StoredReflection[]>(
    userId ? `/reflections/user/${userId}` : null,
    fetcher,
  );

  if (error) {
    return (
      <ErrorState
        error={error}
        label="Couldn't load your reflections"
        onRetry={() => mutate()}
      />
    );
  }
  if (!data) return null;

  const written = data.filter((r) => r.reason && r.reason.trim().length > 0);
  const assessed = written.filter((r) => r.ai_response);

  // Count the habit rather than describing it, so the summary line is a fact.
  const soundCount = assessed.filter((r) => r.reasoning_class === "sound").length;

  return (
    <Card>
      <CardHeader
        title="Times you talked yourself out of a trade"
        subtitle={
          assessed.length > 0
            ? `${soundCount} of ${assessed.length} reasons held up without predicting a price`
            : "Your own words, and what the coach made of them"
        }
      />

      {written.length === 0 ? (
        <EmptyState title="Nothing here yet">
          When a warning fires and you back out, you&apos;ll get the chance to write down
          why. That&apos;s the part that turns one good decision into a habit.
        </EmptyState>
      ) : (
        <>
          <ul className="space-y-3">
            {written.map((r) => {
              const copy = r.reasoning_class ? CLASS_COPY[r.reasoning_class] : null;
              return (
                <li
                  key={r.id}
                  className={`rounded-xl border p-4 ${copy?.tone ?? "border-slate-200"}`}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span className="font-medium capitalize text-slate-700">
                      {r.side} {r.quantity} {r.symbol}
                    </span>
                    <span>· cancelled {new Date(r.created_at).toLocaleDateString()}</span>
                    {r.triggering_rule_ids.length > 0 && (
                      <span>
                        · after {r.triggering_rule_ids.map((x) => x.replaceAll("_", " ")).join(", ")}
                      </span>
                    )}
                  </div>

                  <blockquote className="border-l-2 border-slate-300 pl-3 text-sm italic text-slate-700">
                    &ldquo;{r.reason}&rdquo;
                  </blockquote>

                  {r.ai_response && (
                    <div className="mt-3 border-t border-black/5 pt-2">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        {copy && (
                          <strong className="text-sm text-slate-800">{copy.label}</strong>
                        )}
                        {r.ai_mode && <AiBadge mode={r.ai_mode} />}
                      </div>
                      <p className="text-sm text-slate-700">{r.ai_response}</p>
                      {copy && (
                        <p className="mt-1 text-xs text-slate-500">{copy.hint}</p>
                      )}
                      <Citations citations={r.ai_citations} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>

          <p className="mt-3 text-xs text-slate-500">
            Backing out counted as heeding the warning every time, whatever the
            reasoning looked like — the score rewards the decision, not the wording.
          </p>
          {assessed.length > 0 && <AiDisclaimer />}
        </>
      )}
    </Card>
  );
}
