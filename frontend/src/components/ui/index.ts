/**
 * UI Component Library — Barrel Export
 *
 * Atomic design system derived from the Central Intelligence webapp mockup.
 * Import: import { KpiCard, Card, Badge, Button } from "@/components/ui";
 */

// ─── Atoms ───────────────────────────────────────────────────────────────────
export { Badge } from "./badge";
export { StatusBadge } from "./status-badge";
export { PlatformTag } from "./platform-tag";
export { ScoreBar } from "./score-bar";
export { Button, CopyButton } from "./button";
export { FormField, FormInput, FormSelect, FormTextarea } from "./form-field";

// ─── Molecules ───────────────────────────────────────────────────────────────
export { KpiCard, KpiRow } from "./kpi-card";
export { Card, CardHeader, CardBody } from "./card";
export { FilterBar } from "./filter-bar";
export { HistoryItem, HistoryList } from "./history-item";
export { SuggestionPanel } from "./suggestion-panel";

// ─── Existing ────────────────────────────────────────────────────────────────
export { Skeleton } from "./skeleton";
export { EmptyState } from "./empty-state";
