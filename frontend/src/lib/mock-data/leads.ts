/**
 * ─── MOCK DATA — LEADS ──────────────────────────────────────────────────────
 *
 * Temporary mock data for the Leads page. Remove this entire file and its
 * import in `app/leads/page.tsx` once the real Leads API is connected.
 *
 * To switch to real data:
 *   1. Delete this file (`lib/mock-data/leads.ts`)
 *   2. Replace the `useMockLeads()` call in `app/leads/page.tsx` with a
 *      real API hook (e.g. TanStack Query `useQuery`)
 *   3. Delete the `lib/mock-data/` directory if no other mocks remain
 */

import type { Lead } from "@/types";

export const MOCK_LEADS: Lead[] = [
  {
    id: "a1b2c3d4-0001-4000-8000-000000000001",
    name: "Sarah Mitchell",
    email: "sarah@example.com",
    phone: "+1 (555) 234-5678",
    status: "appointment_set",
    source: "webinar",
    notes: "Attended scaling workshop. Asked about 1-on-1 coaching.",
    createdAt: "2026-03-07T14:22:00Z",
    score: 85,
  },
  {
    id: "a1b2c3d4-0002-4000-8000-000000000002",
    name: "James Torres",
    email: "jtorres@example.com",
    phone: "+1 (555) 876-5432",
    status: "new",
    source: "vsl",
    notes: "Watched full VSL. Replied to follow-up email. Interested in group program.",
    createdAt: "2026-03-06T09:15:00Z",
    score: 62,
  },
  {
    id: "a1b2c3d4-0003-4000-8000-000000000003",
    name: "Priya Nair",
    email: "priya@example.com",
    phone: "+1 (555) 345-6789",
    status: "qualified",
    source: "opt-in",
    notes: "Revenue $250k/yr. Needs help with team hiring + ops. Strong fit.",
    createdAt: "2026-03-05T16:30:00Z",
    score: 78,
  },
  {
    id: "a1b2c3d4-0004-4000-8000-000000000004",
    name: "Derek Owens",
    email: "derek@example.com",
    phone: "+1 (555) 456-7890",
    status: "closed_won",
    source: "webinar",
    notes: "Booked discovery call for Mar 31. Downloaded lead magnet.",
    createdAt: "2026-03-04T11:45:00Z",
    score: 91,
  },
  {
    id: "a1b2c3d4-0005-4000-8000-000000000005",
    name: "Amara Johnson",
    email: "amara@example.com",
    phone: "+1 (555) 567-8901",
    status: "closed_lost",
    source: "vsl",
    notes: "Budget too tight for this quarter. Revisit in Q3.",
    createdAt: "2026-03-03T08:00:00Z",
    score: 44,
  },
  {
    id: "a1b2c3d4-0006-4000-8000-000000000006",
    name: "Carlos Reyes",
    email: "creyes@example.com",
    phone: "+1 (555) 678-9012",
    status: "contacted",
    source: "opt-in",
    notes: "Applied 14 days ago. No response to 3 follow-up attempts.",
    createdAt: "2026-03-03T13:20:00Z",
    score: 70,
  },
  {
    id: "a1b2c3d4-0007-4000-8000-000000000007",
    name: "Rachel Adams",
    email: "rachel.a@example.com",
    phone: "+1 (555) 789-0123",
    status: "new",
    source: "opt-in",
    notes: "Downloaded cash flow calculator. No response to first email yet.",
    createdAt: "2026-03-28T20:10:00Z",
    score: 55,
  },
  {
    id: "a1b2c3d4-0008-4000-8000-000000000008",
    name: "Tyler Brooks",
    email: "tyler.b@example.com",
    phone: "+1 (555) 890-1234",
    status: "contacted",
    source: "webinar",
    notes: "Messaged on Instagram after webinar. Asked about pricing.",
    createdAt: "2026-03-27T18:55:00Z",
    score: 66,
  },
  {
    id: "a1b2c3d4-0009-4000-8000-000000000009",
    name: "Monica Reyes",
    email: "monica.r@example.com",
    phone: "+1 (555) 901-2345",
    status: "qualified",
    source: "vsl",
    notes: "Revenue $180k. Wants to scale to $500k. Has small team of 3.",
    createdAt: "2026-03-26T10:05:00Z",
    score: 80,
  },
  {
    id: "a1b2c3d4-0010-4000-8000-000000000010",
    name: "Chris Donovan",
    email: "chris.d@example.com",
    phone: "+1 (555) 012-3456",
    status: "stale",
    source: "ads",
    notes: "Applied 14 days ago. No response to 3 follow-up attempts.",
    createdAt: "2026-03-15T07:30:00Z",
    score: 30,
  },
  {
    id: "a1b2c3d4-0011-4000-8000-000000000011",
    name: "Natalie Kim",
    email: "natalie.k@example.com",
    phone: "+1 (555) 123-4567",
    status: "new",
    source: "referral",
    notes: "Referred by Derek Wu. Interested in consulting offer.",
    createdAt: "2026-03-29T06:45:00Z",
    score: 72,
  },
  {
    id: "a1b2c3d4-0012-4000-8000-000000000012",
    name: "Omar Hassan",
    email: "omar.h@example.com",
    phone: "+1 (555) 234-5670",
    status: "appointment_set",
    source: "webinar",
    notes: "Booked call for Apr 1. Very engaged during Q&A.",
    createdAt: "2026-03-25T15:15:00Z",
    score: 88,
  },
];

