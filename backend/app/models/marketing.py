"""Marketing domain models: SocialStats, SocialComment, EmailCampaign,
FunnelEvent, FunnelStats.

Sprint 3 — social media, email marketing, and funnel data persistence.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class SocialStats(Base, TimestampMixin, SoftDeleteMixin):
    """Aggregated social media metrics per platform and time period."""

    __tablename__ = "social_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    followers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SocialComment(Base, TimestampMixin):
    """Individual social media comment collected for Voice-of-Customer analysis."""

    __tablename__ = "social_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    commented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sentiment: Mapped[str | None] = mapped_column(String(64), nullable=True)


class EmailCampaign(Base, TimestampMixin, SoftDeleteMixin):
    """Email campaign with performance metrics."""

    __tablename__ = "email_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    campaign_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recipients_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unsubscribe_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bounce_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    click_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Provenance: which integration (or local source) produced this row.
    # Values: "mailchimp" | "seed" | "manual" | NULL (pre-tagging rows).
    # Used by the dashboard to badge each campaign with its source and by
    # the email-stats Celery task to dedup against external_id when the
    # provider supplies a stable identifier.
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    # Stable upstream identifier from the source provider (e.g. Mailchimp
    # campaign_id). When present, the email-stats task dedups on
    # (source, external_id) instead of name — so renames in Mailchimp
    # update the existing row rather than inserting a duplicate.
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Audience (Mailchimp list name, e.g. "Subscribers — newsletter").
    audience_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Segment description if the campaign was sent to a slice rather than the
    # whole list (e.g. "members who clicked the last campaign"). Free text;
    # Mailchimp constructs it dynamically.
    segment_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rendered HTML body. Pulled from /3.0/campaigns/{id}/content. Can be
    # large (50-500KB) — kept here for read-only preview in a sandboxed
    # iframe. Editing happens in Mailchimp; we never write back.
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Public archive URL on Mailchimp's side. Lets users open the rendered
    # campaign in a new tab when the inline iframe isn't enough.
    archive_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Page-builder block source for manual drafts. JSON-serialized Block[]
    # from frontend/src/components/email/blocks/types.ts. Populated by the
    # /email/campaigns POST when the compose page sends it; nullable for
    # legacy rows (drafts saved before block editing) and for Mailchimp-
    # sourced rows (no block representation upstream). When set, the
    # compose page can round-trip — load → edit → save back to the same
    # row — without losing fidelity.
    blocks_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class FunnelEvent(Base, TimestampMixin):
    """Raw funnel conversion event received via webhook."""

    __tablename__ = "funnel_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    funnel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class FunnelStats(Base, TimestampMixin):
    """Aggregated funnel metrics per funnel, stage, and time period."""

    __tablename__ = "funnel_stats"
    __table_args__ = (
        UniqueConstraint(
            "funnel_id", "stage", "period_start",
            name="uq_funnel_stats_funnel_stage_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    funnel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AdsStats(Base, TimestampMixin, SoftDeleteMixin):
    """Aggregated paid advertising metrics per platform and campaign."""

    __tablename__ = "ads_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spend: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    roas: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DmStats(Base, TimestampMixin, SoftDeleteMixin):
    """Aggregated DM outreach metrics per platform."""

    __tablename__ = "dm_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outreach_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    responses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_responses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meetings_booked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Promotion(Base, TimestampMixin, SoftDeleteMixin):
    """Promotional campaign entry for the promo calendar."""

    __tablename__ = "promotions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    promo_type: Mapped[str] = mapped_column(String(64), nullable=False, default="campaign")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="planned", nullable=False)
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
