"""Intelligence domain models: InsightTag, TagDictionary, MarketSignal, Offer,
BusinessProfile, MonthlyPreference."""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TagDictionary(Base):
    """Canonical tag vocabulary used to label insights."""

    __tablename__ = "tag_dictionary"

    tag: Mapped[str] = mapped_column(String(128), primary_key=True)
    tag_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synonyms: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    insight_tags: Mapped[list["InsightTag"]] = relationship(
        "InsightTag", back_populates="tag_entry", lazy="select"
    )


class InsightTag(Base):
    """Association between an Insight and a tag from TagDictionary."""

    __tablename__ = "insight_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    insight_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    tag: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("tag_dictionary.tag", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    insight: Mapped["Insight | None"] = relationship(  # type: ignore[name-defined]
        "Insight", back_populates="tags", lazy="select"
    )
    tag_entry: Mapped["TagDictionary | None"] = relationship(
        "TagDictionary", back_populates="insight_tags", lazy="select"
    )


class MarketSignal(Base):
    """Aggregated signal frequency across all calls, updated by intelligence pipeline."""

    __tablename__ = "market_signals"
    __table_args__ = (
        # Natural aggregation key — the market_signals recompute job upserts on
        # this via INSERT ... ON CONFLICT (signal_family, signal).
        UniqueConstraint("signal_family", "signal", name="uq_market_signals_family_signal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_family: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    signal: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    insight_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_mentions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_30_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_7_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    example_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_call_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
    )
    best_marketing_angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Offer(Base):
    """Product or service offer available in the business catalog.

    NOTE: this table is the app's own CRUD catalog (see
    ``backend/app/routes/offers.py`` — POST creates rows here) and today
    holds 18 rows of test data ("This is a new offer", "just checking") —
    the real WGR offers were never synced into it. Deliberately left alone
    (never clobbered) so the create/edit CRUD flow keeps working; the real
    synced catalog lives in ``WgrOffer``/``WgrOfferMapping`` below."""

    __tablename__ = "offers"

    offer_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offer_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="Active", nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class WgrOffer(Base):
    """Mirror of WGR's real `offers` table (11 rows: e.g. "Agent Infopreneur
    Accelerator - PIF" / Coaching / $10,000 / Active). Distinct from the
    app-CRUD `Offer` above — this is the real product catalog, synced
    read-only via snapshot reconcile (same precedent as `LeadJourney` /
    `MetaCampaign`: upstream is small and can be fully re-read each run).
    `closed_sales.offer_id` references this table's `offer_id` (plain string
    join, no FK — mirror data, consistent with the rest of the WGR mirrors)."""

    __tablename__ = "wgr_offers"

    offer_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    offer_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WgrOfferMapping(Base):
    """Mirror of WGR's `offer_mappings` (15 rows): per-program payment-level
    rows (e.g. program='accelerator', payment_level='pif') pointing at a
    `WgrOffer.offer_id`, carrying the per-payment-level amount_collected /
    revenue_earned. No upstream primary key — `(program, payment_level,
    offer_id)` is verified unique across all 15 rows (probe 2026-08-04), so
    that composite is used as the CI primary key for snapshot reconcile."""

    __tablename__ = "wgr_offer_mappings"

    id: Mapped[str] = mapped_column(String(384), primary_key=True)
    program: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    offer_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount_collected: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    revenue_earned: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WgrCommentEvent(Base):
    """Mirror of WGR's `comment_events` (15,855 rows) — one row per IG/FB
    comment that matched a configured lead-generation keyword. Feeds the
    "Leads by Day" table on the social page (deliverable 1 — Greg-spec
    rebuild): day-bucketed by `occurred_at` in the tenant timezone, mirroring
    the semantics of WGR's own `comment_leads_by_day()` RPC. Snapshot
    reconciled (natural upstream PK `id`, verified unique/non-null,
    probe 2026-08-04) — same precedent as `WgrOffer` / `LeadJourney`."""

    __tablename__ = "wgr_comment_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ghl_contact_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ghl_conversation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    keyword: Mapped[str | None] = mapped_column(String(128), nullable=True)
    post_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    fb_page_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    fb_page_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WgrPostCommentLead(Base):
    """Mirror of WGR's `post_comment_leads` (2,754 rows) — precomputed
    per-post/keyword lead rollup (`keyword_counts` jsonb + `total_leads`),
    keyed by `ig_media_id`. Feeds the per-post lead counts and per-keyword
    stat cards on the social page, joined against `instagram_posts` on
    `ig_media_id`. Snapshot reconciled (natural upstream PK `ig_media_id`,
    verified unique/non-null, probe 2026-08-04)."""

    __tablename__ = "wgr_post_comment_leads"

    ig_media_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shortcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    permalink: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_reel: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    keyword_counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_leads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_lead_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_lead_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BusinessProfile(Base):
    """Singleton-style business configuration record."""

    __tablename__ = "business_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mission: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_voice: Mapped[str | None] = mapped_column(Text, nullable=True)
    core_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_differentiators: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_market: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MonthlyPreference(Base):
    """Monthly content and campaign preferences keyed by month/year."""

    __tablename__ = "monthly_preferences"

    __table_args__ = (UniqueConstraint("month", "year", name="uq_monthly_preferences_month_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sending_days: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    emails_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    primary_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    secondary_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_offers: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ForesightRecommendation(Base):
    """Nightly-computed Foresight P1 card (see docs/superpowers/plans/
    2026-08-06-foresight-layer-prototype.md). ``id`` is the candidate slug
    (e.g. "live_watch") — a full delete+insert overwrite each run, since
    this is OUR computed table (not a WGR mirror needing snapshot-reconcile
    machinery). ``confidence``/``hold_reason`` are mutually meaningful:
    published cards carry confidence and no hold_reason; gated cards carry
    hold_reason and no confidence."""

    __tablename__ = "foresight_recommendations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(String(32), nullable=False)
    hindsight_headline: Mapped[str] = mapped_column(Text, nullable=False)
    hindsight_detail: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_href: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_label: Mapped[str] = mapped_column(Text, nullable=False)
    insight_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    lift_text: Mapped[str] = mapped_column(Text, nullable=False)
    hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_label: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_rate: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_low: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_high: Mapped[float] = mapped_column(Float, nullable=False)
    variant_label: Mapped[str] = mapped_column(Text, nullable=False)
    variant_rate: Mapped[float] = mapped_column(Float, nullable=False)
    variant_low: Mapped[float] = mapped_column(Float, nullable=False)
    variant_high: Mapped[float] = mapped_column(Float, nullable=False)
    n_label: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Hysteresis streak (app.services.foresight.apply_hysteresis): how many
    # CONSECUTIVE nightly runs the raw statistical verdict has cleared while
    # the displayed status is still gated. Reset to 0 once published, and
    # reset to 0 on any night the raw verdict fails to clear. Read BEFORE
    # the delete+insert each run so the state machine has its prior state.
    consecutive_clear_nights: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