// ─── Summary stats derived from mock data ────────────────────────────────────

export function getMockLeadStats() {
  const total = MOCK_LEADS.length;
  const byStatus: Record<string, number> = {};
  const bySource: Record<string, number> = {};

  for (const lead of MOCK_LEADS) {
    byStatus[lead.status] = (byStatus[lead.status] ?? 0) + 1;
    bySource[lead.source] = (bySource[lead.source] ?? 0) + 1;
  }

  const thisWeek = MOCK_LEADS.filter((l) => {
    const d = new Date(l.createdAt);
    const now = new Date();
    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    return d >= weekAgo;
  }).length;

  return { total, thisWeek, byStatus, bySource };
}

// ─── KPI Stats ────────────────────────────────────────────────────────────────

export interface LeadsKpiStat {
  label: string;
  value: string;
  badgeLabel: string;
  badgeDirection: "up" | "down";
  subtitle: string;
  borderColor: string;
}

export const LEADS_KPI_STATS: LeadsKpiStat[] = [
  {
    label: "Total Leads",
    value: "1,247",
    badgeLabel: "14%",
    badgeDirection: "up",
    subtitle: "All time",
    borderColor: "#3B82F6",
  },
  {
    label: "This Week",
    value: "47",
    badgeLabel: "9%",
    badgeDirection: "up",
    subtitle: "Mar 24 – Mar 30",
    borderColor: "#F59E0B",
  },
  {
    label: "Conversion Rate",
    value: "12.3%",
    badgeLabel: "1.2pt",
    badgeDirection: "up",
    subtitle: "Lead to sale",
    borderColor: "#10B981",
  },
  {
    label: "Active Applications",
    value: "23",
    badgeLabel: "4",
    badgeDirection: "down",
    subtitle: "Awaiting review",
    borderColor: "#F97316",
  },
];

// ─── Lead Volume Chart Data ───────────────────────────────────────────────────

export interface ChartDataPoint {
  label: string;
  value: number;
}

export const LEAD_VOLUME_DATA: ChartDataPoint[] = [
  { label: "Wk 1", value: 32 },
  { label: "Wk 2", value: 38 },
  { label: "Wk 3", value: 35 },
  { label: "Wk 4", value: 48 },
  { label: "Wk 5", value: 42 },
  { label: "Wk 6", value: 55 },
  { label: "Wk 7", value: 50 },
  { label: "Now", value: 65 },
];

// ─── Source Breakdown ─────────────────────────────────────────────────────────

export interface SourceSegment {
  label: string;
  percentage: number;
  count: number;
  color: string;
}

export const SOURCE_BREAKDOWN: SourceSegment[] = [
  { label: "Webinar", percentage: 45, count: 561, color: "#F59E0B" },
  { label: "VSL", percentage: 30, count: 374, color: "#3B82F6" },
  { label: "Opt-in", percentage: 25, count: 312, color: "#10B981" },
];

export const SOURCE_BEST_CLOSE_RATE = {
  label: "Webinar",
  rate: "18.4%",
  color: "#92400E",
};

// ─── Sales Funnel Data ────────────────────────────────────────────────────────

export interface FunnelStage {
  label: string;
  count: number;
  color: string;
  widthPercent: number;
  conversionRate?: string;
}

export const FUNNEL_STAGES: FunnelStage[] = [
  {
    label: "Leads",
    count: 1247,
    color: "#3B82F6",
    widthPercent: 100,
  },
  {
    label: "Appointments",
    count: 487,
    color: "#8B5CF6",
    widthPercent: 70,
    conversionRate: "39.1%",
  },
  {
    label: "Applications",
    count: 198,
    color: "#F59E0B",
    widthPercent: 48,
    conversionRate: "40.7%",
  },
  {
    label: "Sales",
    count: 62,
    color: "#10B981",
    widthPercent: 30,
    conversionRate: "31.3%",
  },
];

export const FUNNEL_SUMMARY = {
  overallConversion: "4.97%",
  avgDealValue: "$2,980",
};

// ─── Table Row Data ───────────────────────────────────────────────────────────

export const TABLE_DISPLAY_LEADS = MOCK_LEADS.slice(0, 6);
