"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { Card, CardBody, StatusBadge } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import type { IntegrationSummary } from "@/types";
import { FreshnessPanel } from "./freshness-panel";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatLastSynced(iso: string | null): string {
  if (!iso) return "Never synced";
  try {
    const date = new Date(iso);
    const ms = Date.now() - date.getTime();
    const mins = Math.round(ms / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins} min ago`;
    const hrs = Math.round(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.round(hrs / 24);
    return `${days}d ago`;
  } catch {
    return "Recently";
  }
}

// ─── Card per integration ─────────────────────────────────────────────────────

function IntegrationCard({ p }: { p: IntegrationSummary }) {
  const isComingSoon = p.status === "coming_soon";
  const inner = (
    <Card
      className={`h-full ${isComingSoon ? "" : "hover:shadow-md transition-shadow"}`}
      opacity={isComingSoon ? 0.6 : undefined}
    >
      <CardBody className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-2xl leading-none" aria-hidden>{p.icon || "🔌"}</span>
            <div className="min-w-0">
              <h3 className="text-[15px] font-bold text-gray-900 truncate">{p.name}</h3>
              <p className="text-[11px] text-gray-400 capitalize">{p.category || "integration"}</p>
            </div>
          </div>
          {isComingSoon ? (
            <StatusBadge status="archived" />
          ) : p.connected ? (
            <StatusBadge status="active" />
          ) : (
            <StatusBadge status="draft" />
          )}
        </div>
        <p className="text-[13px] text-gray-600 leading-relaxed line-clamp-3 min-h-[3.5em]">
          {p.description}
        </p>
        <div className="flex items-center justify-between text-[11px] text-gray-400">
          <span>{p.connected ? formatLastSynced(p.last_synced_at) : isComingSoon ? "Coming soon" : "Not connected"}</span>
          {!isComingSoon && (
            <span className="text-accent-600 font-medium">{p.connected ? "Manage →" : "Connect →"}</span>
          )}
        </div>
      </CardBody>
    </Card>
  );

  if (isComingSoon) {
    return <div className="cursor-not-allowed" aria-disabled>{inner}</div>;
  }
  return (
    <Link href={`/integrations/${p.slug}`} className="block">
      {inner}
    </Link>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const { isLoading: authLoading } = useAuth();
  const [providers, setProviders] = useState<IntegrationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiClient.get<IntegrationSummary[]>("/integrations", { silent: true });
      setProviders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrations.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    void load();
  }, [authLoading, load]);

  const available = providers.filter((p) => p.status === "available");
  const comingSoon = providers.filter((p) => p.status === "coming_soon");

  return (
    <>
      <Header title="Integrations" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Integrations</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Connect your tools to Central Intelligence. Saved credentials are encrypted at rest;
            new data syncs into your dashboards automatically.
          </p>
        </div>

        {isLoading && (
          <p className="text-sm text-gray-400">Loading integrations…</p>
        )}
        {error && (
          <p className="text-sm text-red-700">{error}</p>
        )}

        {!isLoading && !error && (
          <>
            <FreshnessPanel />

            <section aria-labelledby="available-heading" className="space-y-3">
              <h2 id="available-heading" className="text-[11px] font-bold tracking-widest uppercase text-emerald-600">
                Available
              </h2>
              {available.length === 0 ? (
                <p className="text-sm text-gray-400">No available integrations.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {available.map((p) => (
                    <IntegrationCard key={p.slug} p={p} />
                  ))}
                </div>
              )}
            </section>

            {comingSoon.length > 0 && (
              <section aria-labelledby="coming-soon-heading" className="space-y-3">
                <h2 id="coming-soon-heading" className="text-[11px] font-bold tracking-widest uppercase text-gray-400">
                  Coming soon
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {comingSoon.map((p) => (
                    <IntegrationCard key={p.slug} p={p} />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </>
  );
}
