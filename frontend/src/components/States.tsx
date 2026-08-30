"use client";

import { ApiError } from "@/lib/api";

/**
 * Shared loading, error and empty states.
 *
 * Most read paths previously ignored SWR's `error`, so a backend that was down
 * produced a permanently blank card with no message and no way to retry. For a
 * beginner that is indistinguishable from "the app is broken and it's my fault".
 */

export function LoadingCard({ lines = 3 }: { lines?: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-2xl border border-slate-200 bg-white p-5"
    >
      <span className="sr-only">Loading…</span>
      <div className="animate-pulse space-y-3">
        <div className="h-4 w-1/3 rounded bg-slate-200" />
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="h-3 rounded bg-slate-100" style={{ width: `${90 - i * 12}%` }} />
        ))}
      </div>
    </div>
  );
}

export function ErrorState({
  error,
  label = "Something went wrong",
  onRetry,
}: {
  error: unknown;
  label?: string;
  onRetry?: () => void;
}) {
  const offline = error instanceof ApiError && error.isOffline;
  const message =
    error instanceof Error ? error.message : "An unexpected error occurred.";

  return (
    <div
      role="alert"
      className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800"
    >
      <p className="font-medium">{offline ? "Can't reach the server" : label}</p>
      <p className="mt-1 text-red-700">{message}</p>
      {offline && (
        <p className="mt-2 text-xs text-red-600">
          Start the backend with{" "}
          <code className="rounded bg-red-100 px-1 py-0.5">uvicorn app.main:app --reload</code>{" "}
          in the <code className="rounded bg-red-100 px-1 py-0.5">backend</code> folder.
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-6 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {children && <div className="mt-1 text-sm text-slate-500">{children}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

/** Small inline badge for prices served from cache. */
export function StaleBadge({ unavailable = false }: { unavailable?: boolean }) {
  return (
    <span
      title={
        unavailable
          ? "Live price unavailable — showing your average cost instead"
          : "Price served from cache; may be a few minutes old"
      }
      className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-800"
    >
      {unavailable ? "no price" : "delayed"}
    </span>
  );
}
