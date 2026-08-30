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
        badge: "bg-red-100 text-red-700 border-red-200",
        panel: "bg-red-50 border-red-300",
        text: "text-red-800",
      };
    case "warn":
      return {
        badge: "bg-amber-100 text-amber-800 border-amber-200",
        panel: "bg-amber-50 border-amber-300",
        text: "text-amber-900",
      };
    default:
      return {
        badge: "bg-sky-100 text-sky-700 border-sky-200",
        panel: "bg-sky-50 border-sky-300",
        text: "text-sky-900",
      };
  }
}
