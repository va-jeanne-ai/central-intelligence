"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

// ─── Client-side auth guard ───────────────────────────────────────────────────
// Redirects to /login when the user becomes null mid-session (expired JWT,
// deleted user, server-side sign-out). The Next middleware only guards on
// navigation/request; this catches the case where the page is already
// rendered and the session goes invalid while sitting on it. Renders nothing.

export function AuthGuard() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Wait until auth has finished hydrating before deciding — otherwise we'd
    // bounce every first paint (user is null while loading).
    if (isLoading) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [user, isLoading, router, pathname]);

  return null;
}
