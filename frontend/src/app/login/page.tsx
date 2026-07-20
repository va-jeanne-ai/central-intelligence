'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff } from 'lucide-react';
import { useAuth } from '@/hooks/use-auth';
import { useBranding } from '@/hooks/use-branding';

// ─── Types ────────────────────────────────────────────────────────────────────

interface FormState {
  email: string;
  password: string;
  showPassword: boolean;
  rememberMe: boolean;
  error: string | null;
  attempts: number;
  isLoading: boolean;
  resetMessage: string | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const MAX_ATTEMPTS = 5;

// ─── Spinner ─────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4 text-white"
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

// ─── Attempt Dots ─────────────────────────────────────────────────────────────

function AttemptDots({ remaining }: { remaining: number }) {
  const used = MAX_ATTEMPTS - remaining;

  return (
    <div className="flex items-center gap-1.5 mt-2.5 mb-2">
      {Array.from({ length: MAX_ATTEMPTS }).map((_, i) => (
        <span
          key={i}
          className="rounded-full inline-block"
          style={{
            width: '8px',
            height: '8px',
            background: i < used ? '#EF4444' : '#D1D5DB',
          }}
          aria-hidden="true"
        />
      ))}
      <span
        className="ml-0.5"
        style={{ fontSize: '11.5px', color: '#6B7280' }}
      >
        {remaining} of {MAX_ATTEMPTS} attempts remaining
      </span>
    </div>
  );
}

// ─── Error Banner ─────────────────────────────────────────────────────────────

function ErrorBanner({ remaining }: { remaining: number }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded"
      style={{
        background: '#FEF2F2',
        border: '1px solid #FECACA',
        borderRadius: '6px',
        padding: '11px 14px',
        marginBottom: '20px',
      }}
    >
      <span
        aria-hidden="true"
        style={{ fontSize: '15px', flexShrink: 0, marginTop: '1px' }}
      >
        ⚠️
      </span>
      <div style={{ fontSize: '13px', color: '#991B1B', lineHeight: '1.45' }}>
        <strong
          style={{ fontWeight: 700, display: 'block', marginBottom: '1px' }}
        >
          Invalid email or password.
        </strong>
        Please check your credentials and try again.
        <AttemptDots remaining={remaining} />
      </div>
    </div>
  );
}

// ─── Login Page ───────────────────────────────────────────────────────────────

