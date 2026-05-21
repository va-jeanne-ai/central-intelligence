"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { showError, showSuccess } from "@/lib/toast";
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
  audience_name: string | null;
  segment_text: string | null;
  body_html: string | null;
  archive_url: string | null;
}

interface EmailData {
  campaigns: number;
  avg_open_rate: number;
  avg_click_rate: number;
  generated_at: string;
  recent_campaigns: EmailCampaignRow[];
  drafts: EmailCampaignRow[];
  archived: EmailCampaignRow[];
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

function CampaignDetail({ c }: { c: EmailCampaignRow }) {
  const hasExtras =
    c.audience_name || c.segment_text || c.body_html || c.archive_url || c.subject;
  if (!hasExtras) {
    return (
      <div className="px-5 pb-4 text-xs text-gray-400 italic">
        No additional details available for this campaign.
      </div>
    );
  }
  return (
    <div className="px-5 pb-4 space-y-3 bg-gray-50 border-t border-gray-100">
      {/* Metadata grid */}
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-xs pt-3">
        {c.subject && (
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Subject</dt>
            <dd className="text-gray-800 mt-0.5">{c.subject}</dd>
          </div>
        )}
        {c.audience_name && (
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Audience</dt>
            <dd className="text-gray-800 mt-0.5">{c.audience_name}</dd>
          </div>
        )}
        {c.segment_text && (
          <div className="sm:col-span-2">
            <dt className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Segment</dt>
            <dd className="text-gray-800 mt-0.5">{c.segment_text}</dd>
          </div>
        )}
      </dl>

      {/* Body — sandboxed iframe so embedded scripts/links can't touch the host page */}
      {c.body_html ? (
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Body</span>
            {c.archive_url && (
              <a
                href={c.archive_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
              >
                Open in Mailchimp ↗
              </a>
            )}
          </div>
          <iframe
            title={`Campaign body — ${c.name}`}
            sandbox=""
            srcDoc={c.body_html}
            className="w-full h-96 bg-white rounded border border-gray-200"
          />
        </div>
      ) : c.archive_url ? (
        <div>
          <a
            href={c.archive_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
          >
            Open in Mailchimp ↗
          </a>
        </div>
      ) : null}
    </div>
  );
}

function DraftRow({
  draft,
  onChange,
}: {
  draft: EmailCampaignRow;
  onChange: () => Promise<void> | void;
}) {
  const router = useRouter();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState(draft.name);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDuplicating, setIsDuplicating] = useState(false);

  // Reset the local rename buffer if the upstream row changes.
  useEffect(() => {
    if (!isRenaming) setNameDraft(draft.name);
  }, [draft.name, isRenaming]);

  async function saveRename() {
    const trimmed = nameDraft.trim();
    if (!trimmed || trimmed === draft.name) {
      setIsRenaming(false);
      setNameDraft(draft.name);
      return;
    }
    setIsSaving(true);
    try {
      await apiClient.patch(
        `/email/campaigns/${draft.id}`,
        { name: trimmed },
        { silent: true },
      );
      showSuccess("Renamed.");
      setIsRenaming(false);
      await onChange();
    } catch (err) {
      showError(err instanceof Error ? err.message : "Rename failed.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete "${draft.name}"? This can't be undone from the UI.`)) {
      return;
    }
    setIsDeleting(true);
    try {
      await apiClient.delete(`/email/campaigns/${draft.id}`, { silent: true });
      showSuccess("Draft deleted.");
      await onChange();
    } catch (err) {
      showError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleDuplicate() {
    setIsDuplicating(true);
    try {
      const res = await apiClient.post<{ id: string }>(
        `/email/campaigns/${draft.id}/duplicate`,
        {},
        { silent: true },
      );
      showSuccess("Draft duplicated. Opening the copy…");
      router.push(`/marketing/email/compose?draft_id=${res.id}`);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Duplicate failed.");
      setIsDuplicating(false);
    }
    // Don't reset isDuplicating on success — we're navigating away.
  }

  return (
    <div>
      <div className="w-full px-5 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors">
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="shrink-0 text-gray-400 text-xs hover:text-gray-600"
          aria-label="Preview draft"
          aria-expanded={isExpanded}
        >
          <span
            className={`inline-block transition-transform ${isExpanded ? "rotate-90" : ""}`}
          >
            ▶
          </span>
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {isRenaming ? (
              <input
                type="text"
                value={nameDraft}
                autoFocus
                disabled={isSaving}
                onChange={(e) => setNameDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void saveRename();
                  if (e.key === "Escape") {
                    setIsRenaming(false);
                    setNameDraft(draft.name);
                  }
                }}
                onBlur={() => void saveRename()}
                className="text-sm font-medium text-gray-900 border border-indigo-300 rounded px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-indigo-300/50 min-w-[200px]"
              />
            ) : (
              <button
                type="button"
                onClick={() => setIsRenaming(true)}
                className="text-sm font-medium text-gray-900 truncate hover:bg-amber-50/60 rounded px-1 -mx-1 transition-colors text-left"
                title="Click to rename"
              >
                {draft.name}
              </button>
            )}
            <SourcePill source={draft.source} />
            <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
              Draft
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5 truncate">
            {draft.subject ?? "(no subject)"}
            {draft.audience_name && ` · ${draft.audience_name}`}
          </p>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDuplicate}
            disabled={isDuplicating}
            title="Duplicate as a new draft"
          >
            {isDuplicating ? "…" : "Duplicate"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            href={`/marketing/email/compose?draft_id=${draft.id}`}
          >
            Edit
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={handleDelete}
            disabled={isDeleting}
            title="Delete draft"
          >
            {isDeleting ? "…" : "Delete"}
          </Button>
        </div>
      </div>
      {isExpanded && <CampaignDetail c={draft} />}
    </div>
  );
}

function DraftsCard({
  drafts,
  onChange,
}: {
  drafts: EmailCampaignRow[];
  onChange: () => Promise<void> | void;
}) {
  if (drafts.length === 0) return null;
  return (
    <Card>
      <CardHeader
        title="Drafts"
        action={
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">
              {drafts.length} draft{drafts.length === 1 ? "" : "s"}
            </span>
            <Button variant="ghost" size="sm" href="/marketing/email/compose">
              + New Draft
            </Button>
          </div>
        }
      />
      <CardBody noPadding>
        <div className="divide-y divide-gray-100">
          {drafts.map((d) => (
            <DraftRow key={d.id} draft={d} onChange={onChange} />
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

function SentRow({
  c,
  onChange,
}: {
  c: EmailCampaignRow;
  onChange: () => Promise<void> | void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);

  async function handleArchive() {
    setIsArchiving(true);
    try {
      await apiClient.post(
        `/email/campaigns/${c.id}/archive`,
        {},
        { silent: true },
      );
      showSuccess("Archived.");
      await onChange();
    } catch (err) {
      showError(err instanceof Error ? err.message : "Archive failed.");
      setIsArchiving(false);
    }
  }

  return (
    <div>
      <div className="w-full px-5 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors">
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="shrink-0 text-gray-400 text-xs hover:text-gray-600"
          aria-expanded={isExpanded}
          aria-label="Preview campaign"
        >
          <span
            className={`inline-block transition-transform ${isExpanded ? "rotate-90" : ""}`}
          >
            ▶
          </span>
        </button>

        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="flex-1 min-w-0 text-left"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-medium text-gray-900 truncate">{c.name}</p>
            <SourcePill source={c.source} />
          </div>
          <p className="text-xs text-gray-500 mt-0.5 truncate">
            {c.subject ?? "(no subject)"} · {formatDate(c.sent_at)}
            {c.audience_name && ` · ${c.audience_name}`}
          </p>
        </button>

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

        <Button
          variant="ghost"
          size="sm"
          onClick={handleArchive}
          disabled={isArchiving}
          title="Archive — hides from this list, can be restored"
          className="shrink-0"
        >
          {isArchiving ? "…" : "Archive"}
        </Button>
      </div>
      {isExpanded && <CampaignDetail c={c} />}
    </div>
  );
}

function RecentCampaignsCard({
  campaigns,
  onChange,
}: {
  campaigns: EmailCampaignRow[];
  onChange: () => Promise<void> | void;
}) {
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
              <SentRow key={c.id} c={c} onChange={onChange} />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function ArchivedRow({
  c,
  onChange,
}: {
  c: EmailCampaignRow;
  onChange: () => Promise<void> | void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  async function handleRestore() {
    setIsRestoring(true);
    try {
      await apiClient.post(
        `/email/campaigns/${c.id}/unarchive`,
        {},
        { silent: true },
      );
      showSuccess("Restored.");
      await onChange();
    } catch (err) {
      showError(err instanceof Error ? err.message : "Restore failed.");
      setIsRestoring(false);
    }
  }

  return (
    <div>
      <div className="w-full px-5 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors">
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="shrink-0 text-gray-400 text-xs hover:text-gray-600"
          aria-expanded={isExpanded}
          aria-label="Preview campaign"
        >
          <span
            className={`inline-block transition-transform ${isExpanded ? "rotate-90" : ""}`}
          >
            ▶
          </span>
        </button>
        <button
          type="button"
          onClick={() => setIsExpanded((v) => !v)}
          className="flex-1 min-w-0 text-left"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-medium text-gray-600 truncate">{c.name}</p>
            <SourcePill source={c.source} />
            <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 border border-gray-200">
              Archived
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5 truncate">
            {c.subject ?? "(no subject)"} · {formatDate(c.sent_at)}
          </p>
        </button>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRestore}
          disabled={isRestoring}
          title="Restore to Recent Campaigns"
          className="shrink-0"
        >
          {isRestoring ? "…" : "Restore"}
        </Button>
      </div>
      {isExpanded && <CampaignDetail c={c} />}
    </div>
  );
}

function ArchivedCard({
  archived,
  onChange,
}: {
  archived: EmailCampaignRow[];
  onChange: () => Promise<void> | void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  if (archived.length === 0) return null;
  return (
    <Card>
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="w-full px-5 py-4 flex items-center justify-between border-b border-gray-100 hover:bg-gray-50 transition-colors text-left"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <span
            className={`text-gray-400 text-xs transition-transform ${isOpen ? "rotate-90" : ""}`}
            aria-hidden
          >
            ▶
          </span>
          <h2 className="text-sm font-bold text-gray-800">Archived</h2>
        </div>
        <span className="text-xs text-gray-400">
          {archived.length} campaign{archived.length === 1 ? "" : "s"}
        </span>
      </button>
      {isOpen && (
        <CardBody noPadding>
          <div className="divide-y divide-gray-100">
            {archived.map((c) => (
              <ArchivedRow key={c.id} c={c} onChange={onChange} />
            ))}
          </div>
        </CardBody>
      )}
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

  // Lifted so child cards can trigger a refresh (after delete / duplicate /
  // rename). Stays stable across renders via useCallback so it's safe to
  // pass as a prop without re-mounting children every render.
  const refresh = useCallback(async () => {
    try {
      const result = await apiClient.get<EmailData>("/email", { silent: true });
      setData(result);
    } catch {
      // On error, data stays as-is — keep showing the previous snapshot.
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    void refresh();
  }, [authLoading, refresh]);

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
        <DraftsCard drafts={data?.drafts ?? []} onChange={refresh} />
        <RecentCampaignsCard campaigns={data?.recent_campaigns ?? []} onChange={refresh} />
        <ArchivedCard archived={data?.archived ?? []} onChange={refresh} />
      </main>
    </>
  );
}
