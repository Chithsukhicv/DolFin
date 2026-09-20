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
    <div role="status" aria-live="polite" className="card rounded-2xl p-5">
      <span className="sr-only">Loading…</span>
      <div className="animate-pulse space-y-3">
        <div className="h-3.5 w-1/3 rounded bg-hairline-strong" />
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className="h-3 rounded bg-hairline"
            style={{ width: `${90 - i * 12}%` }}
          />
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
      className="rounded-2xl border border-rose-500/25 bg-rose-500/[0.07] p-5 text-sm"
    >
      <p className="font-semibold text-rose-200">
        {offline ? "Can't reach the server" : label}
      </p>
      <p className="mt-1 text-rose-300/80">{message}</p>
      {offline && (
        <p className="mt-2 text-xs text-rose-300/70">
          Start the backend with{" "}
          <code className="rounded bg-rose-500/15 px-1.5 py-0.5 font-mono">
            uvicorn app.main:app --reload
          </code>{" "}
          in the{" "}
          <code className="rounded bg-rose-500/15 px-1.5 py-0.5 font-mono">backend</code>{" "}
          folder.
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/20"
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
    <div className="rounded-2xl border border-dashed border-hairline-strong bg-surface-muted/50 p-8 text-center">
      <p className="font-display font-semibold text-fg">{title}</p>
      {children && <div className="mt-1.5 text-sm text-subtle">{children}</div>}
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
      className="ml-1.5 rounded border border-amber-500/25 bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide text-amber-300"
    >
      {unavailable ? "no price" : "delayed"}
    </span>
  );
}
