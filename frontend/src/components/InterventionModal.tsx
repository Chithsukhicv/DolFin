"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  api,
  ApiError,
  type Intervention,
  type PreviewResult,
  type ReflectionAnalysis,
  type ReflectionResult,
} from "@/lib/api";
import { rupees, severityClasses } from "@/lib/format";
import { AiFindingsPanel } from "@/components/AiFindingsPanel";
import { AiBadge, AiDisclaimer, Citations } from "@/components/AiLabel";

interface Props {
  userId: string;
  preview: PreviewResult;
  side: "buy" | "sell";
  symbol: string;
  quantity: number;
  onCancel: () => void;
  onConfirmed: () => void;
}

export function InterventionModal({
  userId,
  preview,
  side,
  symbol,
  quantity,
  onCancel,
  onConfirmed,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const heedRef = useRef<HTMLButtonElement>(null);

  // Three views in one dialog: the warnings, then optionally the "why did you
  // back out?" prompt, then the AI's read on what they wrote. Splitting these
  // into separate modals would lose the context the learner is deciding in.
  const [view, setView] = useState<"warnings" | "reflect" | "assessment">("warnings");
  const [reason, setReason] = useState("");
  const [assessment, setAssessment] = useState<ReflectionAnalysis | null>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);

  const itemsByConcept = new Map<string, Intervention>();
  for (const i of preview.interventions) {
    if (i.concept && !itemsByConcept.has(i.concept)) itemsByConcept.set(i.concept, i);
  }
  const concepts = Array.from(itemsByConcept.keys());

  // Focus the safer action first, so keyboard and screen-reader users land on
  // "reflect" rather than one tab away from overriding a critical warning.
  useEffect(() => {
    heedRef.current?.focus();
  }, []);

  // Escape closes without trading. Keeps the modal from trapping anyone.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onCancel();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onCancel]);

  // Keep Tab inside the dialog while it is open.
  const trapFocus = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !dialogRef.current) return;
    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }, []);

  function describe(err: unknown) {
    if (err instanceof ApiError) return err.message;
    return err instanceof Error ? err.message : "Something went wrong.";
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      // preview_id tells the backend which warnings this trade overrode.
      await api.post(`/portfolio/${side}`, {
        user_id: userId,
        symbol,
        side,
        quantity,
        preview_id: preview.preview_id,
      });
      onConfirmed();
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  }

  /** Record the cancellation. `note` is the learner's own words, if they wrote any. */
  async function submitReflection(note: string) {
    setBusy(true);
    setError(null);
    try {
      // Same preview_id, opposite outcome: these warnings get credited as
      // heeded, which is what raises the discipline sub-score. That happens
      // regardless of what they wrote — backing out is good behaviour even if
      // the reason they gave for it isn't.
      const result = await api.post<ReflectionResult>("/reflections", {
        user_id: userId,
        symbol,
        side,
        quantity,
        preview_id: preview.preview_id,
        triggering_rule_ids: preview.interventions.map((i) => i.rule_id),
        reason: note.trim() || "User cancelled trade after seeing the warnings",
      });

      if (result.analysis?.analysed && result.analysis.response) {
        setAssessment(result.analysis);
        setView("assessment");
      } else {
        onCancel();
      }
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  }

  function heed() {
    if (!hasWarnings) {
      // Nothing fired, so there is nothing to reflect on. Don't make them type.
      void submitReflection("");
      return;
    }
    setView("reflect");
    // Focus the textarea once it exists.
    setTimeout(() => reasonRef.current?.focus(), 0);
  }

  const cost = preview.estimated_cost ?? preview.quote.price * quantity;
  const hasWarnings = preview.interventions.length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onKeyDown={trapFocus}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="coach-check-title"
        aria-describedby="coach-check-message"
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-elev-2 p-6 shadow-xl ring-1 ring-hairline-strong"
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id="coach-check-title" className="text-xl font-semibold text-white">
            Coach check —{" "}
            <span className="capitalize">{side} {quantity} {symbol}</span>
          </h2>
          <span className="whitespace-nowrap text-sm text-muted">{rupees(cost)} approx.</span>
        </div>

        {preview.quote.stale && (
          <p role="status" className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            This price is from our cache because the live feed didn&apos;t respond. It may be a few minutes old.
          </p>
        )}

        {/* Coach summary first: this is the part learners actually read. */}
        <div id="coach-check-message" className="mb-4 rounded-xl border border-indigo-500/25 bg-indigo-500/10 p-4 text-sm text-indigo-200">
          <div className="mb-1 flex items-center gap-2">
            <strong>Your coach says:</strong>
            <AiBadge mode={preview.coach.mode} />
          </div>
          {preview.coach.message}
          {/* Only when a model actually wrote it — the offline message is a
              deterministic template and labelling it as AI would be wrong. */}
          {(preview.coach.mode === "generated" || preview.coach.mode === "cached") && (
            <AiDisclaimer compact />
          )}
        </div>

        {view === "warnings" && (
          <AiFindingsPanel previewId={preview.preview_id} userId={userId} />
        )}

        <div className={`mb-4 space-y-3 ${view === "warnings" ? "" : "hidden"}`}>
          {!hasWarnings ? (
            <p className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-4 text-sm text-emerald-300">
              No warnings on this trade.
            </p>
          ) : (
            preview.interventions.map((i) => {
              const cls = severityClasses(i.severity);
              return (
                <div key={i.rule_id} className={`rounded-xl border p-3 text-sm ${cls.panel}`}>
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls.badge}`}
                    >
                      {i.severity}
                    </span>
                    <strong className={cls.text}>{i.title}</strong>
                  </div>
                  <p className={cls.text}>{i.message}</p>
                  {i.concept && (
                    <Link
                      href={`/learn/${i.concept}`}
                      className="mt-2 inline-block text-xs font-medium underline underline-offset-2"
                    >
                      Understand {i.concept.replaceAll("_", " ")} →
                    </Link>
                  )}
                </div>
              );
            })
          )}
        </div>

        {view === "warnings" && concepts.length > 0 && (
          <div className="mb-4 rounded-xl border border-hairline-strong bg-elev-2 p-3 text-xs text-muted">
            Check your understanding — passing a quiz raises your Discipline score:
            <div className="mt-2 flex flex-wrap gap-2">
              {concepts.map((c) => (
                <Link key={c} href={`/coach/quiz/${c}`}
                  className="rounded-full border border-hairline-strong bg-elev-3 px-3 py-1 text-fg hover:border-brand hover:text-white">
                  {c.replaceAll("_", " ")} quiz →
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Step two: their own words. This is the most valuable teaching moment
            in the app — the difference between "the business hasn't changed" and
            "it'll bounce back tomorrow" is the whole lesson, and no rule can
            read either sentence. */}
        {view === "reflect" && (
          <div className="mb-4">
            <label htmlFor="reflection-reason" className="mb-1 block text-sm font-medium text-fg">
              Good call. Why are you backing out?
            </label>
            <p className="mb-2 text-xs text-subtle">
              One line is enough. Writing it down turns a decision into a habit —
              and your coach will tell you whether the reasoning holds up.
            </p>
            <textarea
              id="reflection-reason"
              ref={reasonRef}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={1000}
              placeholder="e.g. the company hasn't changed, only the price has"
              className="w-full rounded-xl border border-hairline-strong bg-elev-3 p-3 text-sm text-fg placeholder:text-subtle focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
            />
            <p className="mt-1 text-right text-xs text-subtle">{reason.length}/1000</p>
          </div>
        )}

        {/* Step three: what the coach made of it. */}
        {view === "assessment" && assessment && (
          <div className="mb-4">
            <div className={`rounded-xl border p-4 text-sm ${
                assessment.classification === "sound"
                  ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
                  : assessment.classification === "prediction_based"
                    ? "border-amber-500/25 bg-amber-500/10 text-amber-200"
                    : "border-hairline-strong bg-elev-3 text-fg"
              }`}>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <strong>{REASONING_LABEL[assessment.classification ?? "partly_sound"]}</strong>
                <AiBadge mode={assessment.mode} />
              </div>
              <p>{assessment.response}</p>
              {assessment.citations && <Citations citations={assessment.citations} />}
            </div>
            <p className="mt-2 text-xs text-subtle">
              Backing out already counted as heeding the warning. This read on your reasoning
              is advisory — it doesn&apos;t change your score either way.
            </p>
            <AiDisclaimer compact />
          </div>
        )}

        {error && <p role="alert" className="mb-3 text-sm text-neg">{error}</p>}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {view === "warnings" && (
            <>
              <button
                ref={heedRef}
                onClick={heed}
                disabled={busy}
                className="rounded-lg border border-hairline-strong bg-elev-3 px-4 py-2 text-sm font-medium text-fg hover:bg-elev-4 disabled:opacity-50"
              >
                {busy ? "Saving..." : hasWarnings ? "Cancel & reflect" : "Cancel"}
              </button>
              <button
                onClick={confirm}
                disabled={busy}
                className={`rounded-lg px-4 py-2 text-sm font-medium text-white ${
                  preview.blocking
                    ? "bg-rose-600 hover:bg-rose-700"
                    : "bg-brand-fill hover:bg-brand-fill-hover"
                } disabled:opacity-50`}
              >
                {busy ? "Working..." : preview.blocking ? `Override and ${side}` : `Confirm ${side}`}
              </button>
            </>
          )}

          {view === "reflect" && (
            <>
              <button onClick={() => setView("warnings")} disabled={busy}
                className="rounded-lg border border-hairline-strong bg-elev-3 px-4 py-2 text-sm font-medium text-fg hover:bg-elev-4 disabled:opacity-50">
                Back
              </button>
              <button onClick={() => void submitReflection("")} disabled={busy}
                className="rounded-lg px-4 py-2 text-sm font-medium text-subtle hover:text-fg disabled:opacity-50">
                Skip
              </button>
              <button onClick={() => void submitReflection(reason)} disabled={busy || reason.trim().length === 0}
                className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-white hover:bg-brand-fill-hover disabled:opacity-50">
                {busy ? "Checking..." : "Save reason"}
              </button>
            </>
          )}

          {view === "assessment" && (
            <button onClick={onCancel}
              className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-white hover:bg-brand-fill-hover">
              Done
            </button>
          )}
        </div>

        {view === "warnings" && preview.blocking && (
          <p className="mt-3 text-xs text-subtle">
            You can always override — this is practice money and the choice is yours. We just
            want the reasoning in front of you first.
          </p>
        )}
      </div>
    </div>
  );
}

const REASONING_LABEL: Record<string, string> = {
  sound: "That reasoning holds up",
  partly_sound: "Partly there",
  prediction_based: "Right call, shaky reason",
};
