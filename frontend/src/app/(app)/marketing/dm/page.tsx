"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { FilterBar } from "@/components/ui/filter-bar";
import { PlatformTag } from "@/components/ui/platform-tag";
import { CopyButton, Button } from "@/components/ui/button";
import { FormField, FormInput, FormSelect } from "@/components/ui/form-field";
import { HistoryItem, HistoryList } from "@/components/ui/history-item";
import type { DmData } from "@/types";

// ─── Types ────────────────────────────────────────────────────────────────────

type Platform = "Instagram" | "Facebook";

interface DmTemplate {
  id: string;
  title: string;
  preview: string;
  platforms: Platform[];
  stat: string;
}

interface Conversation {
  id: string;
  name: string;
  preview: string;
  platform: Platform;
}

// ─── Static mock data ─────────────────────────────────────────────────────────

const DM_TEMPLATES: DmTemplate[] = [
  {
    id: "1",
    title: "Cold Outreach — Pain Point Hook",
    preview:
      "Hey {first_name}! I noticed you're in {industry} and wanted to reach out because a lot of people in your space are struggling with...",
    platforms: ["Instagram", "Facebook"],
    stat: "38% reply rate",
  },
  {
    id: "2",
    title: "Follow-up — After Story View",
    preview:
      "Hey {first_name}, saw you checked out my story earlier! Wanted to follow up and share something that might be relevant to what you're working on...",
    platforms: ["Instagram"],
    stat: "52% reply rate",
  },
  {
    id: "3",
    title: "Nurture — Value Drop",
    preview:
      "Hey {first_name}! I've been putting together some resources for people in {industry} that I think could really help you with...",
    platforms: ["Facebook"],
    stat: "41% reply rate",
  },
  {
    id: "4",
    title: "Re-engagement — Inactive Lead",
    preview:
      "Hey {first_name}, it's been a while! I wanted to circle back because I have something new that directly addresses the {pain_point} you mentioned...",
    platforms: ["Instagram", "Facebook"],
    stat: "29% reply rate",
  },
  {
    id: "5",
    title: "Warm Lead — Call Booking",
    preview:
      "Hey {first_name}! Based on our conversation, I think a quick 20-min call could be really valuable. Are you free this week to chat about...",
    platforms: ["Instagram"],
    stat: "61% booking rate",
  },
];

const RECENT_CONVERSATIONS: Conversation[] = [
  {
    id: "1",
    name: "Maria Torres",
    preview: "Replied: 'Yes, tell me more!'",
    platform: "Instagram",
  },
  {
    id: "2",
    name: "Jake Williams",
    preview: "Booked a call",
    platform: "Facebook",
  },
  {
    id: "3",
    name: "Priya Sharma",
    preview: "Opened — awaiting reply",
    platform: "Instagram",
  },
  {
    id: "4",
    name: "Carlos Mendez",
    preview: "Replied: 'What\u2019s the cost?'",
    platform: "Facebook",
  },
];

const AI_GENERATED_PREVIEW =
  "Hey {first_name}! I noticed you're building something exciting in {industry}. I've been helping founders like you solve {pain_point} and wanted to share a quick insight that could help. Would love to connect — are you open to a quick chat this week?";

// ─── DM Template Library card ─────────────────────────────────────────────────

