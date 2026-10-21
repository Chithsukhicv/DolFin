import clsx from "clsx";
import { ReactNode, CSSProperties } from "react";

/**
 * Premium dark surface card.
 * Uses inline styles for the neon border/glow accents
 * so they work independently of Tailwind's purge pass.
 */
export function Card({
  children,
  className,
  interactive = false,
  sheen = true,
  as: Tag = "div",
  accent = "purple",
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  sheen?: boolean;
  as?: "div" | "section" | "article" | "li";
  accent?: "purple" | "cyan" | "green";
}) {
  const accentMap = {
    purple: {
      border: "rgb(168 85 247 / 0.2)",
      glow: "0 0 24px -8px rgb(168 85 247 / 0.12)",
      top: "linear-gradient(90deg, transparent, #A855F7, transparent)",
    },
    cyan: {
      border: "rgb(34 211 238 / 0.2)",
      glow: "0 0 24px -8px rgb(34 211 238 / 0.12)",
      top: "linear-gradient(90deg, transparent, #22D3EE, transparent)",
    },
    green: {
      border: "rgb(16 217 160 / 0.2)",
      glow: "0 0 24px -8px rgb(16 217 160 / 0.12)",
      top: "linear-gradient(90deg, transparent, #10D9A0, transparent)",
    },
  }[accent];

  const baseStyle: CSSProperties = {
    background: "rgb(11 11 27 / 0.85)",
    border: `1px solid ${accentMap.border}`,
    boxShadow: accentMap.glow,
    position: "relative",
    overflow: "hidden",
  };

  return (
    <Tag
      className={clsx(
        "rounded-2xl p-5",
        interactive && "cursor-pointer transition-transform hover:-translate-y-0.5",
        className,
      )}
      style={baseStyle}
    >
      {sheen && (
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            top: 0,
            left: 0,
            right: 0,
            height: "1px",
            background: accentMap.top,
            pointerEvents: "none",
          }}
        />
      )}
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
          <span
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl"
            style={{
              background: "rgb(168 85 247 / 0.1)",
              border: "1px solid rgb(168 85 247 / 0.2)",
              color: "#A855F7",
            }}
          >
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <h3 className="font-display text-base font-bold text-white">{title}</h3>
          {subtitle && (
            <p className="mt-0.5 text-xs leading-relaxed text-muted">{subtitle}</p>
          )}
        </div>
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

export function Stat({
  label,
  value,
  delta,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  delta?: string;
  hint?: string;
  tone?: "neutral" | "positive" | "negative";
}) {
  const deltaTone = {
    neutral: { bg: "rgb(255 255 255 / 0.05)", border: "rgb(255 255 255 / 0.1)", color: "#A1A1B5" },
    positive: { bg: "rgb(16 217 160 / 0.1)", border: "rgb(16 217 160 / 0.25)", color: "#10D9A0" },
    negative: { bg: "rgb(242 87 103 / 0.1)", border: "rgb(242 87 103 / 0.25)", color: "#F25767" },
  }[tone];

  return (
    <div>
      <p className="label">{label}</p>
      <div className="mt-2 flex flex-wrap items-baseline gap-2">
        <span className="metric text-2xl font-bold text-white">{value}</span>
        {delta && (
          <span
            className="rounded-md px-1.5 py-0.5 font-mono text-xs font-medium"
            style={{ background: deltaTone.bg, border: `1px solid ${deltaTone.border}`, color: deltaTone.color }}
          >
            {delta}
          </span>
        )}
      </div>
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

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
        <h2 className="font-display text-lg font-bold tracking-tight text-white">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
