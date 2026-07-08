"""Analytics models — the metric snapshot timeseries store.

This is the missing foundation for "monitor progress as we generate more data":
an append-only timeseries of every registered outcome metric (see
``app/analytics/registry.py``), captured on a schedule. Trend detection and
data-cited recommendations read from here.

One row = one metric's value for one (window, scope) at one capture time.
"""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MetricSnapshot(Base):
    """A point-in-time value of one registered metric.

    ``metric_key`` matches ``app.analytics.registry.Metric.key``. ``window`` is the
    lookback the value was computed over ("7d" / "30d" / "90d" / "all"). ``scope``
    lets the same metric be captured globally ("global") or per-entity later
    (e.g. "rep:REP_X") without a schema change.

    Append-only: each scheduled run inserts a new row, so history accrues. The
    unique constraint makes a given day's snapshot idempotent (re-running the task
    the same day updates rather than duplicates).
    """

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "metric_key",
            "window",
            "scope",
            "captured_date",
            name="uq_metric_snapshots_key_window_scope_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    metric_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    area: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    window: Mapped[str] = mapped_column(String(16), nullable=False)  # 7d / 30d / 90d / all
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="global")

    # The computed value + the sample size it rests on (for significance gating later).
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)  # ratio/score/count/currency

    # captured_date = the idempotency key per day; captured_at = the exact instant.
    captured_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Recommendation(Base):
    """A data-cited recommendation, emitted only when a metric's trend crosses a
    threshold. The conclusion comes from statistics (see ``app/analytics/trends.py``
    + ``recommend.py``), NOT from an LLM — the ``evidence`` JSON records the exact
    numbers behind it (metric, baseline→latest, window, sample sizes). An LLM may
    later phrase ``title``/``body`` from this evidence, never invent a recommendation.

    Lifecycle: open → acknowledged → acted → resolved (the feedback loop: as more data
    arrives we re-check whether the metric moved). Recommendations are upserted on the
    natural key (metric_key, window, scope) so a standing finding refreshes rather than
    piles up. ``scope`` mirrors ``MetricSnapshot.scope``: "global" for the existing
    company-wide findings, "rep:<rep_id>" for a per-rep finding — the same metric can
    have both an open global finding and an open finding for one specific rep at once.
    """

    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint(
            "metric_key", "window", "scope", name="uq_recommendations_metric_window_scope"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    metric_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    area: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    window: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="global")

    # What the data says.
    verdict: Mapped[str] = mapped_column(String(24), nullable=False)  # declining / improving / …
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")  # info/warn/critical
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # The exact numbers behind the conclusion (auditable; the "must cite" contract).
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Lifecycle.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")  # open/ack/acted/resolved

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OverallInsight(Base):
    """A daily (or weekly), LLM-synthesized company-level health assessment.

    Unlike ``Recommendation`` (a per-metric, statistics-only finding), this is a
    holistic narrative over the whole analytics picture — verdict + prose + key shifts.
    It *compounds*: each assessment is generated from the fresh analytics PLUS the
    previous assessment's narrative (same period), so the story carries forward.
    ``previous_insight_id`` links to the immediately-earlier row of the SAME period
    (NULL for the genesis assessment of that period).

    ``period`` discriminates 'daily' (the original per-day assessment; see
    ``app.analytics.overall_insight``) from 'weekly' (the digest that synthesizes the
    last 7 days; see ``app.analytics.weekly_digest``). Both share this table because the
    shape and the "LLM only phrases recorded evidence" contract are identical — only the
    cadence and the range of evidence differ. ``insight_date`` is the anchor date
    (the day for 'daily'; the first day of the covered week for 'weekly') and
    ``period_end`` is NULL for 'daily' and the last day of the covered week for 'weekly'.

    ``evidence`` records the analytics inputs the LLM was given (trends, recs, latest
    values) so the narrative is auditable. One row per (``insight_date``, ``period``) —
    a regenerate upserts (replaces) the same slot rather than piling up.
    """

    __tablename__ = "overall_insights"
    __table_args__ = (
        UniqueConstraint("insight_date", "period", name="uq_overall_insights_date_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # One assessment per (calendar day, period); the idempotency key.
    insight_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="published")

    # 'daily' (default, matches all pre-existing rows) or 'weekly'. period_end is the
    # last day of the covered range for 'weekly' digests; NULL for 'daily'.
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="daily", index=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # The assessment itself.
    health_verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # healthy/watch/at_risk
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    key_shifts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # list[str]

    # The analytics inputs given to the LLM (audit trail), and the model used.
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model: Mapped[str] = mapped_column(String(64), nullable=False)  # model id, or "mock"

    # The day this assessment built on (NULL for genesis). SET NULL on delete so
    # pruning an old row never cascades away a later one.
    previous_insight_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("overall_insights.id", ondelete="SET NULL"), nullable=True
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
