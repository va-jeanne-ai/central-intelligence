"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/format";

// ─── API response types (GET /offers/catalog — deliverable 5) ──────────────

interface OfferCatalogItem {
  offer_id: string | null;
  name: string | null;
  offer_type: string | null;
  description: string | null;
  price: number | null;
  status: string | null;
  url: string | null;
  sales_count: number;
  revenue: number;
}

interface OfferPaymentLevelRow {
  program: string | null;
  payment_level: string | null;
  offer_id: string | null;
  amount_collected: number;
  revenue_earned: number;
}

interface OfferCatalogResponse {
  offers: OfferCatalogItem[];
  payment_levels: OfferPaymentLevelRow[];
  total_revenue: number;
  total_sales_count: number;
  generated_at: string;
}

const UNATTRIBUTED_LABEL = "Unattributed";

// ─── Status chip — real WGR statuses ("Active"), same local-chip pattern
// as /marketing/ads (real values don't map cleanly onto the closed-enum
// shared StatusBadge). ────────────────────────────────────────────────────

const STATUS_CHIP_CLASSES: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  inactive: "bg-gray-100 text-gray-500 border-gray-200",
  archived: "bg-gray-100 text-gray-500 border-gray-200",
};

function StatusChip({ status }: { status: string | null }) {
  if (!status) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  const key = status.trim().toLowerCase();
  const classes = STATUS_CHIP_CLASSES[key] ?? "bg-gray-100 text-gray-500 border-gray-200";
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border capitalize ${classes}`}
    >
      {status}
    </span>
  );
}

// ─── Offer catalog table ─────────────────────────────────────────────────────

function OfferCatalogTable({ offers }: { offers: OfferCatalogItem[] }) {
  if (offers.length === 0) {
    return (
      <p className="text-sm text-gray-400 text-center py-8">
        No offers found in the catalog.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" aria-label="Real offer catalog with sales and revenue">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">Offer</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Type</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Price</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Status</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Sales</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">Revenue</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {offers.map((o) => {
            const isUnattributed = o.name === UNATTRIBUTED_LABEL;
            return (
              <tr
                key={o.offer_id ?? UNATTRIBUTED_LABEL}
                className={`hover:bg-gray-50 transition-colors ${isUnattributed ? "bg-amber-50/40" : ""}`}
              >
                <td className="px-5 py-3 font-medium text-gray-800 max-w-xs truncate" title={o.name ?? undefined}>
                  {isUnattributed ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200">
                      {o.name}
                    </span>
                  ) : (
                    o.name ?? "Untitled offer"
                  )}
                </td>
                <td className="px-3 py-3 text-gray-500 text-xs">{o.offer_type ?? "—"}</td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">
                  {o.price != null ? formatCurrency(o.price) : isUnattributed ? "—" : "Custom"}
                </td>
                <td className="px-3 py-3">
                  <StatusChip status={o.status} />
                </td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">
                  {o.sales_count.toLocaleString()}
                </td>
                <td className="px-5 py-3 text-right tabular-nums font-semibold text-gray-900">
                  {formatCurrency(o.revenue)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Payment-level breakdown card ────────────────────────────────────────────

function PaymentLevelsCard({ rows }: { rows: OfferPaymentLevelRow[] }) {
  // Group rows by program for a lightly-nested display.
  const byProgram = new Map<string, OfferPaymentLevelRow[]>();
  for (const row of rows) {
    const key = row.program ?? "—";
    const arr = byProgram.get(key) ?? [];
    arr.push(row);
    byProgram.set(key, arr);
  }

  return (
    <Card>
      <CardHeader
        title="Payment Levels"
        action={<span className="text-xs text-gray-400">{rows.length} rows</span>}
      />
      <CardBody className="flex flex-col gap-4">
        {byProgram.size === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">No payment-level data.</p>
        ) : (
          Array.from(byProgram.entries()).map(([program, programRows]) => (
            <div key={program} className="flex flex-col gap-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                {program}
              </span>
              <div className="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100">
                {programRows.map((row) => (
                  <div
                    key={`${row.program}-${row.payment_level}-${row.offer_id}`}
                    className="flex items-center justify-between px-3 py-2 text-xs"
                  >
                    <span className="text-gray-700 font-medium capitalize">
                      {row.payment_level ?? "—"}
                    </span>
                    <span className="text-gray-500 tabular-nums">
                      {formatCurrency(row.amount_collected)} collected
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </CardBody>
    </Card>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function OffersPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-8 w-32 rounded-lg" />
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-7 w-16" />
          </div>
        ))}
      </div>

      <div className="flex gap-6 items-start">
        <div className="flex-1 min-w-0 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-3 w-16" />
          </div>
          <div className="p-5 flex flex-col gap-3">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        </div>
        <div className="w-[320px] flex-shrink-0">
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function OffersPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<OfferCatalogResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<OfferCatalogResponse>("/offers/catalog", {
          silent: true,
        });
        if (!cancelled) setData(result);
      } catch {
        // On error, data stays null — page renders with empty state.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void fetchData();
    return () => { cancelled = true; };
  }, [authLoading]);

  if (isLoading) {
    return (
      <>
        <Header title="Offers" />
        <OffersPageSkeleton />
      </>
    );
  }

  const offers = data?.offers ?? [];
  const realOfferCount = offers.filter((o) => o.name !== UNATTRIBUTED_LABEL).length;
  const activeCount = offers.filter((o) => (o.status ?? "").trim().toLowerCase() === "active").length;

  return (
    <>
      <Header title="Offers" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Top bar */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Offers</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Real offer catalog synced from WGR, with sales count and revenue per offer.
            </p>
          </div>
          <Button variant="primary" href="/marketing/offers/builder">
            + Create Offer
          </Button>
        </div>

        {/* KPI row */}
        <KpiRow>
          <KpiCard
            label="Active Offers"
            value={data ? activeCount.toLocaleString() : "—"}
            sub={data ? `${realOfferCount} in catalog` : undefined}
            borderColor="#10B981"
          />
          <KpiCard
            label="Total Offers"
            value={data ? realOfferCount.toLocaleString() : "—"}
            borderColor="#F59E0B"
          />
          <KpiCard
            label="Total Sales"
            value={data ? data.total_sales_count.toLocaleString() : "—"}
            borderColor="#3B82F6"
          />
          <KpiCard
            label="Total Revenue"
            value={data ? formatCurrency(data.total_revenue) : "—"}
            borderColor="#F97316"
          />
        </KpiRow>

        {/* Two-column layout: catalog table + payment-level breakdown */}
        <div className="flex gap-6 items-start">
          <div className="flex-1 min-w-0">
            <Card>
              <CardHeader
                title="Offer Catalog"
                action={
                  <span className="text-xs text-gray-400">
                    {data ? `${realOfferCount} offers` : "—"}
                  </span>
                }
              />
              <CardBody noPadding>
                <OfferCatalogTable offers={offers} />
              </CardBody>
            </Card>
          </div>

          <div className="w-[320px] flex-shrink-0">
            <PaymentLevelsCard rows={data?.payment_levels ?? []} />
          </div>
        </div>
      </main>
    </>
  );
}
