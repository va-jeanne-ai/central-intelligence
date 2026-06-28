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
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
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