function TemplateLibraryCard() {
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const filtered = DM_TEMPLATES.filter((t) => {
    const matchesSearch =
      search === "" ||
      t.title.toLowerCase().includes(search.toLowerCase()) ||
      t.preview.toLowerCase().includes(search.toLowerCase());
    const matchesPlatform =
      platformFilter === "all" ||
      t.platforms.some((p) => p.toLowerCase() === platformFilter);
    const matchesType =
      typeFilter === "all" ||
      t.title.toLowerCase().includes(typeFilter.toLowerCase());
    return matchesSearch && matchesPlatform && matchesType;
  });

  return (
    <Card>
      <CardHeader
        title="DM Template Library"
        action={
          <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
            12 templates
          </span>
        }
      />

      {/* Filter bar */}
      <div className="px-5 py-3 border-b border-gray-100">
        <FilterBar>
          <FormInput
            type="text"
            placeholder="Search templates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-0"
          />
          <FormSelect
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
          >
            <option value="all">All Platforms</option>
            <option value="instagram">Instagram</option>
            <option value="facebook">Facebook</option>
          </FormSelect>
          <FormSelect
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All Types</option>
            <option value="cold outreach">Cold Outreach</option>
            <option value="follow-up">Follow-up</option>
            <option value="nurture">Nurture</option>
            <option value="re-engagement">Re-engagement</option>
            <option value="warm lead">Call Booking</option>
          </FormSelect>
        </FilterBar>
      </div>

      {/* Template list */}
      <div className="divide-y divide-gray-100 flex-1">
        {filtered.length === 0 ? (
          <div className="py-10 text-center text-sm text-gray-400">
            No templates match your filters.
          </div>
        ) : (
          filtered.map((template) => (
            <div key={template.id} className="px-5 py-4 flex flex-col gap-2">
              <span className="text-sm font-semibold text-gray-900">{template.title}</span>
              <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">
                {template.preview}
              </p>
              <div className="flex items-center justify-between mt-1">
                <div className="flex items-center gap-1.5">
                  {template.platforms.map((p) => (
                    <PlatformTag
                      key={p}
                      platform={p.toLowerCase() as "instagram" | "facebook"}
                      short
                    />
                  ))}
                  <span className="text-[11px] text-gray-400 ml-1">{template.stat}</span>
                </div>
                <CopyButton text={template.preview} />
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

// ─── AI Template Generator card ───────────────────────────────────────────────

function AiTemplateGeneratorCard() {
  const [platform, setPlatform] = useState("instagram");
  const [templateType, setTemplateType] = useState("cold_outreach");
  const [painPoint, setPainPoint] = useState("");
  const [tone, setTone] = useState("casual");
  const [showPreview, setShowPreview] = useState(false);

  function handleGenerate() {
    setShowPreview(true);
  }

  return (
    <Card>
      <CardHeader title="AI Template Generator" />
      <CardBody className="flex flex-col gap-3">
        <FormField label="Platform">
          <FormSelect value={platform} onChange={(e) => setPlatform(e.target.value)}>
            <option value="instagram">Instagram</option>
            <option value="facebook">Facebook</option>
            <option value="both">Both</option>
          </FormSelect>
        </FormField>

        <FormField label="Template Type">
          <FormSelect value={templateType} onChange={(e) => setTemplateType(e.target.value)}>
            <option value="cold_outreach">Cold Outreach</option>
            <option value="follow_up">Follow-up</option>
            <option value="nurture">Nurture</option>
            <option value="re_engagement">Re-engagement</option>
            <option value="call_booking">Call Booking</option>
          </FormSelect>
        </FormField>

        <FormField label="Target Pain Point">
          <FormInput
            type="text"
            placeholder="e.g. not enough qualified leads"
            value={painPoint}
            onChange={(e) => setPainPoint(e.target.value)}
          />
        </FormField>

        <FormField label="Tone">
          <FormSelect value={tone} onChange={(e) => setTone(e.target.value)}>
            <option value="casual">Casual &amp; Friendly</option>
            <option value="professional">Professional</option>
            <option value="direct">Direct &amp; Bold</option>
            <option value="empathetic">Empathetic</option>
          </FormSelect>
        </FormField>

        <Button variant="primary" fullWidth onClick={handleGenerate} className="mt-1">
          Generate Template with AI
        </Button>

        {/* AI Generated Preview */}
        {showPreview && (
          <div className="mt-1 rounded-lg bg-gray-50 border border-gray-200 p-4 flex flex-col gap-3">
            <p className="text-xs text-gray-600 italic leading-relaxed">
              {AI_GENERATED_PREVIEW}
            </p>
            <div className="flex flex-col gap-1.5">
              <CopyButton text={AI_GENERATED_PREVIEW} label="Copy to Clipboard" className="w-full py-1.5 text-xs rounded-lg" />
              <Button variant="primary" fullWidth className="text-xs py-1.5">
                Save as Template
              </Button>
              <Button variant="ghost" fullWidth onClick={handleGenerate} className="text-xs py-1.5">
                Regenerate
              </Button>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Recent Conversations card ────────────────────────────────────────────────

function RecentConversationsCard() {
  return (
    <Card>
      <CardHeader title="Recent Conversations" />
      <CardBody noPadding>
        <HistoryList>
          {RECENT_CONVERSATIONS.map((conv) => (
            <HistoryItem
              key={conv.id}
              dotColor={conv.platform === "Instagram" ? "#C13584" : "#1877F2"}
              trailing={
                <PlatformTag
                  platform={conv.platform.toLowerCase() as "instagram" | "facebook"}
                  short
                />
              }
            >
              <span className="text-sm font-semibold text-gray-900 block truncate">
                {conv.name}
              </span>
              <p className="text-xs text-gray-500 mt-0.5 truncate">{conv.preview}</p>
            </HistoryItem>
          ))}
        </HistoryList>
      </CardBody>
    </Card>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function DmPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      {/* Top bar skeleton */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-40" />
        <div className="flex items-center gap-3">
          <Skeleton className="h-8 w-32 rounded-lg" />
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
      <div className="flex gap-5 items-start">
        <div className="flex-1 min-w-0 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-5 w-20 rounded-full" />
          </div>
          <div className="px-5 py-3 border-b border-gray-100">
            <Skeleton className="h-8 w-full rounded-lg" />
          </div>
          {[1, 2, 3].map((i) => (
            <div key={i} className="px-5 py-4 border-b border-gray-100 flex flex-col gap-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          ))}
        </div>
        <div className="flex-shrink-0 w-[340px] flex flex-col gap-5">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DmPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<DmData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<DmData>("/dm", { silent: true });
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
        <Header title="Direct Messages" />
        <DmPageSkeleton />
      </>
    );
  }

  return (
    <>
      <Header title="Direct Messages" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Top bar */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">Direct Messages</h1>
          <div className="flex items-center gap-3">
            <Button variant="ghost">
              All Platforms
              <svg
                className="w-3.5 h-3.5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </Button>
            <Button variant="primary" href="/marketing/dm/templates">
              + New Template
            </Button>
          </div>
        </div>

        {/* KPI row */}
        <KpiRow>
          <KpiCard
            label="Outreach Sent"
            value={data ? data.outreach_sent.toLocaleString() : "—"}
            borderColor="#10B981"
          />
          <KpiCard
            label="Response Rate"
            value={data ? `${data.response_rate.toFixed(1)}%` : "—"}
            borderColor="#3B82F6"
          />
          <KpiCard
            label="Meetings Booked"
            value={data ? data.meetings_booked.toLocaleString() : "—"}
            borderColor="#6366F1"
          />
          <KpiCard
            label="Avg Response Time"
            value="—"
            sub="AI-assisted replies"
            borderColor="#C13584"
          />
        </KpiRow>

        {/* Two-column layout */}
        <div className="flex gap-5 items-start">
          {/* Left column */}
          <div className="flex-1 min-w-0">
            <TemplateLibraryCard />
          </div>

          {/* Right sidebar — 340px */}
          <div className="flex-shrink-0 w-[340px] flex flex-col gap-5">
            <AiTemplateGeneratorCard />
            <RecentConversationsCard />
          </div>
        </div>
      </main>
    </>
  );
}
