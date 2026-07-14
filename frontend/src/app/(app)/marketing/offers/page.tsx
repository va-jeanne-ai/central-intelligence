"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { ScoreBar } from "@/components/ui/score-bar";
import { Button } from "@/components/ui/button";
import { FormField, FormInput, FormTextarea } from "@/components/ui/form-field";
import { SuggestionPanel } from "@/components/ui/suggestion-panel";
import type { OfferListResponse, OfferItem } from "@/types";

// ─── Types ────────────────────────────────────────────────────────────────────

type OfferStatus = "active" | "draft" | "archived";

// ─── Constants ────────────────────────────────────────────────────────────────

const AI_SUGGESTIONS = [
  {
    title: "Add a time-based bonus",
    body: "Offers with urgency bonuses convert 23% higher. Consider: 'Book this week and get a free 1:1 strategy session.'",
  },
  {
    title: "Strengthen your guarantee",
    body: "Your ICP values risk reduction. Try: 'Double your leads in 90 days or your next month is free.'",
  },
  {
    title: "Price anchoring opportunity",
    body: "Position against the VIP Day ($4,997) to make the Accelerator ($2,997) feel like a better deal.",
  },
  {
    title: "Missing social proof",
    body: "Add a 'X coaches enrolled' counter. Templates with social proof see 31% more conversions.",
  },
];

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_BORDER: Record<string, string> = {
  active: "#10B981",
  draft: "#4F46E5",
  archived: "#D1D5DB",
};

// ─── Offer card ───────────────────────────────────────────────────────────────

function OfferCard({ offer }: { offer: OfferItem }) {
  const status = offer.status as OfferStatus;
  const borderLeftColor = STATUS_BORDER[status] ?? "#D1D5DB";
  const isArchived = status === "archived";
  const isDraft = status === "draft";
  const opacity = isArchived ? 0.6 : isDraft ? 0.85 : undefined;
  const priceColor = isArchived || isDraft ? "text-gray-400" : "text-gray-900";

  return (
    <Card borderLeftColor={borderLeftColor} opacity={opacity}>
      <div className="p-5 flex flex-col gap-3">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`text-sm font-bold ${isArchived ? "text-gray-500" : "text-gray-900"}`}
            >
              {offer.name}
            </span>
            <StatusBadge status={status} />
          </div>
          <span className={`text-lg font-bold tabular-nums flex-shrink-0 ${priceColor}`}>
            {/* price is null for custom-priced offers (e.g. "… - Custom" synced from WGR) */}
            {offer.price != null ? `$${offer.price.toLocaleString()}` : "Custom"}
          </span>
        </div>

        {/* Description */}
        {offer.description !== null && offer.description !== "" && (
          <p className="text-xs text-gray-500 leading-relaxed">{offer.description}</p>
        )}

        {/* ICP Alignment bar — using offer_type as a proxy label */}
        <ScoreBar
          value={75}
          label="ICP Alignment"
          color={isArchived ? "gray" : "emerald"}
        />
      </div>
    </Card>
  );
}

// ─── Offer Builder card ───────────────────────────────────────────────────────

