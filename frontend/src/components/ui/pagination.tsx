"use client";

import { useEffect, useState } from "react";

/**
 * Molecule: Pagination
 *
 * Shared page-navigation + records-per-page control for every data table.
 * Backends differ in param naming (`page`+`per_page`, `page`+`limit`) and
 * response shape (`{total}` vs `{pagination:{totalPages}}`), so this component
 * stays presentational: callers normalize to (page, total, pageSize) and pass
 * `onPageChange` / `onPageSizeChange`. See `usePagination` for the state hook
 * that pairs with it.
 *
 * Default page size is 20 (see DEFAULT_PAGE_SIZE).
 */

export const PAGE_SIZE_OPTIONS = [20, 50, 100] as const;
export const DEFAULT_PAGE_SIZE = 20;

interface PaginationProps {
  page: number; // 1-based current page
  total: number; // total record count across all pages
  pageSize: number; // current records-per-page
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  className?: string;
}

/** "Go to page N" input. Local draft state so typing doesn't fire a fetch per
 *  keystroke; commits (clamped to [1, totalPages]) on Enter or blur. Resets to
 *  the live page whenever the page changes elsewhere (Prev/Next/filter reset). */
function JumpToPage({
  page,
  totalPages,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  const [draft, setDraft] = useState(String(page));

  useEffect(() => {
    setDraft(String(page));
  }, [page]);

  const commit = () => {
    const parsed = parseInt(draft, 10);
    if (Number.isNaN(parsed)) {
      setDraft(String(page)); // revert garbage
      return;
    }
    const clamped = Math.max(1, Math.min(totalPages, parsed));
    setDraft(String(clamped));
    if (clamped !== page) onPageChange(clamped);
  };

  return (
    <div className="flex items-center gap-1.5 text-sm text-gray-500">
      <label htmlFor="jump-page">Go to</label>
      <input
        id="jump-page"
        type="number"
        inputMode="numeric"
        min={1}
        max={totalPages}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          }
        }}
        aria-label={`Jump to page (1 to ${totalPages})`}
        className="w-14 rounded-md border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700 text-center focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
      />
    </div>
  );
}

export function Pagination({
  page,
  total,
  pageSize,
  onPageChange,
  onPageSizeChange,
  className = "",
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasPrevious = page > 1;
  const hasNext = page < totalPages;

  // 1-based inclusive range of records shown on this page, e.g. "21–40 of 214".
  const firstRow = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastRow = Math.min(page * pageSize, total);

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-t border-gray-100 ${className}`}
    >
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <label htmlFor="page-size" className="text-gray-500">
          Rows per page
        </label>
        <select
          id="page-size"
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="rounded-md border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
        >
          {PAGE_SIZE_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <span className="text-gray-400">
          {firstRow}–{lastRow} of {total}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={!hasPrevious}
          className="text-sm font-medium text-gray-600 hover:text-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ← Previous
        </button>
        <span className="text-sm text-gray-500">
          Page {page} of {totalPages}
        </span>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={!hasNext}
          className="text-sm font-medium text-gray-600 hover:text-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Next →
        </button>
        {totalPages > 1 && (
          <JumpToPage page={page} totalPages={totalPages} onPageChange={onPageChange} />
        )}
      </div>
    </div>
  );
}
