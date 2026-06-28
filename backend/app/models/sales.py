"""Sales domain models — WGR-sourced subsystems CI had no tables for.

Added in the WGR rebase. These mirror the client's (Greg/WGR) sales-team
accountability + revenue subsystems, which CI's original schema never modelled:

  * SalesRep                — the 7-person sales team (clean rep_id key)
  * ScorecardCategory       — the 11-category call rubric
  * CallScore               — per-category 0-10 scores on a call
  * StrikeRule / CoachingStrike / StrikeAction / StrikeEvidence — the
    auto-coaching/accountability system
  * EodReport               — daily end-of-day rollups (JSONB content)
  * ClosedSale              — closed deals / revenue
  * SalesActivity           — every rep touchpoint (large, ~19k rows)

These tables only ever hold WGR data, so we keep WGR's native text primary keys
(rep_id, score_id, strike_id, …) as the CI PK. That makes the sync upsert
idempotent on the natural key with no separate (source, external_id) needed —
unlike the shared-domain tables (leads/calls/appointments) which keep CI's
(source='wgr', external_id) convention because they predate the rebase.

FK note: these reference WGR ids. ``business_id`` points at WGR's
``business_profile.id`` (an int); CI's own BusinessProfile uses a different key,
so business_id is stored as a plain Integer here (no cross-table FK) to avoid
coupling to CI's business_profile row shape. rep_id FKs stay within this module.
"""

from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SalesRep(Base, TimestampMixin):
    """A member of the WGR sales team. Clean join key for all sales_* tables."""

    __tablename__ = "sales_reps"

    rep_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    business_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    ghl_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    slack_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    probation_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    probation_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_tier_access: Mapped[int | None] = mapped_column(Integer, nullable=True)
    historical_aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    hired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RepOverride(Base, TimestampMixin):
    """CI-owned editable overrides for a synced rep (sales_reps).

    The WGR sync owns sales_reps and overwrites it on every run, so editing it
    directly would be wiped. The Members page edits write HERE instead, keyed by
    rep_id; each field is NULL when there's no override (fall back to the synced
    value). Read paths COALESCE override → sales_reps, so edits survive the sync
    AND newly-synced reps still appear. ``notes`` is CI-only (no synced source).
    """

    __tablename__ = "rep_overrides"

    rep_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("sales_reps.rep_id", ondelete="CASCADE"),
        primary_key=True,
    )
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScorecardCategory(Base, TimestampMixin):
    """A rubric category calls are scored against (discovery / sales)."""

    __tablename__ = "sales_scorecard_categories"

    category_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applies_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weight: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CallScore(Base, TimestampMixin):
    """Per-category 0-10 score on a call, with coaching rationale in notes.

    ``call_id`` references WGR's call id (stored on CI's Call as external_id when
    source='wgr'); we keep it as a plain string here rather than a CI FK so the
    score can land even if its call row hasn't synced yet (order-independent)."""

    __tablename__ = "sales_call_scores"

    score_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    call_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_scorecard_categories.category_id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    rep_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_reps.rep_id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    business_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float] = mapped_column(Numeric, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StrikeRule(Base, TimestampMixin):
    """A rule that converts low scores into coaching strikes."""

    __tablename__ = "sales_strike_rules"

    rule_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    strike_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    call_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    threshold_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    evidence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    applies_to_roles: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoachingStrike(Base, TimestampMixin):
    """An auto- or manually-raised accountability strike against a rep."""

    __tablename__ = "sales_coaching_strikes"

    strike_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rep_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_reps.rep_id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    business_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_strike_rules.rule_id", ondelete="SET NULL"), nullable=True,
    )
    category_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    call_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="flag")
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_reps.rep_id", ondelete="SET NULL"), nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    actions: Mapped[list["StrikeAction"]] = relationship(
        "StrikeAction", back_populates="strike", lazy="select",
    )
    evidence: Mapped[list["StrikeEvidence"]] = relationship(
        "StrikeEvidence", back_populates="strike", lazy="select",
    )


class StrikeAction(Base):
    """A lifecycle event on a strike (status transition, note)."""

    __tablename__ = "sales_strike_actions"

    action_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    strike_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sales_coaching_strikes.strike_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    strike: Mapped["CoachingStrike"] = relationship(
        "CoachingStrike", back_populates="actions", lazy="select",
    )


class StrikeEvidence(Base):
    """Links a strike to the call-score that justifies it."""

    __tablename__ = "sales_strike_evidence"

    evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    strike_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sales_coaching_strikes.strike_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    call_score_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_call_scores.score_id", ondelete="SET NULL"), nullable=True,
    )
    added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    strike: Mapped["CoachingStrike"] = relationship(
        "CoachingStrike", back_populates="evidence", lazy="select",
    )


class EodReport(Base):
    """Daily end-of-day rollup (rep or admin) with JSONB content; Slack-delivered."""

    __tablename__ = "sales_eod_reports"

    report_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    business_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    rep_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_reps.rep_id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    slack_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    slack_message_ts: Mapped[str | None] = mapped_column(String(64), nullable=True)
    slack_channel: Mapped[str | None] = mapped_column(String(128), nullable=True)
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClosedSale(Base, TimestampMixin):
    """A closed deal. ~30/74 are rep-unattributed (rep_id null) — dashboards
    bucket those as 'Unattributed'. lead_id/offer_id reference WGR ids stored as
    plain strings (the matching CI lead/offer carries source='wgr')."""

    __tablename__ = "closed_sales"

    sale_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    lead_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ghl_contact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    offer_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    rep_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_reps.rep_id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    product_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_collected: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    revenue_earned: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    time_to_close_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SalesActivity(Base):
    """Every rep touchpoint (DM/SMS/call/email). Large (~19k). ~83% have null
    rep_id (attribution gap) — keep nullable; attribution backfill is deferred."""

    __tablename__ = "sales_activities"

    activity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rep_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("sales_reps.rep_id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    business_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    activity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    ghl_event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ghl_resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )
    activity_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