export default function LoginPage() {
  const router = useRouter();
  const { signIn, resetPassword } = useAuth();
  const { branding } = useBranding();

  const [form, setForm] = useState<FormState>({
    email: '',
    password: '',
    showPassword: false,
    rememberMe: false,
    error: null,
    attempts: MAX_ATTEMPTS,
    isLoading: false,
    resetMessage: null,
  });

  const hasError = form.error !== null;

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (form.isLoading || form.attempts <= 0) return;

    // Client-side validation — gives visible error states even in mock mode
    if (!form.email.includes('@')) {
      setForm((prev) => ({
        ...prev,
        error: 'Please enter a valid email address.',
        attempts: Math.max(0, prev.attempts - 1),
      }));
      return;
    }
    if (form.password.length < 6) {
      setForm((prev) => ({
        ...prev,
        error: 'Password must be at least 6 characters.',
        attempts: Math.max(0, prev.attempts - 1),
      }));
      return;
    }

    setField('isLoading', true);

    const { error } = await signIn(form.email, form.password);

    if (error) {
      setForm((prev) => ({
        ...prev,
        isLoading: false,
        error,
        attempts: Math.max(0, prev.attempts - 1),
      }));
    } else {
      router.push('/dashboard');
    }
  }

  // ── Input shared style helpers ────────────────────────────────────────────

  const inputBase: React.CSSProperties = {
    width: '100%',
    padding: '10px 14px',
    border: `1.5px solid ${hasError ? '#EF4444' : '#E5E7EB'}`,
    borderRadius: '6px',
    fontSize: '13.5px',
    color: '#1F2937',
    background: hasError ? '#FFF5F5' : '#F9FAFB',
    outline: 'none',
    fontFamily: 'inherit',
    transition: 'border-color 0.15s, box-shadow 0.15s',
  };

  const inputWithIcon: React.CSSProperties = {
    ...inputBase,
    paddingRight: '40px',
  };

  // ── Focus handlers — applied via onFocus / onBlur ─────────────────────────

  function handleFocus(e: React.FocusEvent<HTMLInputElement>) {
    if (hasError) {
      e.currentTarget.style.borderColor = '#EF4444';
      e.currentTarget.style.boxShadow = '0 0 0 3px rgba(239,68,68,.12)';
      e.currentTarget.style.background = '#FFF5F5';
    } else {
      e.currentTarget.style.borderColor = '#F59E0B';
      e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,.12)';
      e.currentTarget.style.background = '#FFFFFF';
    }
  }

  function handleBlur(e: React.FocusEvent<HTMLInputElement>) {
    e.currentTarget.style.borderColor = hasError ? '#EF4444' : '#E5E7EB';
    e.currentTarget.style.boxShadow = 'none';
    e.currentTarget.style.background = hasError ? '#FFF5F5' : '#F9FAFB';
  }

  return (
    /*
     * Full-page dark background with subtle radial gold shimmer.
     * The ::before overlay is done via a positioned child div since
     * Tailwind pseudo-elements need arbitrary values — a child div is cleaner.
     */
    <div
      className="relative min-h-screen flex items-center justify-center overflow-hidden"
      style={{ background: '#1F2937' }}
    >
      {/* Radial gold shimmer overlay */}
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            'radial-gradient(circle at 20% 35%, rgba(99,102,241,.07) 0%, transparent 50%), radial-gradient(circle at 80% 65%, rgba(99,102,241,.05) 0%, transparent 45%)',
        }}
      />

      {/* Card + footer wrapper */}
      <div className="relative z-10 flex flex-col items-center">

        {/* ── Login Card ──────────────────────────────────────────────────── */}
        <div
          style={{
            background: '#FFFFFF',
            borderRadius: '16px',
            boxShadow: '0 20px 40px rgba(0,0,0,.3), 0 0 0 1px rgba(0,0,0,.06)',
            width: '420px',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: '36px 36px 28px' }}>

            {/* ── Logo block ──────────────────────────────────────────────── */}
            <div
              className="flex flex-col items-center"
              style={{ marginBottom: '28px' }}
            >
              {/* Logo — instance logo image if configured, else brain icon */}
              {branding.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element -- external, instance-configured URL
                <img
                  src={branding.logo_url}
                  alt={branding.app_name}
                  style={{
                    width: '52px',
                    height: '52px',
                    borderRadius: '14px',
                    objectFit: 'cover',
                    boxShadow: '0 4px 12px rgba(99,102,241,.35)',
                    marginBottom: '12px',
                  }}
                />
              ) : (
                <div
                  aria-hidden="true"
                  style={{
                    width: '52px',
                    height: '52px',
                    borderRadius: '14px',
                    background:
                      'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '26px',
                    boxShadow: '0 4px 12px rgba(99,102,241,.35)',
                    marginBottom: '12px',
                  }}
                >
                  🧠
                </div>
              )}

              {/* App name */}
              <span
                style={{
                  fontSize: '22px',
                  fontWeight: 800,
                  color: '#111827',
                  letterSpacing: '-0.03em',
                }}
              >
                {branding.app_name}
              </span>

              {/* Subtitle */}
              {branding.tagline && (
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    color: '#9CA3AF',
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    marginTop: '2px',
                  }}
                >
                  {branding.tagline}
                </span>
              )}
            </div>

            {/* ── Heading ─────────────────────────────────────────────────── */}
            <h1
              style={{
                fontSize: '16px',
                fontWeight: 700,
                color: '#1F2937',
                textAlign: 'center',
                marginBottom: '24px',
                margin: '0 0 24px',
              }}
            >
              Sign in to your account
            </h1>

            {/* ── Form ────────────────────────────────────────────────────── */}
            <form onSubmit={handleSubmit} noValidate>

              {/* Error banner — shown on failed attempt */}
              {hasError && <ErrorBanner remaining={form.attempts} />}

              {/* Email field */}
              <div style={{ marginBottom: '16px' }}>
                <label
                  htmlFor="login-email"
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 700,
                    color: '#374151',
                    marginBottom: '6px',
                    letterSpacing: '0.01em',
                  }}
                >
                  Email address
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    id="login-email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@company.com"
                    value={form.email}
                    onChange={(e) => setField('email', e.target.value)}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    style={inputBase}
                    aria-invalid={hasError}
                    aria-describedby={hasError ? 'login-error' : undefined}
                    required
                  />
                </div>
              </div>

              {/* Password field */}
              <div style={{ marginBottom: '16px' }}>
                <label
                  htmlFor="login-password"
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 700,
                    color: '#374151',
                    marginBottom: '6px',
                    letterSpacing: '0.01em',
                  }}
                >
                  Password
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    id="login-password"
                    type={form.showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    placeholder="••••••••••"
                    value={form.password}
                    onChange={(e) => setField('password', e.target.value)}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    style={inputWithIcon}
                    aria-invalid={hasError}
                    required
                  />
                  {/* Show/hide toggle */}
                  <button
                    type="button"
                    onClick={() =>
                      setField('showPassword', !form.showPassword)
                    }
                    aria-label={
                      form.showPassword ? 'Hide password' : 'Show password'
                    }
                    style={{
                      position: 'absolute',
                      right: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: '#9CA3AF',
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                    tabIndex={0}
                  >
                    {form.showPassword ? (
                      <EyeOff size={15} aria-hidden="true" />
                    ) : (
                      <Eye size={15} aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>

              {/* Remember me / Forgot password row */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '22px',
                  marginTop: '4px',
                }}
              >
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '7px',
                    fontSize: '12.5px',
                    color: '#4B5563',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={form.rememberMe}
                    onChange={(e) => setField('rememberMe', e.target.checked)}
                    style={{
                      width: '14px',
                      height: '14px',
                      accentColor: '#F59E0B',
                      cursor: 'pointer',
                    }}
                  />
                  Remember me
                </label>

                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    if (!form.email.includes('@')) {
                      setField('resetMessage', 'Enter your email above first.');
                      return;
                    }
                    setField('resetMessage', null);
                    resetPassword(form.email).then(({ error }) => {
                      if (error) {
                        setField('resetMessage', error);
                      } else {
                        setField('resetMessage', 'Reset link sent to ' + form.email + '!');
                      }
                    });
                  }}
                  style={{
                    fontSize: '12.5px',
                    color: '#9CA3AF',
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    cursor: 'pointer',
                  }}
                >
                  Forgot password?
                </button>
              </div>

              {/* Reset password message */}
              {form.resetMessage && (
                <p
                  style={{
                    fontSize: '12px',
                    color: form.resetMessage.includes('sent') ? '#10B981' : '#9CA3AF',
                    marginBottom: '12px',
                    marginTop: '-12px',
                    textAlign: 'right',
                  }}
                >
                  {form.resetMessage}
                </p>
              )}

              {/* Sign In button */}
              <SignInButton isLoading={form.isLoading} />
            </form>
          </div>
        </div>

        {/* ── Powered-by footer ────────────────────────────────────────── */}
        <p
          style={{
            fontSize: '11.5px',
            color: '#6B7280',
            marginTop: '20px',
            letterSpacing: '0.02em',
          }}
        >
          Powered by{' '}
          <strong style={{ color: '#F59E0B', fontWeight: 700 }}>
            {branding.app_name}
          </strong>
        </p>
      </div>
    </div>
  );
}

