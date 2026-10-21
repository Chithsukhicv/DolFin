"use client";

import { ApiError } from "@/lib/api";

export function LoadingCard({ lines = 3 }: { lines?: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-2xl p-5"
      style={{
        background: "rgb(11 11 27 / 0.85)",
        border: "1px solid rgb(124 58 237 / 0.15)",
      }}
    >
      <span className="sr-only">Loading…</span>
      <div className="animate-pulse space-y-3">
        <div className="h-3.5 w-1/3 rounded" style={{ background: "rgb(168 85 247 / 0.15)" }} />
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className="h-3 rounded"
            style={{
              width: `${90 - i * 12}%`,
              background: "rgb(124 58 237 / 0.1)",
            }}
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
  const message = error instanceof Error ? error.message : "An unexpected error occurred.";

  return (
    <div
      role="alert"
      className="rounded-2xl p-5 text-sm"
      style={{
        background: "rgb(242 87 103 / 0.07)",
        border: "1px solid rgb(242 87 103 / 0.25)",
      }}
    >
      <p className="font-semibold" style={{ color: "#F25767" }}>
        {offline ? "Can't reach the server" : label}
      </p>
      <p className="mt-1 text-muted">{message}</p>
      {offline && (
        <p className="mt-2 text-xs text-muted">
          Start the backend with{" "}
          <code
            className="rounded px-1.5 py-0.5 font-mono"
            style={{ background: "rgb(242 87 103 / 0.12)", color: "#F25767" }}
          >
            uvicorn app.main:app --reload
          </code>{" "}
          in the{" "}
          <code
            className="rounded px-1.5 py-0.5 font-mono"
            style={{ background: "rgb(242 87 103 / 0.12)", color: "#F25767" }}
          >
            backend
          </code>{" "}
          folder.
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-xl px-3 py-1.5 text-xs font-semibold transition"
          style={{
            background: "rgb(242 87 103 / 0.1)",
            border: "1px solid rgb(242 87 103 / 0.3)",
            color: "#F25767",
          }}
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
    <div
      className="rounded-2xl p-8 text-center"
      style={{
        background: "rgb(124 58 237 / 0.04)",
        border: "1px dashed rgb(124 58 237 / 0.25)",
      }}
    >
      <p className="font-display font-semibold text-white">{title}</p>
      {children && <div className="mt-1.5 text-sm text-muted">{children}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function StaleBadge({ unavailable = false }: { unavailable?: boolean }) {
  return (
    <span
      title={
        unavailable
          ? "Live price unavailable — showing your average cost instead"
          : "Price served from cache; may be a few minutes old"
      }
      className="ml-1.5 rounded font-mono text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5"
      style={{
        background: "rgb(245 166 35 / 0.12)",
        border: "1px solid rgb(245 166 35 / 0.3)",
        color: "#F5A623",
      }}
    >
      {unavailable ? "no price" : "delayed"}
    </span>
  );
}
