'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff } from 'lucide-react';
import { useAuth } from '@/hooks/use-auth';
import { createClient } from '@/lib/supabase/client';

// ─── Types ────────────────────────────────────────────────────────────────────

interface FormState {
  newPassword: string;
  confirmPassword: string;
  showPassword: boolean;
  error: string | null;
  success: boolean;
  isLoading: boolean;
  isReady: boolean;
  hashError: string | null;
}

// ─── Spinner ─────────────────────────────────────────────────────────────────

function Spinner({ className = "text-white" }: { className?: string }) {
  return (
    <svg
      className={`animate-spin h-4 w-4 ${className}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ResetPasswordPage() {
  const router = useRouter();
  const { updatePassword } = useAuth();

  const [form, setForm] = useState<FormState>({
    newPassword: '',
    confirmPassword: '',
    showPassword: false,
    error: null,
    success: false,
    isLoading: false,
    isReady: false,
    hashError: null,
  });

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  // ── Hash detection + session bootstrap ───────────────────────────────────
  //
  // The recovery flow lands here with a URL hash like:
  //   #access_token=...&refresh_token=...&type=recovery
  // or on error:
  //   #error=access_denied&error_code=otp_expired&...
  //
  // @supabase/ssr's createBrowserClient has detectSessionInUrl on by default,
  // so just calling getSession() once is enough — the client will read the
  // hash, exchange it for a PASSWORD_RECOVERY session, and strip the hash.
  //
  // We also need to parse error params ourselves so we can show a helpful
  // message instead of just appearing blank.
  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (typeof window === 'undefined') return;

      // First check for an error in the hash — Supabase puts these here when
      // the token is expired, already-used, or otherwise invalid.
      const hash = window.location.hash.startsWith('#')
        ? window.location.hash.slice(1)
        : window.location.hash;
      const hashParams = new URLSearchParams(hash);
      const errorCode = hashParams.get('error_code');
      const errorDescription = hashParams.get('error_description');

      if (errorCode) {
        if (!cancelled) {
          setField(
            'hashError',
            errorDescription?.replaceAll('+', ' ') ??
              'This password-reset link is no longer valid.',
          );
        }
        return;
      }

      // No error — try to read the session the Supabase client should have
      // just bootstrapped from the hash.
      const supabase = createClient();
      if (!supabase) {
        if (!cancelled) {
          setField('hashError', 'Auth not configured. Cannot reset password.');
        }
        return;
      }

      const { data, error } = await supabase.auth.getSession();
      if (cancelled) return;

      if (error) {
        setField('hashError', error.message);
        return;
      }

      if (!data.session) {
        setField(
          'hashError',
          'No recovery session found. The link may have already been used. Request a new reset email and try again.',
        );
        return;
      }

      // Session is live; we're good to show the form.
      setField('isReady', true);
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Submit ───────────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setField('error', null);

    if (form.newPassword.length < 8) {
      setField('error', 'Password must be at least 8 characters.');
      return;
    }
    if (form.newPassword !== form.confirmPassword) {
      setField('error', 'Passwords do not match.');
      return;
    }

    setField('isLoading', true);
    const { error } = await updatePassword(form.newPassword);
    setField('isLoading', false);

    if (error) {
      setField('error', error);
      return;
    }

    setField('success', true);
    // Give the user a moment to read the success message, then send them home.
    setTimeout(() => router.push('/login'), 1500);
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">
          Set a new password
        </h1>
        <p className="text-sm text-gray-500 mb-6">
          Enter your new password below. You&apos;ll be signed in once it&apos;s
          saved.
        </p>

        {/* Hash-level error: link expired, already-used, etc. */}
        {form.hashError && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3">
            <p className="text-sm text-red-700 font-medium mb-1">
              Reset link no longer valid
            </p>
            <p className="text-xs text-red-600">{form.hashError}</p>
            <button
              onClick={() => router.push('/login')}
              className="mt-3 text-xs text-red-700 underline"
            >
              Back to login →
            </button>
          </div>
        )}

        {/* Success state */}
        {form.success && (
          <div className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3">
            <p className="text-sm text-green-700 font-medium">
              Password updated. Redirecting to login…
            </p>
          </div>
        )}

        {/* Form — only shown when ready (session bootstrapped from hash) */}
        {form.isReady && !form.success && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="newPassword"
                className="block text-sm font-medium text-gray-700 mb-1.5"
              >
                New password
              </label>
              <div className="relative">
                <input
                  id="newPassword"
                  name="newPassword"
                  type={form.showPassword ? 'text' : 'password'}
                  required
                  autoComplete="new-password"
                  value={form.newPassword}
                  onChange={(e) => setField('newPassword', e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 pr-10 text-sm text-gray-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                  placeholder="At least 8 characters"
                />
                <button
                  type="button"
                  onClick={() => setField('showPassword', !form.showPassword)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600"
                  aria-label={
                    form.showPassword ? 'Hide password' : 'Show password'
                  }
                >
                  {form.showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-medium text-gray-700 mb-1.5"
              >
                Confirm new password
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type={form.showPassword ? 'text' : 'password'}
                required
                autoComplete="new-password"
                value={form.confirmPassword}
                onChange={(e) => setField('confirmPassword', e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                placeholder="Re-enter the same password"
              />
            </div>

            {form.error && (
              <p className="text-xs text-red-600">{form.error}</p>
            )}

            <button
              type="submit"
              disabled={form.isLoading}
              className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {form.isLoading ? (
                <>
                  <Spinner />
                  Updating…
                </>
              ) : (
                'Update password'
              )}
            </button>
          </form>
        )}

        {/* Loading state — between mount and hash detection completing */}
        {!form.isReady && !form.hashError && !form.success && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner className="text-gray-500" />
            <span>Validating reset link…</span>
          </div>
        )}
      </div>
    </main>
  );
}
