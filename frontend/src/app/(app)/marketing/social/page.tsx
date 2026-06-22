"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// ─── API response type ───────────────────────────────────────────────────────

interface PlatformMetricData {
  platform: string; // "instagram" | "facebook" | "tiktok" | "linkedin"
  connected: boolean;
  provider_status: string; // "available" | "coming_soon"
  followers: number | null;
  posts_count: number | null;
  engagement_rate: number | null;
}

interface InstagramPostData {
  id: string;
  platform: string;
  caption: string | null;
  permalink: string | null;
  media_type: string | null;
  is_reel: boolean;
  posted_at: string | null;
  likes_count: number | null;
  comments_count: number | null;
  saves_count: number | null;
  reach: number | null;
  views: number | null;
  engagement_rate: number | null;
}

interface SocialCommentData {
  id: string;
  platform: string;
  comment_text: string;
  commented_at: string | null;
}

interface SocialData {
  posts: number;
  engagement: number;
  followers: number;
  by_platform: PlatformMetricData[];
  top_content: InstagramPostData[];
  recent_comments: SocialCommentData[];
  generated_at: string;
}

// ─── Platform metrics ─────────────────────────────────────────────────────────

interface PlatformRow {
  name: string;
  slug: string;
  icon: string;
}

// Display scaffold (icons + order). Live values are merged in from
// data.by_platform by slug; platforms with no synced row show "—".
const PLATFORMS: PlatformRow[] = [
  { name: "Instagram", slug: "instagram", icon: "📷" },
  { name: "Facebook", slug: "facebook", icon: "📘" },
  { name: "TikTok", slug: "tiktok", icon: "🎵" },
  { name: "LinkedIn", slug: "linkedin", icon: "💼" },
];

// ─── Platform metrics card ────────────────────────────────────────────────────