// ─── Sign In Button ───────────────────────────────────────────────────────────
// Extracted to manage hover state cleanly without Tailwind group hacks.

function SignInButton({ isLoading }: { isLoading: boolean }) {
  const [hovered, setHovered] = useState(false);

  const baseStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    width: '100%',
    padding: '12px 20px',
    borderRadius: '6px',
    border: 'none',
    fontSize: '14px',
    fontWeight: 700,
    color: '#FFFFFF',
    background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
    cursor: isLoading ? 'not-allowed' : 'pointer',
    boxShadow: hovered && !isLoading
      ? '0 4px 14px rgba(99,102,241,.4)'
      : '0 2px 8px rgba(99,102,241,.3)',
    transition: 'opacity 0.15s, transform 0.1s, box-shadow 0.15s',
    fontFamily: 'inherit',
    opacity: hovered && !isLoading ? 0.93 : 1,
    transform: hovered && !isLoading ? 'translateY(-1px)' : 'translateY(0)',
  };

  return (
    <button
      type="submit"
      disabled={isLoading}
      style={baseStyle}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-busy={isLoading}
    >
      {isLoading ? (
        <>
          <Spinner />
          <span>Signing in...</span>
        </>
      ) : (
        <>
          <span aria-hidden="true">🧠</span>
          <span>Sign In</span>
        </>
      )}
    </button>
  );
}