function OfferBuilderCard() {
  return (
    <Card>
      <CardHeader title="Offer Builder" />
      <CardBody className="flex flex-col gap-4">
        <FormField label="Offer Name">
          <FormInput
            type="text"
            placeholder="e.g. 90-Day Coaching Accelerator"
          />
        </FormField>

        <FormField label="Price">
          <FormInput type="text" placeholder="e.g. $2,997" />
        </FormField>

        <FormField label="Core Features (one per line)">
          <FormTextarea
            rows={3}
            placeholder={"Weekly coaching calls\nCommunity access\nDone-for-you templates"}
          />
        </FormField>

        <FormField label="Bonuses">
          <FormTextarea
            rows={2}
            placeholder="e.g. Free strategy call for this week only"
          />
        </FormField>

        <FormField label="Guarantee">
          <FormInput
            type="text"
            placeholder="e.g. Full refund if no results in 30 days"
          />
        </FormField>

        <div className="flex items-center gap-2 pt-1">
          <Button variant="primary" className="flex-1">
            Save Offer
          </Button>
          <Button variant="ghost" className="flex-1">
            AI Suggestions
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function OffersPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      {/* Top bar skeleton */}
      <div className="flex items-center justify-between gap-4">
        <Skeleton className="h-6 w-24" />
        <div className="flex items-center gap-3">
          <Skeleton className="h-8 w-28 rounded-lg" />
          <Skeleton className="h-8 w-32 rounded-lg" />
        </div>
      </div>

      {/* KPI tiles skeleton */}
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-7 w-16" />
          </div>
        ))}
      </div>

      {/* Two-column skeleton */}
      <div className="flex gap-6 items-start">
        <div className="flex-1 min-w-0 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-3 w-16" />
          </div>
          <div className="p-5 flex flex-col gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-3">
                <div className="flex items-start justify-between">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-6 w-16" />
                </div>
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-2 w-full rounded-full" />
              </div>
            ))}
          </div>
        </div>
        <div className="w-[380px] flex-shrink-0 flex flex-col gap-5">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function OffersPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<OfferListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<"all" | OfferStatus>("all");

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<OfferListResponse>("/offers", { silent: true });
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

  const allOffers: OfferItem[] = data?.offers ?? [];
  const filteredOffers =
    statusFilter === "all" ? allOffers : allOffers.filter((o) => o.status === statusFilter);

  const activeCount = allOffers.filter((o) => o.status === "active").length;
  const draftCount = allOffers.filter((o) => o.status === "draft").length;
  const archivedCount = allOffers.filter((o) => o.status === "archived").length;

  return (
    <>
      <Header title="Offers" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Top bar */}
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-xl font-bold text-gray-900">Offers</h1>
          <div className="flex items-center gap-3 flex-shrink-0">
            <Button variant="ghost">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as "all" | OfferStatus)}
                className="bg-transparent text-sm font-medium text-gray-700 cursor-pointer focus:outline-none"
              >
                <option value="all">All Status</option>
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </select>
            </Button>
            <Button variant="primary" href="/marketing/offers/builder">
              + Create Offer
            </Button>
          </div>
        </div>

        {/* KPI row */}
        <KpiRow>
          <KpiCard
            label="Active Offers"
            value={data ? activeCount.toLocaleString() : "—"}
            sub={data ? `${draftCount} drafts, ${archivedCount} archived` : undefined}
            borderColor="#10B981"
          />
          <KpiCard
            label="Total Offers"
            value={data ? (data.total ?? allOffers.length).toLocaleString() : "—"}
            borderColor="#F59E0B"
          />
          <KpiCard
            label="Conversion Rate"
            value="—"
            borderColor="#3B82F6"
          />
          <KpiCard
            label="Revenue / Offer"
            value="—"
            borderColor="#F97316"
          />
        </KpiRow>

        {/* Two-column layout */}
        <div className="flex gap-6 items-start">
          {/* Left column: Offer Library */}
          <div className="flex-1 min-w-0">
            <Card>
              <CardHeader
                title="Offer Library"
                action={
                  <span className="text-xs text-gray-400">
                    {data ? `${data.total ?? allOffers.length} offers` : "—"}
                  </span>
                }
              />
              <CardBody className="flex flex-col gap-4">
                {filteredOffers.length > 0 ? (
                  filteredOffers.map((offer) => (
                    <OfferCard key={offer.offer_id} offer={offer} />
                  ))
                ) : (
                  <p className="text-sm text-gray-400 text-center py-8">
                    {data ? "No offers match this filter." : "No offers found."}
                  </p>
                )}
              </CardBody>
            </Card>
          </div>

          {/* Right column: sidebar */}
          <div className="w-[380px] flex-shrink-0 flex flex-col gap-5">
            <OfferBuilderCard />
            <SuggestionPanel items={AI_SUGGESTIONS} />
          </div>
        </div>
      </main>
    </>
  );
}
