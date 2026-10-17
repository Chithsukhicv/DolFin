"use client";

import useSWR from "swr";
import { fetcher, type ReasoningClass, type StoredReflection } from "@/lib/api";
import { Card, CardHeader } from "@/components/Card";
import { AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";
import { EmptyState, ErrorState } from "@/components/States";

const CLASS_COPY: Record<ReasoningClass, { label: string; border: string; bg: string; hint: string }> = {
  sound: {
    label: "Sound reasoning",
    border: "border-pos/25",
    bg: "bg-pos/8",
    hint: "Didn't depend on guessing the price.",
  },
  partly_sound: {
    label: "Partly there",
    border: "border-hairline-strong",
    bg: "bg-elev-2",
    hint: "A real reason mixed with a prediction, or too vague to stand alone.",
  },
  prediction_based: {
    label: "A prediction, not a reason",
    border: "border-warn/25",
    bg: "bg-warn/8",
    hint: "The decision may have been right; the justification was a forecast.",
  },
};

export function ReflectionHistory({ userId }: { userId: string }) {
  const { data, error, mutate } = useSWR<StoredReflection[]>(
    userId ? `/reflections/user/${userId}` : null,
    fetcher,
  );

  if (error) {
    return <ErrorState error={error} label="Couldn't load your reflections" onRetry={() => mutate()} />;
  }
  if (!data) return null;

  const written = data.filter((r) => r.reason && r.reason.trim().length > 0);
  const assessed = written.filter((r) => r.ai_response);
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
                  className={`rounded-xl border p-4 ${copy?.border ?? "border-hairline"} ${copy?.bg ?? "bg-elev-2"}`}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-subtle">
                    <span className="font-medium capitalize text-fg">
                      {r.side} {r.quantity} {r.symbol}
                    </span>
                    <span>· cancelled {new Date(r.created_at).toLocaleDateString()}</span>
                    {r.triggering_rule_ids.length > 0 && (
                      <span>
                        · after {r.triggering_rule_ids.map((x) => x.replaceAll("_", " ")).join(", ")}
                      </span>
                    )}
                  </div>

                  <blockquote className="border-l-2 border-hairline-strong pl-3 text-sm italic text-muted">
                    &ldquo;{r.reason}&rdquo;
                  </blockquote>

                  {r.ai_response && (
                    <div className="mt-3 border-t border-hairline pt-2">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        {copy && <strong className="text-sm text-fg">{copy.label}</strong>}
                        {r.ai_mode && <AiBadge mode={r.ai_mode} />}
                      </div>
                      <p className="text-sm text-muted">{r.ai_response}</p>
                      {copy && <p className="mt-1 text-xs text-subtle">{copy.hint}</p>}
                      <Citations citations={r.ai_citations} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>

          <p className="mt-3 text-xs text-subtle">
            Backing out counted as heeding the warning every time, whatever the
            reasoning looked like — the score rewards the decision, not the wording.
          </p>
          {assessed.length > 0 && <AiDisclaimer />}
        </>
      )}
    </Card>
  );
}
