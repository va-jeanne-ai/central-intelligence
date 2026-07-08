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

The rep-scoped SQL contract (``rep_sql``, optional — see the ``Metric`` docstring):
  - SELECT exactly three columns aliased ``rep_id``, ``value``, ``sample_size``.
  - GROUP BY rep_id (or equivalent), one row per rep that has data in-window — a rep
    absent from the result set simply gets no snapshot that day, which is correct
    (not a zero; we never fabricate a value for a rep with no activity).
  - Honor the exact same window rule as the global ``sql``: bind ``:since`` and use
    ``(:since IS NULL OR col >= :since)``.
  - COALESCE the value expression so no row's ``value`` is ever NULL (a rep with rows
    in-window always has a computable value; only the "no rows at all" case is
    excluded via the GROUP BY rather than represented as 0).
  - Verified live 2026-07-08/09: 7 reps in sales_reps; e.g. REP_MAKYLA_THOMPSON has
    ~5k outbound sales_activities rows in the trailing 30d window.
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

    # Optional per-rep breakdown of the same metric. See the rep-scoped SQL contract
    # in the module docstring. None → this metric has no per-rep snapshot (either it
    # can't be rep-attributed, e.g. inbound activity, or it hasn't been wired up yet).
    rep_sql: TextClause | None = None

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
        rep_sql=text(
            """
            SELECT
                rep_id,
                COALESCE(AVG(score), 0) AS value,
                COUNT(*)                AS sample_size
            FROM sales_call_scores
            WHERE score IS NOT NULL
              AND rep_id IS NOT NULL
              AND (:since IS NULL OR COALESCE(scored_at, created_at) >= :since)
            GROUP BY rep_id
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
        rep_sql=text(
            """
            SELECT
                rep_id,
                COUNT(*) AS value,
                COUNT(*) AS sample_size
            FROM closed_sales
            WHERE close_date IS NOT NULL
              AND rep_id IS NOT NULL
              AND (:since IS NULL OR close_date >= (:since)::date)
            GROUP BY rep_id
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
        rep_sql=text(
            """
            SELECT
                rep_id,
                COALESCE(SUM(amount_collected), 0) AS value,
                COUNT(*) FILTER (WHERE amount_collected IS NOT NULL) AS sample_size
            FROM closed_sales
            WHERE close_date IS NOT NULL
              AND rep_id IS NOT NULL
              AND (:since IS NULL OR close_date >= (:since)::date)
            GROUP BY rep_id
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
    Metric(
        key="sales.outbound_volume",
        area="sales",
        label="Outbound Volume",
        unit="count",
        higher_is_better=True,
        description="Count of rep-attributed outbound touchpoints (call/email/sms/"
        "social_dm with activity_type ending '_outbound') occurring in the window. "
        "Windowed on sales_activities.occurred_at. Rows with a NULL rep_id are "
        "excluded (unattributed outbound activity — see sales_activities model note); "
        "the global value still counts every outbound row, attributed or not, so a "
        "rep's own attributed volume is naturally ≤ the global count.",
        sql=text(
            """
            SELECT
                COUNT(*) AS value,
                COUNT(*) AS sample_size
            FROM sales_activities
            WHERE activity_type LIKE '%_outbound'
              AND (:since IS NULL OR occurred_at >= :since)
            """
        ),
        rep_sql=text(
            """
            SELECT
                rep_id,
                COUNT(*) AS value,
                COUNT(*) AS sample_size
            FROM sales_activities
            WHERE activity_type LIKE '%_outbound'
              AND rep_id IS NOT NULL
              AND (:since IS NULL OR occurred_at >= :since)
            GROUP BY rep_id
            """
        ),
        asof_table="sales_activities",
        asof_date_col="occurred_at",
        asof_value_expr="COUNT(*)",
        asof_sample_expr="COUNT(*)",
        asof_row_filter="activity_type LIKE '%_outbound'",
    ),
    Metric(
        key="sales.channel_response_rate",
        area="sales",
        label="Channel Response Rate",
        unit="ratio",
        higher_is_better=True,
        description="Inbound / outbound sales_activities in the window — a rough proxy "
        "for how much inbound engagement each unit of outbound effort generates. "
        "GLOBAL ONLY: inbound sales_activities rows carry no rep attribution (ALL "
        "inbound rows have rep_id NULL, verified 2026-07-08), so this metric cannot be "
        "broken out per rep and intentionally has no rep_sql. Windowed on occurred_at "
        "for both the numerator and denominator independently (each side counts rows "
        "whose own occurred_at falls in the window).",
        sql=text(
            """
            SELECT
                COALESCE(
                    (SELECT COUNT(*) FROM sales_activities
                     WHERE activity_type LIKE '%_inbound'
                       AND (:since IS NULL OR occurred_at >= :since))::float
                    / NULLIF(
                        (SELECT COUNT(*) FROM sales_activities
                         WHERE activity_type LIKE '%_outbound'
                           AND (:since IS NULL OR occurred_at >= :since)),
                        0
                    ),
                    0
                ) AS value,
                (SELECT COUNT(*) FROM sales_activities
                 WHERE activity_type LIKE '%_outbound'
                   AND (:since IS NULL OR occurred_at >= :since)) AS sample_size
            """
        ),
    ),
]


# ─── Marketing metrics ──────────────────────────────────────────────────────────
# email_campaigns has 2,400+ rows. social_stats now has real rows too (verified
# 2026-07-08: 2 rows — linkedin/tiktok — with engagement_rate populated), so
# marketing.social_engagement is registered. funnel_stats is still EMPTY
# (verified 2026-07-08) — the writer task (app/tasks/funnel_stats.py) only ever
# populates event_count, never conversion_rate, so today this metric has zero
# sample_size / value 0 either way. It's registered anyway per the engine's
# insufficient_data design (thin/empty data degrades gracefully rather than
# being hidden) and will start reflecting real numbers the moment the funnel
# pipeline starts writing conversion_rate.

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
    Metric(
        key="marketing.social_engagement",
        area="marketing",
        label="Social Engagement Rate",
        unit="ratio",
        higher_is_better=True,
        description="Average engagement_rate across social_stats rows (one row per "
        "platform per aggregation period) whose period_end falls in the window. "
        "Simple average across platforms, not follower-weighted — each platform's "
        "period snapshot counts equally. sample_size is the number of platform-period "
        "rows behind the average (thin today: 2 platforms as of 2026-07-08).",
        sql=text(
            """
            SELECT
                COALESCE(AVG(engagement_rate), 0) AS value,
                COUNT(*) FILTER (WHERE engagement_rate IS NOT NULL) AS sample_size
            FROM social_stats
            WHERE deleted_at IS NULL
              AND (:since IS NULL OR period_end >= :since)
            """
        ),
        asof_table="social_stats",
        asof_date_col="period_end",
        asof_value_expr="COALESCE(AVG(engagement_rate), 0)",
        asof_sample_expr="COUNT(*) FILTER (WHERE engagement_rate IS NOT NULL)",
        asof_row_filter="deleted_at IS NULL",
    ),
    Metric(
        key="marketing.funnel_conversion",
        area="marketing",
        label="Funnel Conversion Rate",
        unit="ratio",
        higher_is_better=True,
        description="Average of the per-stage conversion_rate recorded in funnel_stats "
        "for periods overlapping the window. NOTE: as of 2026-07-08 funnel_stats is "
        "empty and its writer task (update_funnel_stats) only populates event_count, "
        "never conversion_rate — so this metric currently reads 0 value / 0 sample_size "
        "and the engine's insufficient_data verdict applies. It starts reflecting real "
        "numbers once the funnel pipeline computes and persists conversion_rate.",
        sql=text(
            """
            SELECT
                COALESCE(AVG(conversion_rate), 0) AS value,
                COUNT(*) FILTER (WHERE conversion_rate IS NOT NULL) AS sample_size
            FROM funnel_stats
            WHERE :since IS NULL OR period_end >= :since
            """
        ),
        asof_table="funnel_stats",
        asof_date_col="period_end",
        asof_value_expr="COALESCE(AVG(conversion_rate), 0)",
        asof_sample_expr="COUNT(*) FILTER (WHERE conversion_rate IS NOT NULL)",
    ),
]


# ─── Fulfillment metrics ────────────────────────────────────────────────────────
# sales_coaching_strikes has real rows (status active/open, severity flag). goals
# is still EMPTY (verified 2026-07-08, 0 rows total including soft-deleted) —
# fulfillment.goal_completion is registered anyway per the insufficient_data
# design; it will light up once member goals start getting created/completed.

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
        rep_sql=text(
            """
            SELECT
                rep_id,
                COUNT(*) AS value,
                COUNT(*) AS sample_size
            FROM sales_coaching_strikes
            WHERE status IN ('active', 'open')
              AND rep_id IS NOT NULL
              AND (:since IS NULL OR triggered_at >= :since)
            GROUP BY rep_id
            """
        ),
        asof_table="sales_coaching_strikes",
        asof_date_col="triggered_at",
        asof_value_expr="COUNT(*)",
        asof_sample_expr="COUNT(*)",
        asof_row_filter="status IN ('active', 'open')",
    ),
    Metric(
        key="fulfillment.goal_completion",
        area="fulfillment",
        label="Goal Completion Rate",
        unit="ratio",
        higher_is_better=True,
        description="completed / (completed + active + abandoned) for member goals "
        "created in the window. Windowed on goals.created_at (no separate "
        "completed_at column exists). Status vocabulary follows goal_stats.py: "
        "active / completed / abandoned (case-insensitive, matched via LOWER). "
        "Member-scoped (member_id IS NOT NULL) to mirror the existing goal_stats "
        "repository, which excludes lead-attached goals from this same ratio.",
        sql=text(
            """
            SELECT
                COALESCE(
                    COUNT(*) FILTER (WHERE LOWER(status) = 'completed')::float
                    / NULLIF(COUNT(*) FILTER (WHERE LOWER(status) IN ('completed', 'active', 'abandoned')), 0),
                    0
                ) AS value,
                COUNT(*) FILTER (WHERE LOWER(status) IN ('completed', 'active', 'abandoned')) AS sample_size
            FROM goals
            WHERE deleted_at IS NULL
              AND member_id IS NOT NULL
              AND (:since IS NULL OR created_at >= :since)
            """
        ),
        asof_table="goals",
        asof_date_col="created_at",
        asof_value_expr=(
            "COALESCE(COUNT(*) FILTER (WHERE LOWER(status) = 'completed')::float "
            "/ NULLIF(COUNT(*) FILTER (WHERE LOWER(status) IN ('completed', 'active', 'abandoned')), 0), 0)"
        ),
        asof_sample_expr=(
            "COUNT(*) FILTER (WHERE LOWER(status) IN ('completed', 'active', 'abandoned'))"
        ),
        asof_row_filter="deleted_at IS NULL AND member_id IS NOT NULL",
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
