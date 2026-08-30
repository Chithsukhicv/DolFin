"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { clearUserId, getUserId } from "@/lib/session";

/**
 * Validates the cached localStorage user ID against the backend on every
 * page change. If the user no longer exists (e.g. the dev DB was wiped),
 * the cache is cleared and the visitor is sent back to onboarding.
 */
export function AuthGuard() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const id = getUserId();
    if (!id) return; // not logged in, nothing to validate

    let cancelled = false;
    api
      .get(`/users/${id}`)
      .catch(() => {
        if (cancelled) return;
        clearUserId();
        // Skip the redirect when we're already on the landing page.
        if (pathname !== "/") router.replace("/");
      });

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  return null;
}
