"use client";

// "What's new" hub: lists the current release's features; "Show me"
// navigates to the feature's page and hands the tour id to TourProvider via
// sessionStorage (no cross-page tour choreography). Custom modal per the
// project's no-native-dialogs rule; ESC and backdrop-click close it.

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { SparkleIcon } from "@/components/ui/sparkle-icon";
import { PENDING_TOUR_KEY } from "@/lib/tour-logic";
import { TOURS, type TourDef } from "@/lib/tours";

interface WhatsNewDialogProps {
  open: boolean;
  onClose: () => void;
}

export function WhatsNewDialog({ open, onClose }: WhatsNewDialogProps) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus trap + ESC key handler
  useEffect(() => {
    if (!open) return;

    // Move focus to the Close button (last focusable element) on open
    const frame = requestAnimationFrame(() => {
      if (!dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      focusable[focusable.length - 1]?.focus();
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

  // Body scroll lock while open
  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  if (!open) return null;

  const startTour = (tour: TourDef) => {
    sessionStorage.setItem(PENDING_TOUR_KEY, tour.id);
    router.push(tour.route);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="whats-new-title"
        className="w-full max-w-lg rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-gray-100 px-6 py-4">
          <span className="text-accent-500">
            <SparkleIcon />
          </span>
          <h2
            id="whats-new-title"
            className="text-[15px] font-semibold text-gray-800"
          >
            What&apos;s new in Central Intelligence
          </h2>
        </div>
        <ul className="divide-y divide-gray-100">
          {TOURS.map((tour) => (
            <li key={tour.id} className="flex items-start gap-4 px-6 py-4">
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold text-gray-800">
                  {tour.title}
                </div>
                <div className="mt-0.5 text-[12px] leading-relaxed text-gray-500">
                  {tour.blurb}
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => startTour(tour)}>
                Show me
              </Button>
            </li>
          ))}
        </ul>
        <div className="flex justify-end border-t border-gray-100 px-6 py-3">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
