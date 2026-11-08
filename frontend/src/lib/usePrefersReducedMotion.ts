/**
 * usePrefersReducedMotion
 *
 * Subscribes to the (prefers-reduced-motion: reduce) media query using
 * useSyncExternalStore — the same pattern used for session state. This avoids
 * calling setState synchronously inside a useEffect (react-hooks/exhaustive-deps
 * / react-hooks/no-direct-set-state-in-use-effect), which triggers a cascading
 * render and an ESLint error under the Next.js ruleset.
 *
 * Returns true when the user has requested reduced motion.
 * Returns false on the server (SSR snapshot) so scenes render with motion on
 * first paint and only suppress animation if the user actually opted out.
 */
import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function getSnapshot(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia(QUERY).matches;
}

function getServerSnapshot(): boolean {
  return false;
}

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
