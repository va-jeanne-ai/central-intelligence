"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Types ────────────────────────────────────────────────────────────────────

type IdeaStatus = "Idea" | "Scheduled" | "Written" | "Sent" | "Archived";
type IdeaPlatform = "Instagram" | "TikTok" | "Email" | "LinkedIn";

interface ContentIdea {
  id: string;
  title: string;
  status: IdeaStatus;
  platform: IdeaPlatform;
  createdAt: string;
}

// ─── Backend response shape ──────────────────────────────────────────────────

interface ApiContentIdea {
  content_id: string;
  insight_id: string | null;
  call_id: string | null;
  content_format: string | null;  // → platform
  content_premise: string | null; // → title
  status: string | null;
  priority_level: string | null;
  idea_score: number | null;
  created_at: string | null;
}

interface ApiContentIdeaListResponse {
  data: ApiContentIdea[];
  pagination: { total: number; page: number; limit: number };
}

const VALID_PLATFORMS: readonly IdeaPlatform[] = ["Instagram", "TikTok", "Email", "LinkedIn"];
const VALID_STATUSES: readonly IdeaStatus[] = ["Idea", "Scheduled", "Written", "Sent", "Archived"];

function normaliseStatus(raw: string | null): IdeaStatus {
  if (raw && VALID_STATUSES.includes(raw as IdeaStatus)) {
    return raw as IdeaStatus;
  }
  // The backend's lifecycle uses lowercase variants too (new / in_progress /
  // used / archived). Map the closest equivalent to the UI's enum.
  switch (raw) {
    case "new": return "Idea";
    case "in_progress": return "Scheduled";
    case "used": return "Sent";
    case "archived": return "Archived";
    default: return "Idea";
  }
}

