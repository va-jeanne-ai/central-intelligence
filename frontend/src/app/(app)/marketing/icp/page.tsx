"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Backend response shape ───────────────────────────────────────────────────

interface ApiIcpSegment {
  id: string;
  segment: string | null;
  description: string | null;
  demographics: string | null;
  psychographics: string | null;
  pain_summary: string | null;
  goal_summary: string | null;
  buying_triggers: string | null;
  common_objections: string | null;
  is_primary: boolean;
}

interface ApiIcpListResponse {
  segments: ApiIcpSegment[];
  total: number;
}

function fromApi(s: ApiIcpSegment): IcpProfile {
  const painPoints = (s.pain_summary ?? "")
    .split(/[;\n]+/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
  return {
    id: s.id,
    name: s.segment ?? "Untitled segment",
    industry: s.description ?? "—",
    criteria: {
      companySize: s.demographics ?? "—",
      titleRole: s.psychographics ?? "—",
      painPoints: painPoints.length > 0 ? painPoints : ["—"],
    },
    matchScore: s.is_primary ? "Primary" : "—",
  };
}

// ─── Placeholder KPI data ─────────────────────────────────────────────────────

interface KpiTile {
  label: string;
  value: string;
  sub?: string;
}

const KPI_TILES: KpiTile[] = [
  { label: "Active ICPs", value: "3" },
  { label: "Avg Match Score", value: "—" },
  { label: "Leads Matched", value: "—" },
  { label: "Revenue from ICP", value: "—" },
];

// ─── ICP data ─────────────────────────────────────────────────────────────────

interface IcpProfile {
  id: string;
  name: string;
  industry: string;
  criteria: {
    companySize: string;
    titleRole: string;
    painPoints: string[];
  };
  matchScore: string;
}

// ─── Edit state ───────────────────────────────────────────────────────────────

interface EditDraft {
  name: string;
  industry: string;
}

// ─── KPI tile ─────────────────────────────────────────────────────────────────

function KpiTileCard({ tile }: { tile: KpiTile }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
        {tile.label}
      </span>
      <span className="text-2xl font-bold text-gray-900 tabular-nums leading-tight">
        {tile.value}
      </span>
      {tile.sub !== undefined && (
        <span className="text-[11px] font-medium px-1.5 py-0.5 rounded-full self-start bg-emerald-50 text-emerald-700">
          {tile.sub}
        </span>
      )}
    </div>
  );
}

// ─── ICP card (view mode) ─────────────────────────────────────────────────────

interface IcpCardViewProps {
  icp: IcpProfile;
  onEdit: () => void;
}