function PlatformMetricsCard({ data }: { data: SocialData | null }) {
  const byPlatform = new Map(
    (data?.by_platform ?? []).map((p) => [p.platform, p]),
  );

  return (
    <Card>
      <CardHeader
        title="Platform Breakdown"
        action={<span className="text-xs text-gray-400">Last 30 days</span>}
      />
      <CardBody noPadding>
        <div className="divide-y divide-gray-100">
          {PLATFORMS.map((platform) => {
            const live = byPlatform.get(platform.slug);
            const connected = live?.connected ?? false;
            const comingSoon = live?.provider_status === "coming_soon";

            return (
              <div
                key={platform.name}
                className="flex items-center gap-4 px-5 py-3"
              >
                <span className="text-xl leading-none flex-shrink-0" aria-hidden="true">
                  {platform.icon}
                </span>
                <span className="text-sm font-medium text-gray-800 w-24 flex-shrink-0">
                  {platform.name}
                </span>

                {connected ? (
                  // Connected → live metrics
                  <div className="flex flex-1 gap-6">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                        Followers
                      </span>
                      <span className="text-sm font-semibold text-gray-700 tabular-nums">
                        {live?.followers != null ? live.followers.toLocaleString() : "—"}
                      </span>
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                        Posts
                      </span>
                      <span className="text-sm font-semibold text-gray-700 tabular-nums">
                        {live?.posts_count != null ? live.posts_count.toLocaleString() : "—"}
                      </span>
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                        Engagement
                      </span>
                      <span className="text-sm font-semibold text-gray-700 tabular-nums">
                        {live?.engagement_rate != null
                          ? `${live.engagement_rate.toFixed(1)}%`
                          : "—"}
                      </span>
                    </div>
                  </div>
                ) : (
                  // Not connected → Connect button (available) or Coming-soon tag
                  <div className="flex flex-1 items-center justify-end">
                    {comingSoon ? (
                      <span className="text-xs font-medium text-gray-400 bg-gray-100 rounded-full px-3 py-1">
                        Coming soon
                      </span>
                    ) : (
                      <Link
                        href={`/integrations/${platform.slug}`}
                        className="text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-full px-3 py-1 transition-colors"
                      >
                        Connect →
                      </Link>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Schedule a Post CTA card ─────────────────────────────────────────────────

function ScheduleCtaCard() {
  return (
    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex flex-col items-start gap-4">
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center w-12 h-12 rounded-full flex-shrink-0 shadow-sm"
          style={{ background: "linear-gradient(135deg, #10B981 0%, #059669 100%)" }}
          aria-hidden="true"
        >
          <span className="text-xl leading-none">📅</span>
        </div>
        <div>
          <h2 className="text-sm font-bold text-gray-900">Schedule a Post</h2>
          <p className="text-xs text-emerald-700 font-medium mt-0.5">
            Plan and schedule your next post
          </p>
        </div>
      </div>
      <p className="text-sm text-gray-600 leading-relaxed">
        Use the AI Script Generator to create platform-optimized content, then
        schedule your posts across all channels.
      </p>
      <Button variant="primary" href="/marketing/social/scripts">
        Generate Script <span aria-hidden="true">→</span>
      </Button>
    </div>
  );
}

// ─── Recent posts empty state ─────────────────────────────────────────────────

function RecentPostsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        📱
      </span>
      <p className="text-sm font-medium text-gray-500">No recent posts.</p>
      <p className="text-xs text-gray-400">
        Posts will appear here once content is scheduled.
      </p>
    </div>
  );
}

// ─── Recent posts card ────────────────────────────────────────────────────────

function formatPostDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function metric(value: number | null): string {
  return value != null ? value.toLocaleString("en-US") : "—";
}

function RecentPostRow({ post }: { post: InstagramPostData }) {
  const caption = post.caption?.trim() || "(no caption)";
  const inner = (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
            {post.is_reel ? "Reel" : post.media_type || "Post"}
          </span>
          <span className="text-xs text-gray-400">{formatPostDate(post.posted_at)}</span>
        </div>
        <p className="mt-1 text-sm text-gray-700 line-clamp-2">{caption}</p>
      </div>
      <div className="flex shrink-0 gap-4 text-xs text-gray-500 tabular-nums">
        <span title="Reach">👁 {metric(post.reach)}</span>
        <span title="Likes">❤️ {metric(post.likes_count)}</span>
        <span title="Comments">💬 {metric(post.comments_count)}</span>
        <span title="Saves">🔖 {metric(post.saves_count)}</span>
        <span title="Engagement rate" className="font-semibold text-gray-700">
          {post.engagement_rate != null ? `${post.engagement_rate.toFixed(1)}%` : "—"}
        </span>
      </div>
    </div>
  );
  return post.permalink ? (
    <a
      href={post.permalink}
      target="_blank"
      rel="noopener noreferrer"
      className="block px-1 -mx-1 rounded-lg hover:bg-gray-50 transition-colors"
    >
      {inner}
    </a>
  ) : (
    <div className="px-1 -mx-1">{inner}</div>
  );
}

function RecentPostsCard({ posts }: { posts: InstagramPostData[] }) {
  return (
    <Card>
      <CardHeader
        title="Recent Posts"
        action={
          <span className="text-xs text-gray-400">
            {posts.length} {posts.length === 1 ? "post" : "posts"}
          </span>
        }
      />
      <CardBody>
        {posts.length === 0 ? (
          <RecentPostsEmptyState />
        ) : (
          <div className="divide-y divide-gray-100">
            {posts.map((p) => (
              <RecentPostRow key={p.id} post={p} />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Recent comments card ─────────────────────────────────────────────────────

function platformDot(platform: string): string {
  if (platform === "instagram") return "#E1306C";
  if (platform === "facebook") return "#1877F2";
  return "#9CA3AF";
}

function RecentCommentsCard({ comments }: { comments: SocialCommentData[] }) {
  return (
    <Card>
      <CardHeader
        title="Recent Comments"
        action={
          <span className="text-xs text-gray-400">voice of customer</span>
        }
      />
      <CardBody>
        {comments.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <span className="text-3xl" aria-hidden="true">💬</span>
            <p className="text-sm font-medium text-gray-500">No comments yet.</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {comments.map((c) => (
              <li key={c.id} className="flex items-start gap-3 py-3">
                <span
                  className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: platformDot(c.platform) }}
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-700">{c.comment_text}</p>
                  <span className="mt-0.5 block text-xs text-gray-400">
                    {c.platform} · {formatPostDate(c.commented_at)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function SocialPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      {/* Heading skeleton */}
      <div>
        <Skeleton className="h-6 w-40" />
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

      {/* Platform breakdown + CTA skeleton */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-3 w-20" />
          </div>
          <div className="divide-y divide-gray-100">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-3">
                <Skeleton className="w-6 h-6 rounded" />
                <Skeleton className="h-4 w-20" />
                <div className="flex flex-1 gap-6">
                  <Skeleton className="h-4 w-14" />
                  <Skeleton className="h-4 w-10" />
                  <Skeleton className="h-4 w-12" />
                </div>
              </div>
            ))}
          </div>
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>

      {/* Recent posts skeleton */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-16" />
        </div>
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Skeleton className="w-10 h-10 rounded-full" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-56" />
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SocialMediaPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<SocialData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<SocialData>("/social", {
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
        <Header title="Social Media" />
        <SocialPageSkeleton />
      </>
    );
  }

  return (
    <>
      <Header title="Social Media" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Social Media</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Platform performance and content overview across all social channels.
          </p>
        </div>

        {/* Row 1: KPI tiles */}
        <section aria-label="Social media KPIs">
          <KpiRow>
            <KpiCard label="Total Followers" value={data ? data.followers.toLocaleString() : "—"} borderColor="#10B981" />
            <KpiCard label="Posts This Month" value={data ? data.posts.toLocaleString() : "—"} borderColor="#10B981" />
            <KpiCard label="Avg Engagement Rate" value={data ? `${data.engagement.toFixed(1)}%` : "—"} borderColor="#10B981" />
            <KpiCard label="Reach MTD" value="—" borderColor="#10B981" />
          </KpiRow>
        </section>

        {/* Row 2: Platform breakdown + Schedule CTA */}
        <div className="grid grid-cols-2 gap-4">
          <PlatformMetricsCard data={data} />
          <ScheduleCtaCard />
        </div>

        {/* Row 3: Recent posts */}
        <RecentPostsCard posts={data?.top_content ?? []} />

        {/* Row 4: Recent comments (voice of customer) */}
        <RecentCommentsCard comments={data?.recent_comments ?? []} />
      </main>
    </>
  );
}
