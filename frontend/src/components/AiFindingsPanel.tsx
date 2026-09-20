"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ai, type AiFinding } from "@/lib/api";
import { severityClasses } from "@/lib/format";
import { AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";

/**
 * The AI's second opinion on a trade.
 *
 * The nine deterministic rules each check one measurable threshold, which makes
 * them reproducible but also means they only catch what someone thought to
 * encode. This panel shows what the AI reviewer found looking at the whole
 * portfolio — correlated exposure across sectors that move together, a goal
 * horizon that doesn't survive the resulting risk, buying back into a symbol
 * already sold at a loss twice.
 *
 * It renders separately from the rule findings and arrives later on purpose. The
 * preview must not wait on a model call, so the review runs after the response
 * is sent and this polls for it. Rule findings are on screen the whole time.
 */

const POLL_MS = 1500;

/** R13.10 — how long the in-progress indicator may stay on screen. */
const INDICATOR_TIMEOUT_MS = 15_000;

/** R13.11 — findings that land after the wait ended are still appended, so a slow
 *  review is late rather than lost. Polling continues quietly, without a spinner,
 *  for as long as the modal is open. */
const BACKGROUND_POLL_MS = 4000;
const ABANDON_MS = 60_000;

export function AiFindingsPanel({
  previewId,
  userId,
}: {
  previewId: string;
  userId: string;
}) {
  const [findings, setFindings] = useState<AiFinding[] | null>(null);
  const [state, setState] = useState<
    "waiting" | "waiting_quietly" | "done" | "unavailable" | "gave_up"
  >("waiting");
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    const startedAt = Date.now();

    async function poll() {
      if (cancelled.current) return;
      const elapsed = Date.now() - startedAt;

      try {
        const res = await ai.findings(previewId, userId);
        if (cancelled.current) return;

        if (res.status === "unavailable") {
          setState("unavailable");
          return;
        }
        if (res.status === "ready") {
          setFindings(res.findings);
          setState("done");
          return;
        }
      } catch {
        // A failed review must never break the trade flow. Stop quietly.
        setState("gave_up");
        return;
      }

      // Past 15 seconds the spinner comes down (R13.10) but the request does
      // not: the rule findings are what matter and they have been on screen the
      // whole time, so there is no reason to give up on a late second opinion.
      if (elapsed >= ABANDON_MS) {
        setState("gave_up");
        return;
      }
      if (elapsed >= INDICATOR_TIMEOUT_MS) {
        setState("waiting_quietly");
        setTimeout(poll, BACKGROUND_POLL_MS);
        return;
      }
      setTimeout(poll, POLL_MS);
    }

    poll();
    return () => {
      cancelled.current = true;
    };
  }, [previewId, userId]);

  // Nothing to say: no model configured, timed out, or the review genuinely
  // found nothing beyond what the rules already raised. In every one of those
  // cases an empty panel is better than a message about plumbing.
  if (state === "unavailable" || state === "gave_up") return null;
  // Still working, but past the point where a spinner is informative rather than
  // irritating. Render nothing and append if it arrives.
  if (state === "waiting_quietly") return null;
  if (state === "done" && (!findings || findings.length === 0)) {
    return (
      <p className="mb-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
        <AiBadge mode="generated" className="mr-1.5" />
        The AI reviewer looked at your whole portfolio alongside this trade and found
        nothing further to flag.
      </p>
    );
  }

  if (state === "waiting") {
    return (
      <p
        role="status"
        aria-live="polite"
        className="mb-4 flex items-center gap-2 rounded-xl border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-800"
      >
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" aria-hidden />
        The AI reviewer is checking your whole portfolio for anything the rules missed…
      </p>
    );
  }

  return (
    <div className="mb-4 space-y-2">
      <p className="flex items-center gap-2 text-xs font-medium text-slate-600">
        <AiBadge mode="generated" />
        Also worth knowing — found by the AI reviewer, not by a rule
      </p>

      {findings!.map((f) => {
        const cls = severityClasses(f.severity);
        return (
          <div key={f.id} className={`rounded-xl border p-3 text-sm ${cls.panel}`}>
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <strong className={cls.text}>{f.title}</strong>
              {f.confidence && f.confidence !== "high" && (
                <span className="rounded bg-white/70 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-500">
                  {f.confidence} confidence
                </span>
              )}
            </div>
            <p className={cls.text}>{f.body}</p>
            {f.concept && (
              <Link
                href={`/learn/${f.concept}`}
                className="mt-2 inline-block text-xs font-medium underline underline-offset-2"
              >
                Understand {f.concept.replaceAll("_", " ")} →
              </Link>
            )}
            <Citations citations={f.citations} />
          </div>
        );
      })}

      <p className="text-xs text-slate-500">
        These don&apos;t affect your Readiness Score — that&apos;s computed only from the
        deterministic rules, so the same trade always scores the same.
      </p>
      <AiDisclaimer compact />
    </div>
  );
}
