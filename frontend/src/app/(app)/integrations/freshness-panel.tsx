"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Card, CardBody, CardHeader } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { showError, showInfo, showSuccess } from "@/lib/toast";
import type {
  FreshnessResponse,
  FreshnessSourceResult,
  FreshnessVerdict,
  SyncStatusResponse,
  SyncTriggerResponse,
} from "@/types";

// A WGR sync runs in the background and can outlive the page. We persist the
// task id + when it was queued in localStorage so a refresh (or navigating
// away and back) re-attaches to the in-flight sync and keeps showing the
// indicator. Cleared when the task reaches a terminal state.
const WGR_TASK_STORAGE_KEY = "ci.wgrSyncTask";
const POLL_INTERVAL_MS = 4000;

interface PersistedSyncTask {
  taskId: string;
  queuedAt: number; // epoch ms
}

function readPersistedTask(): PersistedSyncTask | null {
  try {
    const raw = localStorage.getItem(WGR_TASK_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedSyncTask;
    if (typeof parsed?.taskId === "string" && typeof parsed?.queuedAt === "number") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

function writePersistedTask(task: PersistedSyncTask | null): void {
  try {
    if (task) localStorage.setItem(WGR_TASK_STORAGE_KEY, JSON.stringify(task));
    else localStorage.removeItem(WGR_TASK_STORAGE_KEY);
  } catch {
    /* storage unavailable (private mode / quota) — degrade to in-memory only */
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatAge(ageMinutes: number | null): string {
  if (ageMinutes === null) return "never";
  if (ageMinutes < 1) return "just now";
  if (ageMinutes < 60) return `${Math.round(ageMinutes)} min ago`;
  const hrs = ageMinutes / 60;
  if (hrs < 24) return `${hrs.toFixed(1)}h ago`;
  return `${(hrs / 24).toFixed(1)}d ago`;
}

function formatClock(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// Verdict → pill styling. Mirrors the gray/green/amber language used elsewhere.
const VERDICT_STYLE: Record<FreshnessVerdict, { dot: string; pill: string; label: string }> = {
  fresh: { dot: "bg-emerald-500", pill: "bg-emerald-50 text-emerald-700", label: "Fresh" },
  stale: { dot: "bg-amber-500", pill: "bg-amber-50 text-amber-700", label: "Stale" },
  unknown: { dot: "bg-gray-400", pill: "bg-gray-100 text-gray-600", label: "No data" },
};

function VerdictPill({ verdict }: { verdict: FreshnessVerdict }) {
  const s = VERDICT_STYLE[verdict];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ${s.pill}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      {s.label}
    </span>
  );
}

function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
      role="status"
      aria-label="Syncing"
    />
  );
}

// ─── Per-source row ─────────────────────────────────────────────────────────────

function SourceRow({
  source,
  onSync,
  isSyncing,
}: {
  source: FreshnessSourceResult;
  onSync?: () => void;
  isSyncing?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-gray-100 last:border-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-semibold text-gray-900 truncate">{source.label}</span>
          <VerdictPill verdict={source.verdict} />
        </div>
        <p className="text-[12px] text-gray-500 mt-0.5">{source.detail}</p>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <div className="text-right">
          <div className="text-[12px] font-medium text-gray-700">{formatAge(source.age_minutes)}</div>
          {source.last_run_at && (
            <div className="text-[11px] text-gray-400">{formatClock(source.last_run_at)}</div>
          )}
        </div>
        {onSync && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onSync}
            disabled={isSyncing}
            data-tour="wgr-sync-now"
          >
            {isSyncing ? (
              <>
                <Spinner className="text-gray-500" /> Syncing…
              </>
            ) : (
              "Sync now"
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

// ─── Panel ─────────────────────────────────────────────────────────────────────

const OVERALL_COPY: Record<FreshnessVerdict, string> = {
  fresh: "All sources are within their expected sync cadence.",
  stale: "Some sources are behind. If the worker/beat were stopped (e.g. end of day), this is expected — start them and let the schedule catch up.",
  unknown: "One or more sources have never recorded a sync yet.",
};

export function FreshnessPanel() {
  const [data, setData] = useState<FreshnessResponse | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  // The in-flight WGR sync, if any. Hydrated from localStorage on mount so it
  // survives refreshes; null when nothing is running.
  const [wgrTask, setWgrTask] = useState<PersistedSyncTask | null>(null);

  const check = useCallback(async () => {
    setIsChecking(true);
    try {
      // silent: we render the result inline, including errors, rather than
      // relying on the global error toast.
      const res = await apiClient.get<FreshnessResponse>("/freshness", { silent: true });
      setData(res);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Freshness check failed.");
    } finally {
      setIsChecking(false);
    }
  }, []);

  // Stop tracking the sync: clear both state and storage.
  const clearWgrTask = useCallback(() => {
    setWgrTask(null);
    writePersistedTask(null);
  }, []);

  const syncWgr = useCallback(async () => {
    try {
      const res = await apiClient.post<SyncTriggerResponse>(
        "/freshness/wgr/sync",
        {},
        { silent: true },
      );
      if (res.queued && res.task_id) {
        const task: PersistedSyncTask = { taskId: res.task_id, queuedAt: Date.now() };
        writePersistedTask(task);
        setWgrTask(task); // flips the indicator on; the poll effect takes over
        showSuccess(res.message);
      } else {
        // Not an error per se (e.g. sync disabled on this env) — inform, don't alarm.
        showInfo(res.message);
      }
    } catch (err) {
      showError(err instanceof Error ? err.message : "Couldn't queue the WGR sync.");
    }
  }, []);

  // On mount, re-attach to any sync that was running before a refresh/navigation.
  useEffect(() => {
    setWgrTask(readPersistedTask());
  }, []);

  // Poll the running task until it reaches a terminal state. Re-runs whenever
  // wgrTask changes (queued, or re-hydrated on mount). The cleanup clears the
  // timer so we never leak a poll loop across task changes or unmount.
  useEffect(() => {
    if (!wgrTask) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const queuedSecondsAgo = (Date.now() - wgrTask.queuedAt) / 1000;
        const status = await apiClient.get<SyncStatusResponse>(
          `/freshness/wgr/sync/${wgrTask.taskId}?queued_seconds_ago=${queuedSecondsAgo}`,
          { silent: true },
        );
        if (cancelled) return;
        if (status.running) {
          timer = setTimeout(() => void poll(), POLL_INTERVAL_MS);
        } else {
          // Terminal — stop, inform, and refresh the freshness numbers so the
          // WGR row's timestamp reflects the just-finished pull.
          clearWgrTask();
          if (status.detail) {
            if (status.state === "FAILURE") showError(status.detail);
            else showSuccess(status.detail);
          }
          void check();
        }
      } catch {
        // A transient poll error shouldn't strand the spinner forever; back off
        // and retry on the next tick. The PENDING-giveup guard on the server
        // still eventually resolves a genuinely dead task.
        if (!cancelled) timer = setTimeout(() => void poll(), POLL_INTERVAL_MS);
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [wgrTask, clearWgrTask, check]);

  const isSyncingWgr = wgrTask !== null;

  return (
    <Card>
      <CardHeader
        title="Data freshness"
        action={
          <Button
            variant="primary"
            size="sm"
            onClick={() => void check()}
            disabled={isChecking}
            data-tour="freshness-check"
          >
            {isChecking ? "Checking…" : data ? "Re-check" : "Check now"}
          </Button>
        }
      />
      <CardBody>
        {/* Refresh-proof running indicator: shown whenever a WGR sync is in
            flight, even before the user has run a freshness check, because the
            running state is re-hydrated from localStorage on mount. */}
        {isSyncingWgr && (
          <div className="mb-3 flex items-center gap-2 rounded-md border border-accent-100 bg-accent-50 px-3 py-2 text-[12px] text-accent-700">
            <Spinner className="text-accent-600" />
            <span>WGR sync in progress… this keeps running if you refresh or leave the page.</span>
          </div>
        )}
        {!data && !isChecking && (
          <p className="text-[13px] text-gray-500">
            Check when each scheduled source last synced and whether it&apos;s within its expected
            cadence. Read-only — this does not trigger any sync.
          </p>
        )}
        {isChecking && !data && (
          <p className="text-[13px] text-gray-400">Checking each source…</p>
        )}
        {data && (
          <>
            <div className="flex items-center gap-2 mb-3">
              <VerdictPill verdict={data.overall} />
              <span className="text-[12px] text-gray-500">
                {OVERALL_COPY[data.overall]} As of {formatClock(data.checked_at)}.
              </span>
            </div>
            <div>
              {data.sources.map((s) => (
                <SourceRow
                  key={s.key}
                  source={s}
                  onSync={s.key === "wgr" ? () => void syncWgr() : undefined}
                  isSyncing={s.key === "wgr" ? isSyncingWgr : undefined}
                />
              ))}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
