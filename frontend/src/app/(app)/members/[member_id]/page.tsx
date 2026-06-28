"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Breadcrumbs, ORIGINS } from "@/components/ui/breadcrumbs";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import {
  Avatar,
  Card,
  CardHeader,
  CardBody,
  CallHistorySection,
  PerformanceSection,
  SubmissionsSection,
  formatDate,
  humanizeRole,
  statusStyle,
  type TeamMemberDetail,
} from "@/components/members/team-member";

// The route param is `member_id` but the Members page is the team roster, so the
// id is a rep_id (e.g. REP_NELSON_FIGUERIA) served by /members/team/{rep_id}.
export default function MemberDetailPage({ params }: { params: { member_id: string } }) {
  const repId = params.member_id;
  const { isLoading: authLoading } = useAuth();
  const [detail, setDetail] = useState<TeamMemberDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    void (async () => {
      try {
        const d = await apiClient.get<TeamMemberDetail>(`/members/team/${repId}`, { silent: true });
        if (!cancelled) setDetail(d);
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, repId]);

  return (
    <>
      <Header title="Member" />
      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <Breadcrumbs origin={ORIGINS.members} current={detail?.name ?? "Member"} />

        {isLoading ? (
          <p className="text-sm text-gray-400">Loading member…</p>
        ) : error || !detail ? (
          <p className="text-[15px] text-red-700">Member not found.</p>
        ) : (
          <>
            {/* Header card */}
            <Card>
              <CardBody>
                <div className="flex items-start gap-4">
                  <Avatar name={detail.name} size="xl" />
                  <div className="min-w-0 flex-1">
                    <h1 className="text-[22px] font-bold text-gray-900">{detail.name}</h1>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {humanizeRole(detail.role)}
                      {detail.hired_at && ` · since ${formatDate(detail.hired_at)}`}
                      {detail.days_active != null && ` · ${detail.days_active} days active`}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${statusStyle(detail.status).pill}`}
                      >
                        {humanizeRole(detail.status)}
                      </span>
                      {detail.email && <span className="text-[12px] text-gray-400">{detail.email}</span>}
                    </div>
                    {detail.capabilities.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {detail.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600 capitalize"
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button variant="primary" href="/fulfillment-director">
                    Ask Director
                  </Button>
                </div>
              </CardBody>
            </Card>

            {/* Performance */}
            <Card>
              <CardHeader title="Performance" />
              <CardBody className="pt-0">
                <PerformanceSection performance={detail.performance} />
              </CardBody>
            </Card>

            {/* Recent submissions + call history (two columns on wide screens) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader title="Recent Submissions" />
                <CardBody className="pt-0">
                  <SubmissionsSection submissions={detail.recent_submissions} />
                </CardBody>
              </Card>
              <Card>
                <CardHeader title="Call History" />
                <CardBody className="pt-0">
                  <CallHistorySection calls={detail.call_history} />
                </CardBody>
              </Card>
            </div>
          </>
        )}
      </main>
    </>
  );
}
