/**
 * Lightweight localStorage cache of the authenticated user's identity.
 *
 * This is a UX optimisation — NOT an auth source-of-truth. The Supabase
 * session itself stays in cookies (managed by @supabase/ssr); the
 * middleware enforces session validity on every protected route. The
 * cache exists so the React tree can mount with `user` already populated
 * and `isLoading=false`, eliminating the "loading…" flash that fires
 * while supabase.auth.getSession() round-trips on every navigation.
 *
 * Security: we cache only public identity (id/email/name/role) and the
 * session expiry timestamp. Tokens are never written here.
 */

import type { Session, User as SupabaseUser } from "@supabase/supabase-js";

const CACHE_KEY = "ci.auth.user.v1";

export interface CachedUser {
  id: string;
  email: string;
  name: string;
  role: string;
  /** Unix seconds. Mirrors session.expires_at. */
  expires_at: number;
}

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function deriveName(user: SupabaseUser): string {
  const meta = user.user_metadata ?? {};
  return (
    (meta.full_name as string | undefined) ??
    (meta.name as string | undefined) ??
    ""
  );
}

function deriveRole(user: SupabaseUser): string {
  const app = user.app_metadata ?? {};
  return (app.role as string | undefined) ?? "user";
}

/**
 * Read the cached user. Returns null on SSR, missing/corrupt entries, or
 * when the session expiry has passed. Expired entries are evicted in-place
 * so subsequent reads don't keep finding-and-discarding them.
 */
export function readCachedUser(): CachedUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CachedUser>;
    if (
      typeof parsed.id !== "string" ||
      typeof parsed.email !== "string" ||
      typeof parsed.name !== "string" ||
      typeof parsed.role !== "string" ||
      typeof parsed.expires_at !== "number"
    ) {
      window.localStorage.removeItem(CACHE_KEY);
      return null;
    }
    if (parsed.expires_at <= nowSeconds()) {
      window.localStorage.removeItem(CACHE_KEY);
      return null;
    }
    return parsed as CachedUser;
  } catch {
    return null;
  }
}

/**
 * Persist the user identity derived from a fresh Supabase session.
 * Wrapped in try/catch — localStorage can throw under quota pressure,
 * private-browsing modes, or some embedded webviews.
 */
export function writeCachedUser(user: SupabaseUser, session: Session): void {
  if (typeof window === "undefined") return;
  try {
    const value: CachedUser = {
      id: user.id,
      email: user.email ?? "",
      name: deriveName(user),
      role: deriveRole(user),
      expires_at: session.expires_at ?? 0,
    };
    window.localStorage.setItem(CACHE_KEY, JSON.stringify(value));
  } catch {
    // ignore — cache is a nice-to-have
  }
}

export function clearCachedUser(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(CACHE_KEY);
  } catch {
    // ignore
  }
}
