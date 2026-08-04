"""Read-only WGR mirror of Greg's Meta Ads subsystem.

Text PKs preserved from WGR. No FKs — mirror data tolerates orphans; join
meta_ad_performance.ad_id → meta_ads.ad_id in queries. Free-text columns are
Text (unbounded upstream); short structured ids/statuses stay String(n).
(`models/meta.py` is users/teams — unrelated; hence the meta_ads name.)
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MetaCampaign(Base):
    __tablename__ = "meta_campaigns"

    campaign_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    meta_campaign_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    daily_budget: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    lifetime_budget: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    targeting_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    targeting_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MetaAd(Base):
    __tablename__ = "meta_ads"

    ad_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    campaign_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    meta_ad_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ad_format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hook_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    script_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    script_cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    framework_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    offer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    calendar_entry_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parent_ad_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    iteration_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    launched_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    kill_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    kill_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MetaAdPerformance(Base):
    __tablename__ = "meta_ad_performance"

    perf_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ad_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    snapshot_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    snapshot_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount_spent: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_per_lead: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    booked_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_per_booked_call: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    link_clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_per_link_click: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    hook_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    hold_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ctr: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    cpm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    frequency: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    kpi_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metric_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
