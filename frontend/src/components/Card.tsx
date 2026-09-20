import clsx from "clsx";
import { ReactNode } from "react";

/**
 * The surface everything sits on.
 *
 * Not hover-lifting by default. Most cards here are panels holding data, and a
 * static panel that lifts under the cursor is claiming to be clickable when it
 * isn't. Pass `interactive` only on the ones that navigate.
 */
export function Card({
  children,
  className,
  interactive = false,
  sheen = true,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  /** Top-edge highlight, like light catching the lip of a physical panel. */
  sheen?: boolean;
  as?: "div" | "section" | "article" | "li";
}) {
  return (
    <Tag
      className={clsx(
        "card rounded-2xl p-5",
        sheen && "card-sheen",
        interactive && "card-interactive cursor-pointer",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  subtitle,
  right,
  icon,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        {icon && (
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-indigo-500/25 bg-indigo-500/10 text-indigo-300">
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <h3 className="font-display text-base font-bold text-white">{title}</h3>
          {subtitle && (
            <p className="mt-0.5 text-xs leading-relaxed text-subtle">{subtitle}</p>
          )}
        </div>
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

/**
 * A single headline number.
 *
 * `metric` gives the mono face and tabular figures, so a value updating from
 * 1,299 to 1,311 does not shift sideways — jitter in a portfolio total reads as
 * instability in exactly the place a nervous beginner needs to feel none.
 */
export function Stat({
  label,
  value,
  delta,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  /** Signed change, e.g. "+2.4%". Coloured by `tone`. */
  delta?: string;
  hint?: string;
  tone?: "neutral" | "positive" | "negative";
}) {
  const deltaTone = {
    neutral: "text-muted bg-surface-muted border-hairline-strong",
    positive: "text-emerald-300 bg-emerald-500/10 border-emerald-500/25",
    negative: "text-rose-300 bg-rose-500/10 border-rose-500/25",
  }[tone];

  return (
    <div>
      <p className="label">{label}</p>
      <div className="mt-2 flex flex-wrap items-baseline gap-2">
        <span className="metric text-2xl font-bold text-white">{value}</span>
        {delta && (
          <span
            className={clsx(
              "rounded-md border px-1.5 py-0.5 font-mono text-xs font-medium",
              deltaTone,
            )}
          >
            {delta}
          </span>
        )}
      </div>
      {hint && <p className="mt-1.5 text-xs text-subtle">{hint}</p>}
    </div>
  );
}

/** Section heading used above a group of cards. */
export function SectionTitle({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        <h2 className="font-display text-lg font-bold tracking-tight text-white">
          {title}
        </h2>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
