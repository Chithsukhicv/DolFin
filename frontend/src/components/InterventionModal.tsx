"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError, type Intervention, type PreviewResult } from "@/lib/api";
import { rupees, severityClasses } from "@/lib/format";

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

  async function heed() {
    setBusy(true);
    setError(null);
    try {
      // Same preview_id, opposite outcome: these warnings get credited as
      // heeded, which is what raises the discipline sub-score.
      await api.post("/reflections", {
        user_id: userId,
        symbol,
        side,
        quantity,
        preview_id: preview.preview_id,
        triggering_rule_ids: preview.interventions.map((i) => i.rule_id),
        reason: "User cancelled trade after seeing the warnings",
      });
      onCancel();
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
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
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id="coach-check-title" className="text-xl font-semibold">
            Coach check —{" "}
            <span className="capitalize">
              {side} {quantity} {symbol}
            </span>
          </h2>
          <span className="whitespace-nowrap text-sm text-slate-500">
            {rupees(cost)} approx.
          </span>
        </div>

        {preview.quote.stale && (
          <p
            role="status"
            className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
          >
            This price is from our cache because the live feed didn&apos;t respond. It may be
            a few minutes old.
          </p>
        )}

        {/* Coach summary first: this is the part learners actually read. */}
        <div
          id="coach-check-message"
          className="mb-4 rounded-xl bg-indigo-50 p-4 text-sm text-indigo-900"
        >
          <strong className="mb-1 block">Your coach says:</strong>
          {preview.coach.message}
        </div>

        <div className="mb-4 space-y-3">
          {!hasWarnings ? (
            <p className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
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

        {concepts.length > 0 && (
          <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
            Check your understanding — passing a quiz raises your Discipline score:
            <div className="mt-2 flex flex-wrap gap-2">
              {concepts.map((c) => (
                <Link
                  key={c}
                  href={`/coach/quiz/${c}`}
                  className="rounded-full bg-white px-3 py-1 ring-1 ring-slate-200 hover:bg-slate-100"
                >
                  {c.replaceAll("_", " ")} quiz →
                </Link>
              ))}
            </div>
          </div>
        )}

        {error && (
          <p role="alert" className="mb-3 text-sm text-red-600">
            {error}
          </p>
        )}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref={heedRef}
            onClick={heed}
            disabled={busy}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {busy ? "Saving..." : hasWarnings ? "Cancel & reflect" : "Cancel"}
          </button>
          <button
            onClick={confirm}
            disabled={busy}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-white ${
              preview.blocking
                ? "bg-red-600 hover:bg-red-700"
                : "bg-indigo-600 hover:bg-indigo-700"
            } disabled:opacity-50`}
          >
            {busy ? "Working..." : preview.blocking ? `Override and ${side}` : `Confirm ${side}`}
          </button>
        </div>

        {preview.blocking && (
          <p className="mt-3 text-xs text-slate-500">
            You can always override — this is practice money and the choice is yours. We just
            want the reasoning in front of you first.
          </p>
        )}
      </div>
    </div>
  );
}
