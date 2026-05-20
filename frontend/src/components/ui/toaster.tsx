"use client";

// ─── Toaster ─────────────────────────────────────────────────────────────────
// Thin wrapper around sonner's <Toaster /> that applies Central Intelligence brand defaults.
// Mount once in the root Providers component so toasts are globally available.

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="top-right"
      toastOptions={{
        style: {
          fontFamily: "inherit",
          borderRadius: "0.75rem",
          border: "1px solid rgb(229 231 235)", // gray-200
          boxShadow:
            "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
        },
        className: "text-sm",
      }}
      closeButton
      richColors
    />
  );
}
