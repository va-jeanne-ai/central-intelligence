"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  type DragEndEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { apiClient } from "@/lib/api-client";
import { showApiError } from "@/lib/toast";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface GoalRow {
  id: string;
  member_id: string | null;
  member_name: string | null;
  goal_text: string | null;
  status: string | null;
  stage: string | null;
  targetDate: string | null;
  created_at: string | null;
  overdue: boolean;
}

type Stage = "todo" | "in_progress" | "blocked" | "done";

const STAGES: { key: Stage; label: string }[] = [
  { key: "todo", label: "To Do" },
  { key: "in_progress", label: "In Progress" },
  { key: "blocked", label: "Blocked" },
  { key: "done", label: "Done" },
];

const STATUS_BADGE: Record<string, string> = {
  active: "bg-blue-50 text-blue-700",
  completed: "bg-green-50 text-green-700",
  abandoned: "bg-gray-100 text-gray-500",
};

function statusBadge(status: string | null): string {
  return STATUS_BADGE[(status ?? "").toLowerCase()] ?? "bg-gray-100 text-gray-600";
}

/** NULL / unrecognised stage falls into "To Do". */
function normalizeStage(stage: string | null): Stage {
  const s = (stage ?? "").toLowerCase();
  return (STAGES.find((x) => x.key === s)?.key ?? "todo") as Stage;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

// ─── Card ────────────────────────────────────────────────────────────────────

function GoalCard({ goal }: { goal: GoalRow }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: goal.id });
  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm cursor-grab active:cursor-grabbing hover:border-orange-300 transition-colors"
    >
      <p className="text-[13px] font-medium text-gray-800 line-clamp-2">{goal.goal_text || "—"}</p>
      <p className="text-[11px] text-gray-400 mt-1 truncate">{goal.member_name ?? "—"}</p>
      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${statusBadge(goal.status)}`}>
          {goal.status ? goal.status[0].toUpperCase() + goal.status.slice(1) : "—"}
        </span>
        {goal.overdue && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-600">
            Overdue
          </span>
        )}
        {goal.targetDate && <span className="text-[10px] text-gray-400">🎯 {fmtDate(goal.targetDate)}</span>}
      </div>
    </div>
  );
}

// ─── Column ──────────────────────────────────────────────────────────────────

function Column({ stage, label, goals }: { stage: Stage; label: string; goals: GoalRow[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  return (
    <div
      ref={setNodeRef}
      className={`flex flex-col rounded-xl border bg-gray-50/60 min-h-[200px] transition-colors ${
        isOver ? "border-orange-400 bg-orange-50/50" : "border-gray-200"
      }`}
    >
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-gray-200">
        <span className="text-[11px] font-bold uppercase tracking-widest text-orange-600">{label}</span>
        <span className="text-[11px] text-gray-400">{goals.length}</span>
      </div>
      <div className="flex-1 p-2 space-y-2 overflow-y-auto">
        {goals.length === 0 ? (
          <p className="text-[11px] text-gray-300 text-center py-6">Drop goals here</p>
        ) : (
          goals.map((g) => <GoalCard key={g.id} goal={g} />)
        )}
      </div>
    </div>
  );
}

// ─── Board ───────────────────────────────────────────────────────────────────

export function GoalBoard({ goals, onChanged }: { goals: GoalRow[]; onChanged: () => void }) {
  // Local mirror so we can move a card optimistically before the PATCH lands.
  const [items, setItems] = useState<GoalRow[]>(goals);
  useEffect(() => {
    setItems(goals);
  }, [goals]);

  const sensors = useSensors(useSensor(PointerSensor), useSensor(KeyboardSensor));

  const grouped = useMemo(() => {
    const by: Record<Stage, GoalRow[]> = { todo: [], in_progress: [], blocked: [], done: [] };
    for (const g of items) by[normalizeStage(g.stage)].push(g);
    return by;
  }, [items]);

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const goalId = String(active.id);
    const targetStage = String(over.id) as Stage;
    const goal = items.find((g) => g.id === goalId);
    if (!goal) return;
    if (normalizeStage(goal.stage) === targetStage) return; // dropped in same column

    const prevStage = goal.stage;
    // Optimistic move.
    setItems((cur) => cur.map((g) => (g.id === goalId ? { ...g, stage: targetStage } : g)));
    try {
      await apiClient.patch(`/goals/${goalId}`, { stage: targetStage });
      onChanged();
    } catch (err) {
      // Revert on failure.
      setItems((cur) => cur.map((g) => (g.id === goalId ? { ...g, stage: prevStage } : g)));
      showApiError(err as Error);
    }
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {STAGES.map((s) => (
          <Column key={s.key} stage={s.key} label={s.label} goals={grouped[s.key]} />
        ))}
      </div>
    </DndContext>
  );
}
