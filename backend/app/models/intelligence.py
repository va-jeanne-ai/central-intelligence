"""Intelligence domain models: InsightTag, TagDictionary, MarketSignal, Offer,
BusinessProfile, MonthlyPreference."""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    DateTime,
    ForeignKey,
    Integer,
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


