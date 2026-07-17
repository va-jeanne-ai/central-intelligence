"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { configClient } from "@/lib/config-client";
import { setCurrencySymbol } from "@/lib/format";
import { APP_CONFIG } from "@/lib/config";
import type { BrandingConfig } from "@/types";

// ─── Fallback ───────────────────────────────────────────────────────────────
// Used while the branding request is in flight and whenever it errors (e.g.
// API unreachable) — mirrors the previous hardcoded APP_CONFIG values so the
// UI degrades to today's static branding instead of blank/undefined fields.

const FALLBACK_BRANDING: BrandingConfig = {
  app_name: APP_CONFIG.name,
  tagline: APP_CONFIG.subtitle,
  logo_url: null,
  colors: null,
  currency_code: "USD",
  currency_symbol: "$",
  locale: "en-US",
};

const BRANDING_QUERY_KEY = ["config", "branding"] as const;
const BRANDING_STALE_TIME_MS = 5 * 60 * 1000; // 5 minutes — cosmetic, changes rarely

/**
 * Fetches the instance's public white-label branding config (no auth
 * required — safe to call from the pre-auth /login page as well as the
 * authenticated app shell). Falls back to the static APP_CONFIG values
 * while loading or if the request fails, so the UI never renders blank
 * branding.
 *
 * Also mirrors `currency_symbol` into the module-level singleton in
 * `@/lib/format` so pure formatting helpers (which can't call hooks) stay in
 * sync — call this hook once near the app root (or anywhere it's rendered)
 * and every `formatCurrency`/`getCurrencySymbol()` call downstream picks up
 * the resolved symbol.
 */
export function useBranding() {
  const query = useQuery({
    queryKey: BRANDING_QUERY_KEY,
    queryFn: () => configClient.getBranding(),
    staleTime: BRANDING_STALE_TIME_MS,
    retry: 1,
  });

  const branding = query.data ?? FALLBACK_BRANDING;

  useEffect(() => {
    setCurrencySymbol(branding.currency_symbol);
  }, [branding.currency_symbol]);

  return {
    branding,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
