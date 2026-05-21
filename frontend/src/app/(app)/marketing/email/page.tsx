"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// ─── API response type ───────────────────────────────────────────────────────

interface EmailCampaignRow {
  id: string;
  name: string;
  subject: string | null;
  campaign_type: string | null;
  status: string;
  sent_at: string | null;
  recipients_count: number;
  open_count: number;
  click_count: number;
  open_rate: number | null;
  click_rate: number | null;
  source: string | null;
  external_id: string | null;
}

interface EmailData {
  campaigns: number;
  avg_open_rate: number;
  avg_click_rate: number;
  generated_at: string;
  recent_campaigns: EmailCampaignRow[];
}

// ─── Source pill ──────────────────────────────────────────────────────────────

function SourcePill({ source }: { source: string | null }) {
  if (!source) {
    return (
      <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 border border-gray-200">
        Untagged
      </span>
    );
  }
  // mailchimp → emerald (live data), seed → amber (placeholder), other → gray
  const styles: Record<string, string> = {
    mailchimp: "bg-emerald-50 text-emerald-700 border-emerald-200",
    seed: "bg-amber-50 text-amber-700 border-amber-200",
    manual: "bg-indigo-50 text-indigo-700 border-indigo-200",
  };
  const cls = styles[source] ?? "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${cls}`}>
      {source}
    </span>
  );
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// ─── Compose CTA card ─────────────────────────────────────────────────────────

function ComposeCtaCard() {
  return (
    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex flex-col items-start gap-4">
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center w-12 h-12 rounded-full flex-shrink-0 shadow-sm"
          style={{ background: "linear-gradient(135deg, #10B981 0%, #059669 100%)" }}
          aria-hidden="true"
        >
          <span className="text-xl leading-none">✉️</span>
        </div>
        <div>
          <h2 className="text-sm font-bold text-gray-900">Compose Email</h2>
          <p className="text-xs text-emerald-700 font-medium mt-0.5">
            Draft and send to your list
          </p>
        </div>
      </div>
      <p className="text-sm text-gray-600 leading-relaxed">
        Write a new email campaign with AI-assisted copy suggestions and send it
        to a segment of your subscriber list.
      </p>
      <Button variant="primary" href="/marketing/email/compose">
        Compose Email <span aria-hidden="true">→</span>
      </Button>
    </div>
  );
}

// ─── Recent campaigns empty state ─────────────────────────────────────────────

function RecentCampaignsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        📬
      </span>
      <p className="text-sm font-medium text-gray-500">No campaigns yet.</p>
      <p className="text-xs text-gray-400">
        Send your first email to see campaign results here.
      </p>
    </div>
  );
}

// ─── Recent campaigns card ────────────────────────────────────────────────────

function RecentCampaignsCard({ campaigns }: { campaigns: EmailCampaignRow[] }) {
  return (
    <Card>
      <CardHeader
        title="Recent Campaigns"
        action={
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">
              {campaigns.length} shown
            </span>
            <Button variant="ghost" size="sm" href="/marketing/email/compose">
              + New Campaign
            </Button>
          </div>
        }
      />
      <CardBody noPadding>
        {campaigns.length === 0 ? (
          <RecentCampaignsEmptyState />
        ) : (
          <div className="divide-y divide-gray-100">
            {campaigns.map((c) => (
              <div key={c.id} className="px-5 py-3 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-gray-900 truncate">{c.name}</p>
                    <SourcePill source={c.source} />
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5 truncate">
                    {c.subject ?? "(no subject)"} · {formatDate(c.sent_at)}
                  </p>
                </div>
                <div className="hidden sm:flex items-center gap-6 text-right shrink-0">
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-gray-400">Sent</p>
                    <p className="text-sm font-semibold text-gray-900">{c.recipients_count.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-gray-400">Open</p>
                    <p className="text-sm font-semibold text-gray-900">{formatPercent(c.open_rate)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-gray-400">Click</p>
                    <p className="text-sm font-semibold text-gray-900">{formatPercent(c.click_rate)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function EmailPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      {/* Heading skeleton */}
      <div>
        <Skeleton className="h-6 w-44" />
        <Skeleton className="h-4 w-80 mt-2" />
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

      {/* Compose CTA skeleton */}
      <Skeleton className="h-44 rounded-xl" />

      {/* Recent campaigns skeleton */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-3 w-24" />
        </div>
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Skeleton className="w-10 h-10 rounded-full" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-60" />
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function EmailPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<EmailData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<EmailData>("/email", {
          silent: true,
        });
        if (!cancelled) setData(result);
      } catch {
        // On error, data stays null — page renders with "—" fallbacks.
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
        <Header title="Email" />
        <EmailPageSkeleton />
      </>
    );
  }

  return (
    <>
      <Header title="Email" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Email Campaigns</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Subscriber performance and campaign results across all email sends.
          </p>
        </div>

        {/* Row 1: KPI tiles */}
        <section aria-label="Email KPIs">
          <KpiRow>
            <KpiCard label="Campaigns Sent" value={data ? data.campaigns.toLocaleString() : "—"} borderColor="#10B981" />
            <KpiCard label="Open Rate" value={data ? `${data.avg_open_rate.toFixed(1)}%` : "—"} borderColor="#10B981" />
            <KpiCard label="CTR" value={data ? `${data.avg_click_rate.toFixed(1)}%` : "—"} borderColor="#10B981" />
            <KpiCard label="Conversions" value="—" borderColor="#10B981" />
          </KpiRow>
        </section>

        {/* Row 2: Compose CTA — full width */}
        <ComposeCtaCard />

        {/* Row 3: Recent campaigns */}
        <RecentCampaignsCard campaigns={data?.recent_campaigns ?? []} />
      </main>
    </>
  );
}
