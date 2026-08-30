"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import {
  getServerUserId,
  getUserId,
  subscribe,
} from "./session";

/**
 * Read the current user id reactively.
 *
 * `useSyncExternalStore` is the supported way to read a value that lives
 * outside React (here, localStorage). It gives a correct SSR snapshot and
 * avoids the setState-inside-useEffect pattern this app used before, which
 * caused a cascading render on every page load.
 *
 * Returns `undefined` while hydrating, `null` when signed out, and the id when
 * signed in. Distinguishing "not known yet" from "definitely signed out"
 * matters: without it every page flashes a redirect on first paint.
 */
export function useUserId(): string | null | undefined {
  const id = useSyncExternalStore(subscribe, getUserId, getServerUserId);
  const hydrated = useHydrated();
  return hydrated ? id : undefined;
}

/**
 * Require a session, redirecting to onboarding when there isn't one.
 * Returns the id, or `undefined` while it is still unknown.
 */
export function useRequireUser(): string | undefined {
  const router = useRouter();
  const id = useUserId();

  useEffect(() => {
    if (id === null) router.replace("/");
  }, [id, router]);

  return id ?? undefined;
}

/** True once the client has hydrated, so localStorage can be trusted. */
function useHydrated(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

function noopSubscribe() {
  return () => {};
}
