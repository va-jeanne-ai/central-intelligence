"use client";

// Shared appointment detail panel — used by both the /appointments Calendar
// tab and the /calendar page's appointments overlay so clicking an
// appointment chip looks identical everywhere. No navigation: there's no
// appointment detail *page* in this app (only a lead detail page, which
// this links out to when the appointment has a lead_id).

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { formatTimeRange } from "@/lib/calendar-helpers";
import { resolveAppointmentStatus } from "@/lib/appointment-status";
import type { AppointmentRow } from "@/types";

interface AppointmentDetailPopoverProps {
  appointment: AppointmentRow | null;
  onClose: () => void;
}

function formatFullDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function AppointmentDetailPopover({ appointment, onClose }: AppointmentDetailPopoverProps) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!appointment) return;

    const frame = requestAnimationFrame(() => closeRef.current?.focus());

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          }
        } else if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [appointment, onClose]);

  if (!appointment) return null;

  const status = resolveAppointmentStatus(appointment.status);
  const time = formatTimeRange(appointment.scheduledAt, appointment.end_at, false);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="appointment-detail-title"
        className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold ${status.badgeClasses}`}
            >
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: status.dotColor }} />
              {status.label}
            </span>
            <h2 id="appointment-detail-title" className="text-base font-bold text-gray-900 mt-2">
              {appointment.contact_name || appointment.appointment_type || "Appointment"}
            </h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-gray-400 hover:text-gray-600 text-lg leading-none focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 rounded"
          >
            ×
          </button>
        </div>

        <dl className="mt-4 space-y-2.5 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-gray-400 text-xs font-semibold uppercase tracking-wide">When</dt>
            <dd className="text-gray-800 text-right">
              {formatFullDate(appointment.scheduledAt)}
              <div className="text-gray-500 font-mono text-xs">{time}</div>
            </dd>
          </div>
          {appointment.contact_email && (
            <div className="flex justify-between gap-4">
              <dt className="text-gray-400 text-xs font-semibold uppercase tracking-wide">Contact</dt>
              <dd className="text-gray-800 text-right truncate">{appointment.contact_email}</dd>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <dt className="text-gray-400 text-xs font-semibold uppercase tracking-wide">Rep</dt>
            <dd className="text-gray-800 text-right">{appointment.rep_name ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-gray-400 text-xs font-semibold uppercase tracking-wide">Type</dt>
            <dd className="text-gray-800 text-right">{appointment.appointment_type ?? "—"}</dd>
          </div>
        </dl>

        <div className="mt-6 flex justify-end gap-2">
          {appointment.lead_id && (
            <button
              type="button"
              onClick={() => router.push(`/leads/${appointment.lead_id}`)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-accent-500 hover:bg-accent-600 text-white transition-colors"
            >
              View lead
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
