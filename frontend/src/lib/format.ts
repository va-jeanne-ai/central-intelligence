// ─── Currency formatting ────────────────────────────────────────────────────
// Shared helper so every surface that renders a currency value (Insights
// charts, KPI cards, future pages) picks up the instance's configured
// currency symbol instead of hardcoding "$". The symbol itself is held in a
// module-level singleton (see setCurrencySymbol/getCurrencySymbol) that the
// useBranding hook populates once branding loads — pure formatting modules
// that can't call hooks (e.g. team-formatting.ts) can still read it via
// getCurrencySymbol().

let currencySymbol = "$";

/** Set by the branding provider/hook once `/config/branding` resolves. */
export function setCurrencySymbol(symbol: string): void {
  currencySymbol = symbol || "$";
}

/** Read the current instance currency symbol. Defaults to "$" until branding loads. */
export function getCurrencySymbol(): string {
  return currencySymbol;
}

export interface FormatCurrencyOptions {
  /** Override the symbol for this call instead of using the singleton. */
  symbol?: string;
}

/**
 * Formats a numeric value as currency using the instance's configured symbol.
 * Mirrors the existing call-site convention across the app:
 * `${symbol}${Math.round(value).toLocaleString()}` — whole numbers,
 * thousands-separated, symbol prefixed with no space.
 */
export function formatCurrency(value: number, opts: FormatCurrencyOptions = {}): string {
  const symbol = opts.symbol ?? getCurrencySymbol();
  return `${symbol}${Math.round(value).toLocaleString()}`;
}
