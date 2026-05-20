"use client";

// ─── ConfirmDialog ────────────────────────────────────────────────────────────
// Modal confirm dialog for destructive / warning actions.
// No external dependencies — pure Tailwind + React.

import { useEffect, useRef } from "react";

type Variant = "danger" | "warning" | "default";

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: Variant;
  loading?: boolean;
}

// ─── Style maps ───────────────────────────────────────────────────────────────

const VARIANT_ICON: Record<Variant, string> = {
  danger: "🗑️",
  warning: "⚠️",
  default: "❓",
};

const CONFIRM_BUTTON_STYLE: Record<Variant, string> = {
  danger:
    "bg-red-600 hover:bg-red-700 active:bg-red-800 focus-visible:ring-red-500 text-white",
  warning:
    "bg-amber-500 hover:bg-amber-600 active:bg-amber-700 focus-visible:ring-amber-500 text-white",
  default:
    "bg-gray-700 hover:bg-gray-800 active:bg-gray-900 focus-visible:ring-gray-500 text-white",
};

// ─── Spinner ──────────────────────────────────────────────────────────────────

function ButtonSpinner() {
  return (
    <span
      className="inline-block w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin mr-1.5"
      aria-hidden="true"
    />
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  loading = false,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Focus trap + ESC key handler
  useEffect(() => {
    if (!open) return;

    // Move focus to Cancel button on open
    const frame = requestAnimationFrame(() => {
      cancelRef.current?.focus();
    });

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }

      // Tab trap
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      role="presentation"
      onClick={(e) => {
        // Close when clicking directly on the backdrop (not the dialog card)
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Dialog card */}
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby={description ? "confirm-dialog-description" : undefined}
        className="bg-white rounded-xl shadow-xl max-w-sm w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Icon */}
        <span
          className="text-2xl leading-none select-none"
          role="img"
          aria-hidden="true"
        >
          {VARIANT_ICON[variant]}
        </span>

        {/* Title */}
        <h2
          id="confirm-dialog-title"
          className="text-sm font-bold text-gray-900 mt-3"
        >
          {title}
        </h2>

        {/* Description */}
        {description && (
          <p
            id="confirm-dialog-description"
            className="text-xs text-gray-500 mt-1"
          >
            {description}
          </p>
        )}

        {/* Button row */}
        <div className="flex justify-end gap-2 mt-5">
          {/* Cancel */}
          <button
            ref={cancelRef}
            type="button"
            onClick={onClose}
            disabled={loading}
            className="
              inline-flex items-center justify-center
              px-4 py-2 rounded-lg border border-gray-300
              text-xs font-semibold text-gray-700
              bg-white hover:bg-gray-50 active:bg-gray-100
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors duration-150
              focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2
            "
          >
            {cancelLabel}
          </button>

          {/* Confirm */}
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`
              inline-flex items-center justify-center
              px-4 py-2 rounded-lg
              text-xs font-semibold
              disabled:opacity-60 disabled:cursor-not-allowed
              transition-colors duration-150
              focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2
              ${CONFIRM_BUTTON_STYLE[variant]}
            `}
          >
            {loading && <ButtonSpinner />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
