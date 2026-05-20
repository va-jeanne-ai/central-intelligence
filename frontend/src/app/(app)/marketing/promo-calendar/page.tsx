"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import type { Promotion } from "@/types";

// ─── Content type config ─────────────────────────────────────────────────────

const CONTENT_TYPES = ["email", "reel", "story", "video", "image", "carousel"] as const;
type ContentType = (typeof CONTENT_TYPES)[number];

const CONTENT_TYPE_COLORS: Record<ContentType, string> = {
  email: "#3B82F6",
  reel: "#EC4899",
  story: "#F59E0B",
  video: "#EF4444",
  image: "#10B981",
  carousel: "#14B8A6",
};

const PROMO_STATUSES = ["planned", "active", "completed", "cancelled"] as const;
type PromoStatus = (typeof PROMO_STATUSES)[number];

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getContentColor(type: string | null): string {
  if (type === null) return "#6366F1";
  return CONTENT_TYPE_COLORS[type.toLowerCase() as ContentType] ?? "#6366F1";
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function isoToDate(iso: string): Date {
  const dateOnly = iso.slice(0, 10);
  const [y, m, d] = dateOnly.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

function toDateInputValue(iso: string): string {
  return iso.slice(0, 10);
}

// ─── Form state ──────────────────────────────────────────────────────────────

interface PromoFormState {
  name: string;
  description: string;
  promo_type: ContentType;
  start_date: string;
  end_date: string;
  status: PromoStatus;
  color: string;
  notes: string;
}

const BLANK_FORM: PromoFormState = {
  name: "",
  description: "",
  promo_type: "email",
  start_date: "",
  end_date: "",
  status: "planned",
  color: "",
  notes: "",
};

// ─── Promotion modal ─────────────────────────────────────────────────────────

interface PromoModalProps {
  initial: PromoFormState;
  title: string;
  onClose: () => void;
  onSubmit: (form: PromoFormState) => Promise<void>;
  isSubmitting: boolean;
}

function PromoModal({ initial, title, onClose, onSubmit, isSubmitting }: PromoModalProps) {
  const [form, setForm] = useState<PromoFormState>(initial);

  function update<K extends keyof PromoFormState>(key: K, value: PromoFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  // Auto-set color when content type changes (unless user manually set one)
  function handleTypeChange(type: ContentType) {
    update("promo_type", type);
    update("color", CONTENT_TYPE_COLORS[type]);
  }

  const inputClass =
    "text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent w-full";
  const labelClass = "text-[10px] font-bold uppercase tracking-wider text-gray-500 block mb-1";

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-6"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 sticky top-0 bg-white rounded-t-2xl z-10">
          <h2 className="text-sm font-bold text-gray-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-xs font-medium px-3 py-1.5 border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors duration-150"
          >
            Cancel
          </button>
        </div>

        {/* Form */}
        <div className="px-6 py-5 flex flex-col gap-4">
          {/* Name */}
          <div>
            <label className={labelClass}>Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => update("name", e.target.value)}
              placeholder="e.g. Spring Launch Email Sequence"
              className={inputClass}
            />
          </div>

          {/* Description */}
          <div>
            <label className={labelClass}>Description</label>
            <textarea
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
              placeholder="Describe this content piece..."
              rows={2}
              className={`${inputClass} resize-none`}
            />
          </div>

          {/* Content Type + Status */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Content Type</label>
              <select
                value={form.promo_type}
                onChange={(e) => handleTypeChange(e.target.value as ContentType)}
                className={inputClass}
              >
                {CONTENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Status</label>
              <select
                value={form.status}
                onChange={(e) => update("status", e.target.value as PromoStatus)}
                className={inputClass}
              >
                {PROMO_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Start Date</label>
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => update("start_date", e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>End Date</label>
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => update("end_date", e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          {/* Color picker */}
          <div>
            <label className={labelClass}>Color</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={form.color || CONTENT_TYPE_COLORS[form.promo_type]}
                onChange={(e) => update("color", e.target.value)}
                className="w-10 h-10 rounded-lg border border-gray-200 cursor-pointer p-0.5 bg-white"
              />
              <div className="flex-1 flex flex-wrap gap-1.5">
                {Object.entries(CONTENT_TYPE_COLORS).map(([type, c]) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => update("color", c)}
                    className={`w-6 h-6 rounded-full border-2 transition-transform hover:scale-110 ${
                      form.color === c ? "border-gray-900 scale-110" : "border-transparent"
                    }`}
                    style={{ backgroundColor: c }}
                    title={type.charAt(0).toUpperCase() + type.slice(1)}
                    aria-label={`Select ${type} color`}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className={labelClass}>Notes</label>
            <textarea
              value={form.notes}
              onChange={(e) => update("notes", e.target.value)}
              placeholder="Any additional notes..."
              rows={2}
              className={`${inputClass} resize-none`}
            />
          </div>

          {/* Submit */}
          <div className="flex items-center gap-3 pt-1 border-t border-gray-100">
            <button
              type="button"
              onClick={() => void onSubmit(form)}
              disabled={isSubmitting || form.name.trim() === "" || form.start_date === "" || form.end_date === ""}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-200 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95 shadow-sm"
            >
              {isSubmitting ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-semibold rounded-lg transition-colors duration-150"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Calendar view ───────────────────────────────────────────────────────────

interface CalendarViewProps {
  promotions: Promotion[];
  onEdit: (promo: Promotion) => void;
}

function CalendarView({ promotions, onEdit }: CalendarViewProps) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());

  function prevMonth() {
    if (month === 0) { setMonth(11); setYear((y) => y - 1); }
    else { setMonth((m) => m - 1); }
  }

  function nextMonth() {
    if (month === 11) { setMonth(0); setYear((y) => y + 1); }
    else { setMonth((m) => m + 1); }
  }

  function goToday() {
    setYear(today.getFullYear());
    setMonth(today.getMonth());
  }

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: (number | null)[] = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  function getPromosForDay(day: number): Promotion[] {
    const cellDate = new Date(year, month, day);
    return promotions.filter((p) => {
      const start = isoToDate(p.start_date);
      const end = isoToDate(p.end_date);
      return cellDate >= start && cellDate <= end;
    });
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Month nav */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <button
          type="button"
          onClick={prevMonth}
          className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500"
          aria-label="Previous month"
        >
          &larr;
        </button>
        <div className="flex items-center gap-1">
          <select
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
            className="text-sm font-bold text-gray-900 bg-transparent cursor-pointer focus:outline-none hover:text-indigo-600 transition-colors border-none p-0 pr-5"
          >
            {MONTH_NAMES.map((name, i) => (
              <option key={i} value={i}>{name}</option>
            ))}
          </select>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="text-sm font-bold text-gray-900 bg-transparent cursor-pointer focus:outline-none hover:text-indigo-600 transition-colors border-none p-0 pr-5"
          >
            {Array.from({ length: 11 }, (_, i) => today.getFullYear() - 2 + i).map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={nextMonth}
          className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500"
          aria-label="Next month"
        >
          &rarr;
        </button>
      </div>

      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 border-b border-gray-100">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
          <div key={d} className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-gray-400">
            {d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7">
        {cells.map((day, idx) => {
          const isToday =
            day !== null &&
            day === today.getDate() &&
            month === today.getMonth() &&
            year === today.getFullYear();
          const dayPromos = day !== null ? getPromosForDay(day) : [];

          return (
            <div
              key={idx}
              className={`min-h-[90px] border-b border-r border-gray-100 p-1.5 ${
                day === null ? "bg-gray-50/50" : "bg-white"
              } ${idx % 7 === 6 ? "border-r-0" : ""}`}
            >
              {day !== null && (
                <>
                  <span
                    className={`text-xs font-medium w-6 h-6 flex items-center justify-center rounded-full mb-1 ${
                      isToday
                        ? "bg-indigo-600 text-white font-bold"
                        : "text-gray-500"
                    }`}
                  >
                    {day}
                  </span>
                  <div className="flex flex-col gap-0.5">
                    {dayPromos.slice(0, 3).map((p) => {
                      const color = p.color ?? getContentColor(p.promo_type);
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => onEdit(p)}
                          className="text-left w-full truncate text-[10px] font-medium px-1.5 py-0.5 rounded text-white leading-tight hover:opacity-90 transition-opacity"
                          style={{ backgroundColor: color }}
                          title={`${p.promo_type}: ${p.name}`}
                        >
                          {p.name}
                        </button>
                      );
                    })}
                    {dayPromos.length > 3 && (
                      <span className="text-[10px] text-gray-400 px-1">
                        +{dayPromos.length - 3} more
                      </span>
                    )}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── List view ───────────────────────────────────────────────────────────────

interface ListViewProps {
  promotions: Promotion[];
  onEdit: (promo: Promotion) => void;
  onDelete: (id: string) => void;
}

function ListView({ promotions, onEdit, onDelete }: ListViewProps) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const filtered = promotions.filter((p) => {
    const matchesStatus = statusFilter === "all" || p.status === statusFilter;
    const matchesType = typeFilter === "all" || p.promo_type === typeFilter;
    return matchesStatus && matchesType;
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Filters */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="all">All Status</option>
          {PROMO_STATUSES.map((s) => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="all">All Types</option>
          {CONTENT_TYPES.map((t) => (
            <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
          ))}
        </select>
        <span className="text-xs text-gray-400 ml-auto">
          {filtered.length} item{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <span className="text-4xl" aria-hidden="true">📅</span>
          <p className="text-sm font-medium text-gray-500">No content scheduled.</p>
          <p className="text-xs text-gray-400">Create an entry to start planning.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-400">Name</th>
                <th className="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-400">Type</th>
                <th className="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-400">Start</th>
                <th className="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-400">End</th>
                <th className="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-400">Status</th>
                <th className="text-right px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((p) => {
                const color = p.color ?? getContentColor(p.promo_type);
                return (
                  <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          style={{ backgroundColor: color }}
                          aria-hidden="true"
                        />
                        <span className="font-medium text-gray-900">{p.name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full text-white"
                        style={{ backgroundColor: color }}
                      >
                        {p.promo_type}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-600 tabular-nums">{formatDate(p.start_date)}</td>
                    <td className="px-5 py-3 text-gray-600 tabular-nums">{formatDate(p.end_date)}</td>
                    <td className="px-5 py-3">
                      <span className={`text-xs font-medium capitalize ${
                        p.status === "active" ? "text-emerald-600" :
                        p.status === "completed" ? "text-gray-400" :
                        p.status === "cancelled" ? "text-red-500" :
                        "text-indigo-600"
                      }`}>
                        {p.status}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => onEdit(p)}
                          className="text-xs font-medium px-2.5 py-1 border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => onDelete(p.id)}
                          className="text-xs font-medium px-2.5 py-1 border border-red-200 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Loading skeleton ────────────────────────────────────────────────────────

function PromoCalendarSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-6 w-44" />
          <Skeleton className="h-4 w-80 mt-2" />
        </div>
        <div className="flex items-center gap-3">
          <Skeleton className="h-8 w-24 rounded-lg" />
          <Skeleton className="h-8 w-24 rounded-lg" />
          <Skeleton className="h-8 w-36 rounded-lg" />
        </div>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="flex items-center gap-4 px-5 py-4 border-b border-gray-100">
          <Skeleton className="h-5 w-5 rounded" />
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-5 w-5 rounded" />
          <Skeleton className="h-5 w-14 rounded-lg" />
        </div>
        <div className="grid grid-cols-7 border-b border-gray-100">
          {[1,2,3,4,5,6,7].map((i) => (
            <div key={i} className="px-2 py-2 flex justify-center">
              <Skeleton className="h-3 w-8" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {Array.from({ length: 35 }).map((_, i) => (
            <div key={i} className="min-h-[90px] border-b border-r border-gray-100 p-1.5">
              <Skeleton className="h-4 w-4 rounded-full mb-1" />
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function PromoCalendarPage() {
  const { isLoading: authLoading } = useAuth();
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [view, setView] = useState<"calendar" | "list">("calendar");

  const [showModal, setShowModal] = useState(false);
  const [editingPromo, setEditingPromo] = useState<Promotion | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<{ promotions: Promotion[]; total: number }>(
          "/promo-calendar",
          { silent: true }
        );
        if (!cancelled) setPromotions(result.promotions);
      } catch {
        // On error, promotions stays empty.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void fetchData();
    return () => { cancelled = true; };
  }, [authLoading]);

  async function handleCreate(form: PromoFormState) {
    setIsSubmitting(true);
    try {
      const created = await apiClient.post<Promotion>("/promo-calendar", {
        name: form.name,
        description: form.description || null,
        promo_type: form.promo_type,
        start_date: form.start_date,
        end_date: form.end_date,
        status: form.status,
        department: "marketing",
        color: form.color || null,
        notes: form.notes || null,
      });
      setPromotions((prev) => [...prev, created]);
    } catch {
      // keep modal open
    } finally {
      setIsSubmitting(false);
      setShowModal(false);
    }
  }

  async function handleEdit(form: PromoFormState) {
    if (editingPromo === null) return;
    setIsSubmitting(true);
    try {
      const updated = await apiClient.put<Promotion>(`/promo-calendar/${editingPromo.id}`, {
        name: form.name,
        description: form.description || null,
        promo_type: form.promo_type,
        start_date: form.start_date,
        end_date: form.end_date,
        status: form.status,
        department: "marketing",
        color: form.color || null,
        notes: form.notes || null,
      });
      setPromotions((prev) =>
        prev.map((p) => (p.id === editingPromo.id ? updated : p))
      );
    } catch {
      // silent
    } finally {
      setIsSubmitting(false);
      setEditingPromo(null);
    }
  }

  async function handleDelete(id: string) {
    try {
      await apiClient.delete(`/promo-calendar/${id}`);
      setPromotions((prev) => prev.filter((p) => p.id !== id));
    } catch {
      // silent
    }
  }

  function openEdit(promo: Promotion) {
    setEditingPromo(promo);
  }

  if (isLoading) {
    return (
      <>
        <Header title="Promo Calendar" />
        <PromoCalendarSkeleton />
      </>
    );
  }

  const editFormInitial: PromoFormState | null =
    editingPromo !== null
      ? {
          name: editingPromo.name,
          description: editingPromo.description ?? "",
          promo_type: (editingPromo.promo_type ?? "email") as ContentType,
          start_date: toDateInputValue(editingPromo.start_date),
          end_date: toDateInputValue(editingPromo.end_date),
          status: (editingPromo.status ?? "planned") as PromoStatus,
          color: editingPromo.color ?? "",
          notes: editingPromo.notes ?? "",
        }
      : null;

  return (
    <>
      <Header title="Promo Calendar" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Promo Calendar</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Plan and schedule promotional campaigns, content, and launches.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* View toggle */}
            <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
              <button
                type="button"
                onClick={() => setView("calendar")}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  view === "calendar"
                    ? "bg-indigo-600 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                Calendar
              </button>
              <button
                type="button"
                onClick={() => setView("list")}
                className={`px-3 py-1.5 text-xs font-medium transition-colors border-l border-gray-200 ${
                  view === "list"
                    ? "bg-indigo-600 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                List
              </button>
            </div>

            <Button variant="primary" onClick={() => setShowModal(true)}>
              + New Content
            </Button>
          </div>
        </div>

        {/* Content type legend */}
        <div className="flex items-center gap-4 flex-wrap">
          {Object.entries(CONTENT_TYPE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: color }}
                aria-hidden="true"
              />
              <span className="text-xs text-gray-500 capitalize">{type}</span>
            </div>
          ))}
        </div>

        {/* Main view */}
        {view === "calendar" ? (
          <CalendarView promotions={promotions} onEdit={openEdit} />
        ) : (
          <ListView
            promotions={promotions}
            onEdit={openEdit}
            onDelete={(id) => { void handleDelete(id); }}
          />
        )}
      </main>

      {/* Create modal */}
      {showModal && (
        <PromoModal
          initial={BLANK_FORM}
          title="Schedule Content"
          onClose={() => setShowModal(false)}
          onSubmit={handleCreate}
          isSubmitting={isSubmitting}
        />
      )}

      {/* Edit modal */}
      {editingPromo !== null && editFormInitial !== null && (
        <PromoModal
          initial={editFormInitial}
          title="Edit Content"
          onClose={() => setEditingPromo(null)}
          onSubmit={handleEdit}
          isSubmitting={isSubmitting}
        />
      )}
    </>
  );
}
