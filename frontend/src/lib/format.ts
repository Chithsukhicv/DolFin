// Helpers for currency, percentage, and severity styling.

export function rupees(n: number): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "₹0";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: n >= 100 ? 0 : 2,
  }).format(n);
}

export function pct(n: number, fractionDigits = 2): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "0%";
  return `${n.toFixed(fractionDigits)}%`;
}

export function severityClasses(sev: "info" | "warn" | "critical"): {
  badge: string;
  panel: string;
  text: string;
} {
  switch (sev) {
    case "critical":
      return {
        badge: "bg-rose-500/20 text-rose-300 border-rose-500/30",
        panel: "bg-rose-500/[0.07] border-rose-500/25",
        text: "text-rose-200",
      };
    case "warn":
      return {
        badge: "bg-amber-500/20 text-amber-300 border-amber-500/30",
        panel: "bg-amber-500/[0.07] border-amber-500/25",
        text: "text-amber-200",
      };
    default:
      return {
        badge: "bg-blue-500/20 text-blue-300 border-blue-500/30",
        panel: "bg-blue-500/[0.07] border-blue-500/25",
        text: "text-blue-200",
      };
  }
}
