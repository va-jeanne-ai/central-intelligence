"use client";

// ─── ErrorBoundary ────────────────────────────────────────────────────────────
// React class component that catches render errors in its subtree.
// Hooks cannot catch render errors, so a class component is required (React 18).
//
// Usage:
//   <ErrorBoundary fallback={<p>Custom fallback</p>}>
//     <SomePage />
//   </ErrorBoundary>

import { Component, type ReactNode, type ErrorInfo } from "react";
import Link from "next/link";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Props {
  /** Content to render when no error has occurred. */
  children: ReactNode;
  /**
   * Optional custom fallback rendered instead of the default error card.
   * Receives no props — if you need access to the error or reset callback,
   * use the `onError` prop to handle it externally.
   */
  fallback?: ReactNode;
  /** Called after an error is caught, before the fallback is rendered. */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

// ─── Component ────────────────────────────────────────────────────────────────

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.props.onError?.(error, errorInfo);
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    // Render the consumer-supplied fallback if provided.
    if (this.props.fallback != null) {
      return this.props.fallback;
    }

    // Default error card.
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] p-8">
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
          <h2 className="text-lg font-semibold text-gray-900">
            Something went wrong
          </h2>

          {/* Error detail — dev mode only */}
          {process.env.NODE_ENV === "development" &&
            this.state.error != null && (
              <p className="text-xs text-left font-mono text-red-600 bg-red-50 rounded-lg p-3 break-words">
                {this.state.error.message}
              </p>
            )}

          {/* Description */}
          <p className="text-sm text-gray-500">
            An unexpected error occurred. You can try again or return to the
            dashboard.
          </p>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
            <button
              type="button"
              onClick={this.handleReset}
              className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-indigo-500 hover:bg-indigo-400 active:bg-indigo-600 text-white text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
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
      </div>
    );
  }
}
