"use client";

// ─── Page-level error boundary ────────────────────────────────────────────────
// Next.js App Router special file — automatically wraps every page inside the
// (app) route group. Receives `error` and `reset` from Next.js.
//
// Must be a Client Component ("use client" directive is required).
// The component MUST be a default export — Next.js discovers it by convention.

import Link from "next/link";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ErrorPageProps {
  /** The error that was thrown. Next.js may attach a `digest` for server errors. */
  error: Error & { digest?: string };
  /** Calling this function attempts to re-render the segment that errored. */
  reset: () => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  return (
    <main className="flex flex-col items-center justify-center flex-1 p-8">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 max-w-md w-full text-center space-y-4">
        {/* Icon */}
        <div className="mx-auto w-12 h-12 rounded-full bg-red-50 flex items-center justify-center">
          <svg
            className="w-6 h-6 text-red-500"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
            />
          </svg>
        </div>

        {/* Heading */}
        <h1 className="text-lg font-semibold text-gray-900">
          Something went wrong
        </h1>

        {/* Error detail — development only */}
        {process.env.NODE_ENV === "development" && (
          <p className="text-xs text-left font-mono text-red-600 bg-red-50 rounded-lg p-3 break-words">
            {error.message}
            {error.digest != null && (
              <span className="block mt-1 text-gray-400">
                digest: {error.digest}
              </span>
            )}
          </p>
        )}

        {/* User-facing description */}
        <p className="text-sm text-gray-500">
          An unexpected error occurred while loading this page. You can try
          again or return to the dashboard.
        </p>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-accent-500 hover:bg-accent-400 active:bg-accent-600 text-white text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
          >
            Try again
          </button>

          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center px-4 py-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2"
          >
            Return to Dashboard
          </Link>
        </div>
      </div>
    </main>
  );
}
