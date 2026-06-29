"""Derive a metric's rolling history *as of* each past day — set-based, read-only.

The snapshot store only holds points for days the snapshot job actually ran. To show
a true multi-month trend without waiting for snapshots to accrue (and without writing
anything), we recompute the metric directly from its source table for a span of past
days in a single query: a generated date series LEFT JOINed against the rows that fall
in each day's rolling window.

Each point for day D = the metric over rows whose date column is in ``(D - W, D]``,
where W is the rolling window width in days. This mirrors how the live 30d-window
metric reads, just evaluated as-of each historical day.

SQL safety: every interpolated fragment (table, date column, value/sample exprs,
filter) comes from the trusted in-process metric registry — never from request input.
The only request-derived values (window width, day span) are passed as bound params.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from app.analytics.registry import Metric


def build_asof_history_sql(metric: Metric) -> TextClause:
    """One query returning the rolling series for ``metric``.

    Binds (all caller-supplied, all parameterized):
      :window_days — rolling window width (e.g. 30)
      :days        — how many days back the series spans (e.g. 90)

    The anchor day is the database's ``CURRENT_DATE`` (server-side, no bind).

    Returns rows ``(captured_date, value, sample_size)`` ordered ascending, one per
    day in the span, with 0/empty for days whose window caught no rows.
    """
    if not metric.has_asof:
        raise ValueError(f"metric {metric.key!r} has no as-of history support")

    filter_clause = f"AND {metric.asof_row_filter}" if metric.asof_row_filter else ""

    # In a LEFT JOIN with the window predicate in ON, a day that matched no rows still
    # produces one all-NULL ``src`` row. A bare COUNT(*) would count that phantom as 1.
    # Any aggregate over a ``src`` column is NULL-safe, so rewrite the unqualified
    # COUNT(*) forms to count the (always-present-on-real-rows) date column instead.
    def _null_safe(expr: str) -> str:
        if expr.strip().upper() == "COUNT(*)":
            return f"COUNT({metric.asof_date_col})"
        return expr

    value_expr = _null_safe(metric.asof_value_expr)
    sample_expr = _null_safe(metric.asof_sample_expr)

    # generate_series gives one row per day; the LEFT JOIN attaches the source rows
    # whose date column falls in that day's rolling window. Aggregates are grouped
    # back per day. COALESCE so empty windows yield 0, not NULL.
    return text(
        f"""
        WITH days AS (
            SELECT generate_series(
                CURRENT_DATE - make_interval(days => :days),
                CURRENT_DATE,
                interval '1 day'
            )::date AS d
        )
        SELECT
            days.d AS captured_date,
            COALESCE({value_expr}, 0) AS value,
            {sample_expr} AS sample_size
        FROM days
        LEFT JOIN {metric.asof_table} src
          ON {metric.asof_date_col} >  days.d - make_interval(days => :window_days)
         AND {metric.asof_date_col} <= days.d
         {filter_clause}
        GROUP BY days.d
        ORDER BY days.d ASC
        """
    )
