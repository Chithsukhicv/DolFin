// Client-side session. A localStorage stub standing in for real auth.
//
// Exposed as a subscribable store rather than a bare getter so React can read
// it with useSyncExternalStore. Every page previously did
// `useEffect(() => setUserId(getUserId()))`, which triggers a cascading render
// on load and is flagged by react-hooks/set-state-in-effect.

const KEY = "dolfin.user.id";

const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

export function getUserId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY);
}

export function setUserId(id: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, id);
  emit();
}

export function clearUserId() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
  emit();
}

/** Subscribe to session changes, including from other browser tabs. */
export function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** Server snapshot: there is no session during SSR. */
export function getServerUserId(): null {
  return null;
}
