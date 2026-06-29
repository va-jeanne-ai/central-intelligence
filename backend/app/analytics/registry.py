"""Metric registry — the declarative catalog of outcome metrics.

This is the "what we measure" layer of the data-intelligence engine. Each metric
declares:
  - a stable ``key`` (used as the natural key in the snapshot store)
  - the ``area`` (sales / marketing / fulfillment)
  - a human ``label`` + ``unit`` and ``higher_is_better`` direction
  - the ``sql`` that computes ONE numeric ``value`` plus a ``sample_size`` over a
    time window — purely from the real tables, no heuristics.

The SQL contract (every metric MUST follow it so the compute layer is generic):
  - SELECT exactly two columns aliased ``value`` and ``sample_size``.
  - ``value`` is the metric (rate, average, count, …); ``sample_size`` is the row
    count the value rests on (used later to gate significance — don't trust a rate
    built on 3 rows).
  - Accept a window via a single bind param ``:since`` (a timestamp). When
    ``:since`` is NULL the metric is all-time (use ``(:since IS NULL OR col >= :since)``).
  - Return exactly one row. Use COALESCE so an empty window yields 0, not NULL.

All SQL below was verified against the live schema + real data (2026-06-29):
  - closed_sales.lead_id is the raw WGR string → joins to leads.external_id (NOT leads.id).
  - appointment statuses are: completed / cancelled / scheduled / no_show.
  - sales_call_scores.score is 0–10; scored_at is populated.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause


@dataclass(frozen=True)
class Metric:
    """One declared outcome metric. ``sql`` follows the contract in the module docstring.

    The optional ``asof_*`` fields declare how to compute the metric *as of* any past
    day, set-based, so a true rolling history can be derived on read directly from the
    source tables — no accumulated snapshots required. They describe a single-table
    aggregate: rows of ``asof_table`` whose ``asof_date_col`` falls in a rolling window
    ``(as_of - W, as_of]``, optionally pre-filtered by ``asof_row_filter``, reduced by
    ``asof_value_expr`` (the metric) and ``asof_sample_expr`` (the row count). Metrics
    whose computation spans tables (e.g. a cross-table EXISTS) leave these None and
    simply don't offer as-of history. See ``analytics/asof.py`` for the generator.
    """

    key: str
    area: str
    label: str
    unit: str  # "ratio" (0–1), "score", "count", "currency"
    higher_is_better: bool
    sql: TextClause
    description: str = ""

    # As-of history support (optional; None → metric has no derived history).
    asof_table: str | None = None
    asof_date_col: str | None = None  # SQL expr, e.g. "close_date" or "COALESCE(scored_at, created_at)"
    asof_value_expr: str | None = None  # aggregate producing the metric value
    asof_sample_expr: str | None = None  # aggregate producing the row count
    asof_row_filter: str | None = None  # extra WHERE predicate (no leading AND)

    @property
    def has_asof(self) -> bool:
        return bool(
            self.asof_table
            and self.asof_date_col
            and self.asof_value_expr
            and self.asof_sample_expr
        )


# ─── Sales metrics ──────────────────────────────────────────────────────────────
# Proven end-to-end first (most data-rich area), then generalized to other areas.

_SALES_METRICS: list[Metric] = [
    Metric(
        key="sales.lead_to_close_rate",
        area="sales",
        label="Lead → Close Rate",
        unit="ratio",
        higher_is_better=True,
        description="Share of leads (that ENTERED the funnel in window) that have a "
        "closed sale. Windowed on leads.entry_date — the upstream funnel-entry date, "
        "NOT created_at (when the row was synced into CI). Rows with a NULL entry_date "
        "are excluded when a window is set (entry_date is ~99% populated). "
        "Join: closed_sales.lead_id = leads.external_id.",
        sql=text(
            """
            WITH base AS (
                SELECT
                    l.id,
                    EXISTS (
                        SELECT 1 FROM closed_sales cs
                        WHERE cs.lead_id = l.external_id
                    ) AS closed
                FROM leads l
                WHERE l.deleted_at IS NULL
                  AND (:since IS NULL OR (l.entry_date IS NOT NULL
                                          AND l.entry_date >= (:since)::date))
            )
            SELECT
                COALESCE(AVG(CASE WHEN closed THEN 1.0 ELSE 0.0 END), 0) AS value,
                COUNT(*)                                                 AS sample_size
            FROM base
            """
        ),
    ),
    Metric(
        key="sales.avg_call_score",
        area="sales",
        label="Avg Call Score",
        unit="score",
        higher_is_better=True,
        description="Average sales call score (0–10) over calls scored in the window.",
        sql=text(
            """
            SELECT
                COALESCE(AVG(score), 0) AS value,
                COUNT(*)                AS sample_size
            FROM sales_call_scores
            WHERE score IS NOT NULL
              AND (:since IS NULL OR COALESCE(scored_at, created_at) >= :since)
            """
        ),
        asof_table="sales_call_scores",
        asof_date_col="COALESCE(scored_at, created_at)",
        asof_value_expr="COALESCE(AVG(score), 0)",
        asof_sample_expr="COUNT(*)",
        asof_row_filter="score IS NOT NULL",
    ),
    Metric(
        key="sales.appointment_show_rate",
        area="sales",
        label="Appointment Show Rate",
        unit="ratio",
        higher_is_better=True,
        description="completed / (completed + no_show) for appointments scheduled in "
        "the window. Excludes still-scheduled and cancelled (not yet a show/no-show).",
        sql=text(
            """
            SELECT
                COALESCE(
                    COUNT(*) FILTER (WHERE status = 'completed')::float
                    / NULLIF(COUNT(*) FILTER (WHERE status IN ('completed', 'no_show')), 0),
                    0
                ) AS value,
                COUNT(*) FILTER (WHERE status IN ('completed', 'no_show')) AS sample_size
            FROM appointments
            WHERE deleted_at IS NULL
              AND (:since IS NULL OR COALESCE(scheduled_at, created_at) >= :since)
            """
        ),
        asof_table="appointments",
        asof_date_col="COALESCE(scheduled_at, created_at)",
        asof_value_expr=(
            "COALESCE(COUNT(*) FILTER (WHERE status = 'completed')::float "
            "/ NULLIF(COUNT(*) FILTER (WHERE status IN ('completed', 'no_show')), 0), 0)"
        ),
        asof_sample_expr="COUNT(*) FILTER (WHERE status IN ('completed', 'no_show'))",
        asof_row_filter="deleted_at IS NULL",
    ),
    Metric(
        key="sales.closed_sales_count",
        area="sales",
        label="Closed Sales",
        unit="count",
        higher_is_better=True,
        description="Number of closed sales with a close_date in the window.",
        sql=text(
            """
            SELECT
                COUNT(*) AS value,
                COUNT(*) AS sample_size
            FROM closed_sales
            WHERE close_date IS NOT NULL
              AND (:since IS NULL OR close_date >= (:since)::date)
            """
        ),
        asof_table="closed_sales",
        asof_date_col="close_date",
        asof_value_expr="COUNT(*)",
        asof_sample_expr="COUNT(*)",
        asof_row_filter="close_date IS NOT NULL",
    ),
    Metric(
        key="sales.revenue_collected",
        area="sales",
        label="Revenue Collected",
        unit="currency",
        higher_is_better=True,
        description="Sum of amount_collected over closed sales with a close_date in the window.",
        sql=text(
            """
            SELECT
                COALESCE(SUM(amount_collected), 0) AS value,
                COUNT(*) FILTER (WHERE amount_collected IS NOT NULL) AS sample_size
            FROM closed_sales
            WHERE close_date IS NOT NULL
              AND (:since IS NULL OR close_date >= (:since)::date)
            """
        ),
        asof_table="closed_sales",
        asof_date_col="close_date",
        asof_value_expr="COALESCE(SUM(amount_collected), 0)",
        asof_sample_expr="COUNT(*) FILTER (WHERE amount_collected IS NOT NULL)",
        asof_row_filter="close_date IS NOT NULL",
    ),
    Metric(
        key="sales.revenue_earned",
        area="sales",
        label="Revenue Earned",
        unit="currency",
        higher_is_better=True,
        description="Sum of revenue_earned over closed sales with a close_date in the "
        "window. Distinct from Revenue Collected (amount_collected): earned is the full "
        "booked value of the sale, collected is the cash actually taken in — the gap is "
        "payment plans / outstanding balances. Both pass through 1:1 from WGR.",
        sql=text(
            """
            SELECT
                COALESCE(SUM(revenue_earned), 0) AS value,
                COUNT(*) FILTER (WHERE revenue_earned IS NOT NULL) AS sample_size
            FROM closed_sales
            WHERE close_date IS NOT NULL
              AND (:since IS NULL OR close_date >= (:since)::date)
            """
        ),
        asof_table="closed_sales",
        asof_date_col="close_date",
        asof_value_expr="COALESCE(SUM(revenue_earned), 0)",
        asof_sample_expr="COUNT(*) FILTER (WHERE revenue_earned IS NOT NULL)",
        asof_row_filter="close_date IS NOT NULL",
    ),
]


# ─── Marketing metrics ──────────────────────────────────────────────────────────
# Only metrics backed by REAL data are registered (verified 2026-06-29): email_campaigns
# has 2,396 rows; funnel_stats / social_stats / ads_stats are EMPTY, so those metrics are
# intentionally omitted until the data exists (snapshotting zeros forever isn't a signal).

_MARKETING_METRICS: list[Metric] = [
    Metric(
        key="marketing.email_open_rate",
        area="marketing",
        label="Email Open Rate",
        unit="ratio",
        higher_is_better=True,
        description="Opens / recipients across campaigns sent in the window.",
        sql=text(
            """
            SELECT
                COALESCE(
                    SUM(open_count)::float / NULLIF(SUM(recipients_count), 0), 0
                ) AS value,
                COALESCE(SUM(recipients_count), 0) AS sample_size
            FROM email_campaigns
            WHERE deleted_at IS NULL
              AND sent_at IS NOT NULL
              AND (:since IS NULL OR sent_at >= :since)
            """
        ),
        asof_table="email_campaigns",
        asof_date_col="sent_at",
        asof_value_expr="COALESCE(SUM(open_count)::float / NULLIF(SUM(recipients_count), 0), 0)",
        asof_sample_expr="COALESCE(SUM(recipients_count), 0)",
        asof_row_filter="deleted_at IS NULL AND sent_at IS NOT NULL",
    ),
    Metric(
        key="marketing.email_click_rate",
        area="marketing",
        label="Email Click Rate",
        unit="ratio",
        higher_is_better=True,
        description="Clicks / recipients across campaigns sent in the window.",
        sql=text(
            """
            SELECT
                COALESCE(
                    SUM(click_count)::float / NULLIF(SUM(recipients_count), 0), 0
                ) AS value,
                COALESCE(SUM(recipients_count), 0) AS sample_size
            FROM email_campaigns
            WHERE deleted_at IS NULL
              AND sent_at IS NOT NULL
              AND (:since IS NULL OR sent_at >= :since)
            """
        ),
        asof_table="email_campaigns",
        asof_date_col="sent_at",
        asof_value_expr="COALESCE(SUM(click_count)::float / NULLIF(SUM(recipients_count), 0), 0)",
        asof_sample_expr="COALESCE(SUM(recipients_count), 0)",
        asof_row_filter="deleted_at IS NULL AND sent_at IS NOT NULL",
    ),
]


# ─── Fulfillment metrics ────────────────────────────────────────────────────────
# Verified 2026-06-29: sales_coaching_strikes has 15 rows (status active/open, severity
# flag). goals table is EMPTY, so goal-completion is omitted until data exists.

_FULFILLMENT_METRICS: list[Metric] = [
    Metric(
        key="fulfillment.open_coaching_strikes",
        area="fulfillment",
        label="Open Coaching Strikes",
        unit="count",
        higher_is_better=False,  # fewer unresolved strikes is better
        description="Count of coaching strikes still unresolved (status active/open) "
        "that were triggered in the window.",
        sql=text(
            """
            SELECT
                COUNT(*) AS value,
                COUNT(*) AS sample_size
            FROM sales_coaching_strikes
            WHERE status IN ('active', 'open')
              AND (:since IS NULL OR triggered_at >= :since)
            """
        ),
        asof_table="sales_coaching_strikes",
        asof_date_col="triggered_at",
        asof_value_expr="COUNT(*)",
        asof_sample_expr="COUNT(*)",
        asof_row_filter="status IN ('active', 'open')",
    ),
]


# The full catalog. Areas append here as their data lands.
REGISTRY: list[Metric] = [*_SALES_METRICS, *_MARKETING_METRICS, *_FULFILLMENT_METRICS]

_BY_KEY: dict[str, Metric] = {m.key: m for m in REGISTRY}


def all_metrics() -> list[Metric]:
    """Every registered metric."""
    return list(REGISTRY)


def metrics_for_area(area: str) -> list[Metric]:
    """Registered metrics for one area (e.g. 'sales')."""
    return [m for m in REGISTRY if m.area == area]


def get_metric(key: str) -> Metric | None:
    """Look up a metric by its stable key."""
    return _BY_KEY.get(key)
