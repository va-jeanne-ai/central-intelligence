# Central Intelligence

## Purpose

AI-powered workforce management platform — the "Central Intelligence" system for task coordination and agent workflows.

## Goals

- Complete PRD and technical architecture (see New Documents/)
- Build out implementation per sprint plan
- Deliver webapp matching mockups in template/

## Configuration

- `.env`: (pending — add API keys as needed)
- OAuth: (pending — configure if Google integrations required)

## Tools Inventory

| Script | Purpose |
|--------|---------|
| (none yet) | |

## Workflows Inventory

| Workflow | Purpose |
|----------|---------|
| (none yet) | |

## Key References

- `New Documents/PRD.md` — Full product requirements
- `New Documents/technical-plan-enhanced.md` — Technical architecture
- `New Documents/sprint-plan-enhanced.md` — Implementation schedule
- `New Documents/api-contract-enhanced.md` — API specifications
- `New Documents/data-schema-enhanced.md` — Database schema
- `template/` — Original client materials and mockups (read-only reference)

## Frontend — Atomic Component Library

All frontend pages must use the shared atomic UI components in `frontend/src/components/ui/`. The webapp mockup (`New Documents/webapp-mockup.html`) is the single source of truth for design — light mode adaptation.

**Atoms** — smallest building blocks:
| Component | File | Purpose |
|-----------|------|---------|
| `Badge` | `badge.tsx` | Trend badges (↑/↓ with up/down/neutral variants) |
| `StatusBadge` | `status-badge.tsx` | Entity status pills (active, draft, paused, archived, etc.) |
| `PlatformTag` | `platform-tag.tsx` | Social platform pills (instagram, facebook, linkedin, tiktok) |
| `ScoreBar` | `score-bar.tsx` | Horizontal progress bars (ICP alignment, lead scores) |
| `Button` / `CopyButton` | `button.tsx` | Primary (gold), ghost (outline), danger buttons + copy-to-clipboard |
| `FormField` / `FormInput` / `FormSelect` / `FormTextarea` | `form-field.tsx` | Consistent form elements with label styling |

**Molecules** — composed from atoms:
| Component | File | Purpose |
|-----------|------|---------|
| `KpiCard` / `KpiRow` | `kpi-card.tsx` | KPI metric cards with colored top borders in 4-col grid |
| `Card` / `CardHeader` / `CardBody` | `card.tsx` | Generic white card container with header/body sections |
| `FilterBar` | `filter-bar.tsx` | Horizontal search + filter selects row |
| `HistoryItem` / `HistoryList` | `history-item.tsx` | Timeline rows with colored dots and trailing elements |
| `SuggestionPanel` | `suggestion-panel.tsx` | AI suggestion amber panel with arrow-prefixed items |

**Rules:**
- Always use these components instead of writing one-off card/button/badge/form markup.
- Import from individual files: `import { KpiCard } from "@/components/ui/kpi-card"`.
- KPI cards use department border colors: marketing `#10B981`, sales `#3B82F6`, fulfillment `#F97316`, gold `#F59E0B`.
- Barrel export available at `@/components/ui` for convenience.
- Existing skeleton components (`skeleton.tsx`) stay as-is for loading states.

## Project Notes

- `New Documents/` and `template/` are reference material — do not modify without asking.
- Architecture diagram: `New Documents/architecture-diagram.html`
- Webapp mockup: `New Documents/webapp-mockup.html` — **single source of truth for UI design** (adapted to light mode)

## Integrations catalog

[INTEGRATIONS.md](INTEGRATIONS.md) is the living catalog of every third-party integration (Mailchimp, Google Calendar, Meta Ads, etc.). Each entry covers what it does today, the surfaces it powers, and what it *could* power but doesn't yet.

**Update rule:** any commit that adds, expands, or removes an integration — OR wires a new app surface to an existing one — must update `INTEGRATIONS.md` in the same commit. The provider registry at [`backend/app/services/integrations_registry.py`](backend/app/services/integrations_registry.py) is the source of truth for what shows up in the UI; `INTEGRATIONS.md` is the source of truth for *why*.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
