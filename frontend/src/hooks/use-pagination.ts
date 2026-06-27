"use client";

import { useCallback, useEffect, useState } from "react";
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from "@/components/ui/pagination";

/**
 * Pagination state shared by every table.
 *
 * - `page` is 1-based.
 * - `pageSize` defaults to 20 and is persisted per table in localStorage
 *   (keyed by `storageKey`) so a user's choice survives refresh/navigation.
 * - Changing `pageSize` snaps back to page 1 (the old page number is
 *   meaningless at a new size).
 * - `resetToFirstPage` is what callers fire when a FILTER changes, so the
 *   user isn't stranded on a now-empty page 3.
 *
 * The hook is deliberately transport-agnostic: it owns only page/pageSize.
 * Each table maps these onto its endpoint's param names (`per_page` vs
 * `limit`) and reads `total` out of its own response shape.
 */

function isValidSize(n: unknown): n is number {
  return typeof n === "number" && (PAGE_SIZE_OPTIONS as readonly number[]).includes(n);
}

function readStoredSize(storageKey: string): number {
  try {
    const raw = localStorage.getItem(storageKey);
    const parsed = raw == null ? NaN : Number(raw);
    return isValidSize(parsed) ? parsed : DEFAULT_PAGE_SIZE;
  } catch {
    return DEFAULT_PAGE_SIZE;
  }
}

export interface UsePaginationResult {
  page: number;
  pageSize: number;
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
  resetToFirstPage: () => void;
}

export function usePagination(storageKey: string): UsePaginationResult {
  const [page, setPage] = useState(1);
  // Start from the default for deterministic SSR/first render, then hydrate the
  // persisted choice on mount (localStorage is client-only).
  const [pageSize, setPageSizeState] = useState<number>(DEFAULT_PAGE_SIZE);

  useEffect(() => {
    const stored = readStoredSize(storageKey);
    if (stored !== DEFAULT_PAGE_SIZE) setPageSizeState(stored);
  }, [storageKey]);

  const setPageSize = useCallback(
    (next: number) => {
      setPageSizeState(next);
      setPage(1); // page index is invalid at a new size
      try {
        localStorage.setItem(storageKey, String(next));
      } catch {
        /* storage unavailable — keep the in-memory choice */
      }
    },
    [storageKey],
  );

  const resetToFirstPage = useCallback(() => setPage(1), []);

  return { page, pageSize, setPage, setPageSize, resetToFirstPage };
}
