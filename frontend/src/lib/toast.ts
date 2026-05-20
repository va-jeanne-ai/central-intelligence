// ─── Toast utilities ──────────────────────────────────────────────────────────
// Convenience wrappers around sonner so call-sites don't import sonner directly.
// Use these throughout the app for consistent, typed toast notifications.

import { toast } from "sonner";

/** Show a success toast (green) */
export function showSuccess(message: string): void {
  toast.success(message);
}

/** Show an error toast (red) */
export function showError(message: string): void {
  toast.error(message);
}

/** Show a warning toast (amber) */
export function showWarning(message: string): void {
  toast.warning(message);
}

/** Show an informational toast (blue) */
export function showInfo(message: string): void {
  toast.info(message);
}

/** Format a raw API error response into a user-friendly error toast.
 *
 * Accepts either:
 * - A plain string message
 * - An object with an optional `message` and/or `code` field (e.g. Supabase
 *   error responses or API error payloads)
 *
 * Falls back to a generic message when nothing useful is available.
 */
export function showApiError(
  error: { code?: string; message?: string } | string
): void {
  const msg =
    typeof error === "string"
      ? error
      : error.message ?? "An unexpected error occurred";
  toast.error(msg);
}