function IcpCardView({ icp, onEdit }: IcpCardViewProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col">
      {/* Card header */}
      <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1 min-w-0">
          <h3 className="text-sm font-bold text-gray-900 truncate">{icp.name}</h3>
          <span className="inline-flex self-start items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-100">
            {icp.industry}
          </span>
        </div>
        <div className="flex flex-col items-center flex-shrink-0">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-0.5">
            Match
          </span>
          <span className="text-lg font-bold text-gray-900 tabular-nums leading-none">
            {icp.matchScore}%
          </span>
        </div>
      </div>

      {/* Key criteria */}
      <div className="px-5 py-4 flex flex-col gap-3 flex-1">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
            Company Size
          </span>
          <span className="text-sm text-gray-700">{icp.criteria.companySize}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
            Title / Role
          </span>
          <span className="text-sm text-gray-700">{icp.criteria.titleRole}</span>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
            Pain Points
          </span>
          <ul className="flex flex-col gap-1">
            {icp.criteria.painPoints.map((point) => (
              <li key={point} className="flex items-start gap-1.5 text-sm text-gray-700">
                <span className="text-emerald-500 mt-0.5 flex-shrink-0" aria-hidden="true">
                  •
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Action buttons */}
      <div className="px-5 py-3 border-t border-gray-100 flex items-center gap-2">
        <button
          type="button"
          onClick={onEdit}
          className="flex-1 inline-flex items-center justify-center px-3 py-2 text-xs font-semibold rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors duration-150 active:scale-95"
        >
          Edit
        </button>
        <button
          type="button"
          className="flex-1 inline-flex items-center justify-center px-3 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition-colors duration-150 active:scale-95 shadow-sm"
        >
          View Leads
        </button>
      </div>
    </div>
  );
}

// ─── ICP card (edit mode) ─────────────────────────────────────────────────────

interface IcpCardEditProps {
  icp: IcpProfile;
  draft: EditDraft;
  onDraftChange: (draft: EditDraft) => void;
  onSave: () => void;
  onCancel: () => void;
}

function IcpCardEdit({ icp, draft, onDraftChange, onSave, onCancel }: IcpCardEditProps) {
  return (
    <div className="bg-white rounded-xl border border-emerald-300 shadow-sm ring-1 ring-emerald-100 flex flex-col">
      {/* Card header */}
      <div className="px-5 py-4 border-b border-gray-100">
        <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 mb-3">
          Editing ICP
        </p>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label
              htmlFor={`icp-name-${icp.id}`}
              className="text-[10px] font-bold uppercase tracking-wider text-gray-500"
            >
              ICP Name
            </label>
            <input
              id={`icp-name-${icp.id}`}
              type="text"
              value={draft.name}
              onChange={(e) => onDraftChange({ ...draft, name: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 text-gray-900 bg-white transition-shadow"
              placeholder="e.g. SMB SaaS Founder"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label
              htmlFor={`icp-industry-${icp.id}`}
              className="text-[10px] font-bold uppercase tracking-wider text-gray-500"
            >
              Industry
            </label>
            <input
              id={`icp-industry-${icp.id}`}
              type="text"
              value={draft.industry}
              onChange={(e) => onDraftChange({ ...draft, industry: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 text-gray-900 bg-white transition-shadow"
              placeholder="e.g. SaaS"
            />
          </div>
        </div>
      </div>

      {/* Criteria read-only hint */}
      <div className="px-5 py-4 flex-1">
        <p className="text-xs text-gray-400">
          Other criteria fields (company size, role, pain points) are editable in the full profile view.
        </p>
      </div>

      {/* Save / Cancel */}
      <div className="px-5 py-3 border-t border-gray-100 flex items-center gap-2">
        <button
          type="button"
          onClick={onSave}
          className="flex-1 inline-flex items-center justify-center px-3 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition-colors duration-150 active:scale-95 shadow-sm"
        >
          Save
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 inline-flex items-center justify-center px-3 py-2 text-xs font-semibold rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors duration-150 active:scale-95"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ─── New ICP form card ────────────────────────────────────────────────────────

interface NewIcpFormCardProps {
  onSave: (name: string, industry: string) => void;
  onCancel: () => void;
}

function NewIcpFormCard({ onSave, onCancel }: NewIcpFormCardProps) {
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");

  return (
    <div className="bg-emerald-50 rounded-xl border border-emerald-300 shadow-sm ring-1 ring-emerald-100 flex flex-col">
      <div className="px-5 py-4 border-b border-emerald-200">
        <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 mb-3">
          New ICP
        </p>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="new-icp-name"
              className="text-[10px] font-bold uppercase tracking-wider text-gray-500"
            >
              ICP Name
            </label>
            <input
              id="new-icp-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 text-gray-900 bg-white transition-shadow"
              placeholder="e.g. Growth-Stage CMO"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label
              htmlFor="new-icp-industry"
              className="text-[10px] font-bold uppercase tracking-wider text-gray-500"
            >
              Industry
            </label>
            <input
              id="new-icp-industry"
              type="text"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 text-gray-900 bg-white transition-shadow"
              placeholder="e.g. Marketing"
            />
          </div>
        </div>
      </div>
      <div className="px-5 py-4 flex-1">
        <p className="text-xs text-gray-500">
          Fill in basic details to create the profile. You can add criteria after saving.
        </p>
      </div>
      <div className="px-5 py-3 border-t border-emerald-200 flex items-center gap-2">
        <button
          type="button"
          onClick={() => onSave(name.trim(), industry.trim())}
          disabled={!name.trim()}
          className="flex-1 inline-flex items-center justify-center px-3 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors duration-150 active:scale-95 shadow-sm"
        >
          Save ICP
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 inline-flex items-center justify-center px-3 py-2 text-xs font-semibold rounded-lg border border-gray-300 text-gray-700 hover:bg-white transition-colors duration-150 active:scale-95"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ─── ICP cards section ────────────────────────────────────────────────────────

function IcpCardsSection() {
  const { isLoading: authLoading } = useAuth();
  const [icps, setIcps] = useState<IcpProfile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDrafts, setEditDrafts] = useState<Record<string, EditDraft>>({});
  const [showNewForm, setShowNewForm] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const loadIcps = useCallback(async () => {
    try {
      const result = await apiClient.get<ApiIcpListResponse>("/icp", { silent: true });
      setIcps(result.segments.map(fromApi));
      setError(null);
    } catch {
      setError("Failed to load ICPs.");
      setIcps([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    void loadIcps();
  }, [authLoading, loadIcps]);

  function handleEditStart(icp: IcpProfile) {
    setEditingId(icp.id);
    setEditDrafts((prev) => ({
      ...prev,
      [icp.id]: { name: icp.name, industry: icp.industry },
    }));
  }

  async function handleEditSave(id: string) {
    const draft = editDrafts[id];
    if (!draft) return;
    // Frontend `name` maps to backend `segment`; `industry` maps to `description`.
    // The other backend fields (demographics, psychographics, pain_summary, etc.)
    // aren't editable from this UI yet — they pass through untouched on the
    // server side because PUT /icp/{id} accepts a partial update.
    try {
      await apiClient.put(`/icp/${id}`, {
        segment: draft.name.trim() || undefined,
        description: draft.industry.trim() || undefined,
      }, { silent: true });
      // Refresh the list so we render canonical server state.
      await loadIcps();
    } catch {
      setError("Failed to save ICP. Try again.");
    }
    setEditingId(null);
  }

  function handleEditCancel() {
    setEditingId(null);
  }

  async function handleGenerateIcps() {
    setIsGenerating(true);
    setError(null);
    try {
      // POST /icp/generate enqueues a Celery task; backend returns
      // {task_id, status, message}. The task uses Claude to synthesise
      // ICP segments from real intelligence data (pain points, calls, etc.).
      await apiClient.post(
        "/icp/generate",
        { offer_type: "Coaching", max_offers: 3 },
        { silent: true, timeout: 120_000 },
      );
      // The task is async — give the worker a moment, then refresh.
      // For now: show a banner and let the user refresh manually if they
      // don't see new rows. (Polling /icp/generate/{task_id}/status is the
      // proper UX but requires more wiring.)
      setError("ICP generation started. Refresh in ~30s to see new segments.");
    } catch {
      setError("Failed to start ICP generation.");
    } finally {
      setIsGenerating(false);
      setShowNewForm(false);
    }
  }

  // Kept for back-compat with the existing NewIcpFormCard prop signature.
  // Adds the new ICP client-side only; "Generate ICPs" is the persistent path.
  function handleNewIcpSave(name: string, industry: string) {
    if (!name) return;
    const newIcp: IcpProfile = {
      id: `icp-local-${Date.now()}`,
      name,
      industry: industry || "—",
      criteria: { companySize: "—", titleRole: "—", painPoints: ["—"] },
      matchScore: "—",
    };
    setIcps((prev) => [...prev, newIcp]);
    setShowNewForm(false);
  }

  return (
    <section aria-label="ICP cards">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Section header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-900">Ideal Customer Profiles</h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void handleGenerateIcps()}
              disabled={isGenerating}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150 active:scale-95"
            >
              {isGenerating ? "Generating…" : "✨ Generate ICPs"}
            </button>
            <button
              type="button"
              onClick={() => setShowNewForm(true)}
              disabled={showNewForm}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg border border-emerald-500 text-emerald-700 hover:bg-emerald-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150 active:scale-95"
            >
              + Add ICP
            </button>
          </div>
        </div>

        {error !== null && (
          <div className="border-b border-amber-200 bg-amber-50 px-5 py-2">
            <p className="text-xs text-amber-800">{error}</p>
          </div>
        )}

        {/* Cards grid */}
        <div className="p-5">
          {isLoading ? (
            <p className="text-xs text-gray-400">Loading ICPs…</p>
          ) : (
          <div className="grid grid-cols-3 gap-4">
            {icps.map((icp) =>
              editingId === icp.id ? (
                <IcpCardEdit
                  key={icp.id}
                  icp={icp}
                  draft={editDrafts[icp.id] ?? { name: icp.name, industry: icp.industry }}
                  onDraftChange={(draft) =>
                    setEditDrafts((prev) => ({ ...prev, [icp.id]: draft }))
                  }
                  onSave={() => handleEditSave(icp.id)}
                  onCancel={handleEditCancel}
                />
              ) : (
                <IcpCardView
                  key={icp.id}
                  icp={icp}
                  onEdit={() => handleEditStart(icp)}
                />
              )
            )}

            {showNewForm && (
              <NewIcpFormCard
                onSave={handleNewIcpSave}
                onCancel={() => setShowNewForm(false)}
              />
            )}
          </div>
          )}
        </div>
      </div>
    </section>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IcpPage() {
  return (
    <>
      <Header title="ICP Management" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">ICP Management</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            View, edit, and manage your Ideal Customer Profiles.{" "}
            <span className="inline-flex items-center gap-1 text-gray-400">
              <span aria-hidden="true">🕐</span>
              Last updated: —
            </span>
          </p>
        </div>

        {/* Row 1: KPI tiles */}
        <section aria-label="ICP KPIs">
          <div className="grid grid-cols-4 gap-4">
            {KPI_TILES.map((tile) => (
              <KpiTileCard key={tile.label} tile={tile} />
            ))}
          </div>
        </section>

        {/* Row 2: ICP cards */}
        <IcpCardsSection />
      </main>
    </>
  );
}
