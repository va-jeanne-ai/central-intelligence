"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import type { User as SupabaseUser } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";
import { apiClient } from "@/lib/api-client";
import {
  clearCachedUser,
  readCachedUser,
  writeCachedUser,
} from "@/lib/auth-cache";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MockUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

type AuthUser = MockUser | SupabaseUser | null;

export interface AuthContextType {
  user: AuthUser;
  isLoading: boolean;
  isMockMode: boolean;
  signIn: (email: string, password: string) => Promise<{ error?: string }>;
  signOut: () => Promise<void>;
  resetPassword: (email: string) => Promise<{ error?: string }>;
  updatePassword: (newPassword: string) => Promise<{ error?: string }>;
}

// ─── Context ──────────────────────────────────────────────────────────────────

export const AuthContext = createContext<AuthContextType | null>(null);

// ─── Mock user constant ───────────────────────────────────────────────────────

const MOCK_USER: MockUser = {
  id: "mock-user-id",
  email: "admin@centralintelligence.ai",
  name: "Jade Doe",
  role: "admin",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function isMockConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return !url || !key;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const mockMode = isMockConfigured();

  // Initial state must match between SSR (no localStorage) and the first
  // client render — otherwise Next.js throws a hydration mismatch. So we
  // start with user=null and re-hydrate from the cache in a useLayoutEffect
  // below (runs synchronously after the first commit, before paint). That
  // keeps SSR/CSR markup identical AND still avoids the visible flash for
  // the sidebar avatar / name.
  // isLoading stays TRUE until the apiClient also has a valid access token:
  // consumers gate API calls on isLoading, and firing fetches before the
  // token lands would 401 every cold nav.
  // Cache is identity-only (no tokens) and self-evicts on expiry. See
  // lib/auth-cache.ts.
  const [user, setUser] = useState<AuthUser>(null);
  const [isLoading, setIsLoading] = useState(true);

  // ── Initialisation ─────────────────────────────────────────────────────────

  useEffect(() => {
    if (mockMode) {
      // Auto-sign-in with mock user so the app is always usable without creds.
      setUser(MOCK_USER);
      setIsLoading(false);
      return;
    }

    const supabase = createClient();
    if (!supabase) {
      setIsLoading(false);
      return;
    }

    // Step 1: paint a cached user identity immediately (no Authorization
    // header yet — that's why isLoading stays true). This runs in the same
    // tick as the first client commit, so the sidebar avatar fills in
    // before paint instead of flashing through an empty state. SSR rendered
    // user=null, this useEffect-time setUser keeps the SSR/CSR markup in
    // agreement (no hydration mismatch).
    const cached = readCachedUser();
    if (cached) {
      setUser(cached as AuthUser);
    }

    // Step 2: hydrate the real session from cookies.
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      if (session?.access_token) {
        apiClient.setToken(session.access_token);
      }
      if (session?.user) {
        writeCachedUser(session.user, session);
      } else {
        // No live session — drop any stale cache (e.g. user signed out in
        // another tab, refresh token expired).
        clearCachedUser();
      }
      setIsLoading(false);
    });

    // Keep in sync with Supabase auth state changes (login, logout, refresh).
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      if (session?.access_token) {
        apiClient.setToken(session.access_token);
      } else {
        apiClient.clearToken();
      }
      // Mirror the cache against the live session for SIGNED_IN,
      // TOKEN_REFRESHED, USER_UPDATED (fresh write) and SIGNED_OUT (clear).
      if (session?.user) {
        writeCachedUser(session.user, session);
      } else {
        clearCachedUser();
      }
    });

    // Token-refresh hook for the api-client. Called when a request 401s; we
    // ask Supabase for a fresh session (auto-refreshes the access token if
    // the refresh token is still valid) and hand the new access_token back
    // so the api-client can retry once before bouncing the user to /login.
    apiClient.setRefresher(async () => {
      const { data } = await supabase.auth.getSession();
      return data.session?.access_token ?? null;
    });

    return () => {
      subscription.unsubscribe();
      apiClient.setRefresher(null);
    };
  }, [mockMode]);

  // ── signIn ─────────────────────────────────────────────────────────────────

  const signIn = useCallback(
    async (email: string, password: string): Promise<{ error?: string }> => {
      if (mockMode) {
        // Simulate a brief network round-trip.
        await delay(500);
        setUser(MOCK_USER);
        return {};
      }

      const supabase = createClient();
      if (!supabase) return { error: "Auth not configured" };

      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        return { error: error.message };
      }

      return {};
    },
    [mockMode],
  );

  // ── signOut ────────────────────────────────────────────────────────────────

  const signOut = useCallback(async (): Promise<void> => {
    if (mockMode) {
      setUser(null);
      router.push("/login");
      return;
    }

    // Best-effort server-side sign-out. If the session is already invalid
    // (expired JWT / missing user), supabase.auth.signOut() can throw or
    // hang — that must NOT block the local logout. Always fall through to
    // clearing local state + redirecting so the button works regardless.
    try {
      const supabase = createClient();
      if (supabase) {
        await supabase.auth.signOut();
      }
    } catch (err) {
      // Already-invalid session — nothing to revoke server-side. Proceed.
      console.warn("supabase.auth.signOut() failed; clearing local session anyway", err);
    }

    apiClient.clearToken();
    clearCachedUser();
    setUser(null);
    router.push("/login");
  }, [mockMode, router]);

  // ── resetPassword ──────────────────────────────────────────────────────────

  const resetPassword = useCallback(
    async (_email: string): Promise<{ error?: string }> => {
      if (mockMode) {
        await delay(500);
        return {};
      }

      const supabase = createClient();
      if (!supabase) return { error: "Auth not configured" };

      // Send the user to /reset-password after they click the email link.
      // Without `redirectTo`, Supabase falls back to the project's Site URL
      // (configured in Supabase Dashboard), which may not match where we
      // actually want to receive and consume the recovery token.
      const { error } = await supabase.auth.resetPasswordForEmail(_email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });

      if (error) {
        return { error: error.message };
      }

      return {};
    },
    [mockMode],
  );

  // ── updatePassword ─────────────────────────────────────────────────────────
  // Called from /reset-password after the user follows their recovery link.
  // The Supabase client (createBrowserClient with detectSessionInUrl on by
  // default) consumes the recovery token from window.location.hash, sets a
  // PASSWORD_RECOVERY session, and updateUser then changes the password.
  const updatePassword = useCallback(
    async (newPassword: string): Promise<{ error?: string }> => {
      if (mockMode) {
        await delay(500);
        return {};
      }

      const supabase = createClient();
      if (!supabase) return { error: "Auth not configured" };

      const { error } = await supabase.auth.updateUser({ password: newPassword });

      if (error) {
        return { error: error.message };
      }

      return {};
    },
    [mockMode],
  );

  // ── Value ──────────────────────────────────────────────────────────────────

  const value: AuthContextType = {
    user,
    isLoading,
    isMockMode: mockMode,
    signIn,
    signOut,
    resetPassword,
    updatePassword,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