function normalisePlatform(raw: string | null): IdeaPlatform {
  if (raw && VALID_PLATFORMS.includes(raw as IdeaPlatform)) {
    return raw as IdeaPlatform;
  }
  // Backend may have other `content_format` strings like "Long-form article".
  // Default to Instagram if we can't map; user can edit later when we wire
  // edits. (No idea-status filter loses these because the page only renders
  // the 4 known platforms.)
  return "Instagram";
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

function fromApi(a: ApiContentIdea): ContentIdea {
  return {
    id: a.content_id,
    title: a.content_premise ?? "Untitled idea",
    status: normaliseStatus(a.status),
    platform: normalisePlatform(a.content_format),
    createdAt: formatDate(a.created_at),
  };
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUSES: IdeaStatus[] = ["Idea", "Scheduled", "Written", "Sent", "Archived"];
const PLATFORMS: IdeaPlatform[] = ["Instagram", "TikTok", "Email", "LinkedIn"];

// ─── Status pill colors ───────────────────────────────────────────────────────

function statusPillClasses(status: IdeaStatus): string {
  switch (status) {
    case "Idea":
      return "bg-purple-50 text-purple-700";
    case "Scheduled":
      return "bg-blue-50 text-blue-700";
    case "Written":
      return "bg-green-50 text-green-700";
    case "Sent":
      return "bg-emerald-50 text-emerald-700";
    case "Archived":
      return "bg-gray-100 text-gray-500";
    default:
      return "bg-gray-100 text-gray-500";
  }
}

// ─── Platform pill ────────────────────────────────────────────────────────────

function PlatformPill({ platform }: { platform: IdeaPlatform }) {
  return (
    <span className="text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
      {platform}
    </span>
  );
}

// ─── Status pill ──────────────────────────────────────────────────────────────

function StatusPill({ status }: { status: IdeaStatus }) {
  return (
    <span
      className={`text-[11px] font-medium px-1.5 py-0.5 rounded-full ${statusPillClasses(status)}`}
    >
      {status}
    </span>
  );
}

// ─── Content idea card row ────────────────────────────────────────────────────

function IdeaRow({ idea }: { idea: ContentIdea }) {
  return (
    <div className="flex items-center gap-4 px-5 py-4 border-b border-gray-100 hover:bg-gray-50 transition-colors duration-100">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 truncate">{idea.title}</p>
        <p className="text-xs text-gray-400 mt-0.5">{idea.createdAt}</p>
      </div>
      <PlatformPill platform={idea.platform} />
      <StatusPill status={idea.status} />
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        💡
      </span>
      <p className="text-sm font-medium text-gray-500">No content ideas here yet.</p>
      <p className="text-xs text-gray-400">Add your first idea using the button above.</p>
    </div>
  );
}

// ─── Add idea form ────────────────────────────────────────────────────────────

interface AddIdeaFormProps {
  onSave: (idea: Omit<ContentIdea, "id" | "createdAt">) => void;
  onCancel: () => void;
}

function AddIdeaForm({ onSave, onCancel }: AddIdeaFormProps) {
  const [title, setTitle] = useState("");
  const [platform, setPlatform] = useState<IdeaPlatform>("Instagram");
  const [status, setStatus] = useState<IdeaStatus>("Idea");

  function handleSave() {
    if (title.trim() === "") return;
    onSave({ title: title.trim(), platform, status });
  }

  return (
    <div className="border-b border-gray-100 px-5 py-4 bg-gray-50">
      <p className="text-xs font-bold uppercase tracking-wider text-emerald-600 mb-3">
        New Idea
      </p>
      <div className="flex flex-col gap-3">
        {/* Title */}
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Content idea title…"
          autoFocus
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSave();
            if (e.key === "Escape") onCancel();
          }}
        />
        <div className="flex gap-3">
          {/* Platform */}
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
              Platform
            </label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value as IdeaPlatform)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            >
              {PLATFORMS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          {/* Status */}
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
              Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as IdeaStatus)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={handleSave}
            disabled={title.trim() === ""}
            className="text-sm font-semibold px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-200 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-150"
          >
            Save Idea
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="text-sm font-medium px-4 py-2 border border-gray-200 text-gray-600 hover:bg-white rounded-lg transition-colors duration-150"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Status tab bar ───────────────────────────────────────────────────────────

type TabFilter = "All" | IdeaStatus;

interface StatusTabBarProps {
  activeTab: TabFilter;
  ideas: ContentIdea[];
  onTabChange: (tab: TabFilter) => void;
}

function StatusTabBar({ activeTab, ideas, onTabChange }: StatusTabBarProps) {
  const tabs: TabFilter[] = ["All", ...STATUSES];

  function countFor(tab: TabFilter): number {
    if (tab === "All") return ideas.length;
    return ideas.filter((i) => i.status === tab).length;
  }

  return (
    <div className="flex items-center gap-1 px-5 py-3 border-b border-gray-100 overflow-x-auto">
      {tabs.map((tab) => {
        const count = countFor(tab);
        const isActive = activeTab === tab;
        return (
          <button
            key={tab}
            type="button"
            onClick={() => onTabChange(tab)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors duration-150 ${
              isActive
                ? "bg-emerald-50 text-emerald-700"
                : "text-gray-500 hover:bg-gray-50 hover:text-gray-700"
            }`}
          >
            {tab}
            <span
              className={`text-[11px] font-bold px-1.5 py-0.5 rounded-full ${
                isActive ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"
              }`}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CiContentIdeasPage() {
  const { isLoading: authLoading } = useAuth();
  const [ideas, setIdeas] = useState<ContentIdea[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabFilter>("All");
  const [showAddForm, setShowAddForm] = useState(false);

  const loadIdeas = useCallback(async () => {
    try {
      const result = await apiClient.get<ApiContentIdeaListResponse>(
        "/ci/content-ideas?limit=100",
        { silent: true },
      );
      setIdeas(result.data.map(fromApi));
      setError(null);
    } catch {
      setError("Failed to load content ideas.");
      setIdeas([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    void loadIdeas();
  }, [authLoading, loadIdeas]);

  const filteredIdeas =
    activeTab === "All" ? ideas : ideas.filter((i) => i.status === activeTab);

  async function handleSaveIdea(data: Omit<ContentIdea, "id" | "createdAt">) {
    try {
      await apiClient.post(
        "/ci/content-ideas",
        {
          title: data.title,
          platform: data.platform,
          status: data.status,
        },
        { silent: true },
      );
      // Refresh from server so the new idea has its canonical ID + timestamp.
      await loadIdeas();
      setShowAddForm(false);
      setError(null);
    } catch {
      setError("Failed to save idea. Try again.");
    }
  }

  return (
    <>
      <Header title="Content Ideas" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Content Ideas</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Manage your content pipeline from idea to published.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowAddForm((prev) => !prev)}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95 shadow-sm"
          >
            <span aria-hidden="true">+</span>
            Add Idea
          </button>
        </div>

        {error !== null && (
          <div className="border border-amber-200 bg-amber-50 rounded-lg px-4 py-3">
            <p className="text-xs text-amber-800">{error}</p>
          </div>
        )}

        {/* Ideas list card */}
        <section aria-label="Content ideas list">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Status tab bar */}
            <StatusTabBar
              activeTab={activeTab}
              ideas={ideas}
              onTabChange={setActiveTab}
            />

            {/* Loading state */}
            {isLoading && (
              <p className="px-5 py-4 text-xs text-gray-400">Loading ideas…</p>
            )}

            {/* Inline add form */}
            {showAddForm && (
              <AddIdeaForm
                onSave={handleSaveIdea}
                onCancel={() => setShowAddForm(false)}
              />
            )}

            {/* List */}
            {filteredIdeas.length === 0 ? (
              <EmptyState />
            ) : (
              <div>
                {filteredIdeas.map((idea) => (
                  <IdeaRow key={idea.id} idea={idea} />
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </>
  );
}
