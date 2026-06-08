"""Operational domain models: Lead, Member, Call, Insight, ContentIdea, Goal,
PainPoint, Win, Objection."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# pgvector adapter — Vector(1024) is the SQLAlchemy type for the
# Voyage voyage-3 embedding column on the embeddings table.
from pgvector.sqlalchemy import Vector

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Lead(Base, TimestampMixin, SoftDeleteMixin):
    """Prospective client who has not yet enrolled as a member."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Stable upstream identifier from the source provider (e.g. GHL
    # contact_id). When source + external_id are both present, the lead
    # webhook upsert dedups on the pair — surviving email-changes and
    # rename storms. Partial unique index enforces this at the DB level.
    external_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="lead", lazy="select")
    goals: Mapped[list["Goal"]] = relationship("Goal", back_populates="lead", lazy="select")
    pain_points: Mapped[list["PainPoint"]] = relationship(
        "PainPoint", back_populates="lead", lazy="select"
    )
    objections: Mapped[list["Objection"]] = relationship(
        "Objection", back_populates="lead", lazy="select"
    )
    # Append-only staff-side journal entries. Distinct from `notes` (which
    # carries the immutable upstream provider payload, e.g. the raw GHL
    # webhook body). Newest first.
    staff_notes: Mapped[list["LeadNote"]] = relationship(
        "LeadNote",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadNote.created_at.desc()",
        lazy="select",
    )
    # Gmail threads where this lead's email address appears. Filled by
    # the nightly + on-demand sync task. Most recent thread first.
    email_threads: Mapped[list["EmailThread"]] = relationship(
        "EmailThread",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="EmailThread.last_message_at.desc()",
        lazy="select",
    )


class Member(Base, TimestampMixin, SoftDeleteMixin):
    """Active enrolled client receiving coaching services."""

    __tablename__ = "members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    enrollment_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    coach_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="member", lazy="select")
    goals: Mapped[list["Goal"]] = relationship("Goal", back_populates="member", lazy="select")
    wins: Mapped[list["Win"]] = relationship("Win", back_populates="member", lazy="select")
    pain_points: Mapped[list["PainPoint"]] = relationship(
        "PainPoint", back_populates="member", lazy="select"
    )
    staff_notes: Mapped[list["MemberNote"]] = relationship(
        "MemberNote", back_populates="member", lazy="select"
    )


class Call(Base, SoftDeleteMixin):
    """Recorded coaching or sales call.

    Primary key uses the string format CALL_xxx to match upstream identifiers
    from transcript ingestion pipelines.
    """

    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    call_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    call_result: Mapped[str | None] = mapped_column(String(128), nullable=True)
    call_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transcript_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transcript_uid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transcript_quality: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    processed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    call_duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    insights: Mapped[list["Insight"]] = relationship(
        "Insight", back_populates="call", lazy="select"
    )
    content_ideas: Mapped[list["ContentIdea"]] = relationship(
        "ContentIdea", back_populates="call", lazy="select"
    )
    lead: Mapped["Lead | None"] = relationship("Lead", back_populates="calls", lazy="select")
    member: Mapped["Member | None"] = relationship(
        "Member", back_populates="calls", lazy="select"
    )


class Insight(Base):
    """Extracted insight from a call transcript.

    Primary key uses the string format INS_xxx to match pipeline identifiers.
    """

    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    call_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    speaker_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insight_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    signal_family: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    signal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signal_strength: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pain_layer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_they_say: Mapped[str | None] = mapped_column(Text, nullable=True)
    the_real_problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotional_driver: Mapped[str | None] = mapped_column(Text, nullable=True)
    core_fear_revealed: Mapped[str | None] = mapped_column(Text, nullable=True)
    false_belief_revealed: Mapped[str | None] = mapped_column(Text, nullable=True)
    structural_obstacle: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_signal: Mapped[str | None] = mapped_column(Text, nullable=True)
    buying_trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    objection_created: Mapped[str | None] = mapped_column(Text, nullable=True)
    marketing_translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook_angle_example: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_use_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_confidence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    frequency_score: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    call: Mapped["Call | None"] = relationship("Call", back_populates="insights", lazy="select")
    tags: Mapped[list["InsightTag"]] = relationship(  # type: ignore[name-defined]
        "InsightTag", back_populates="insight", lazy="select"
    )
    content_ideas: Mapped[list["ContentIdea"]] = relationship(
        "ContentIdea", back_populates="insight", lazy="select"
    )


class ContentIdea(Base, SoftDeleteMixin):
    """Marketing/content idea derived from a call insight.

    Primary key uses the string format CONT_xxx.
    """

    __tablename__ = "content_ideas"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    insight_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("insights.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    call_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    market_audience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_format: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_angle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_premise: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook_opening_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    teaching_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_idea: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    best_platform: Mapped[str | None] = mapped_column(String(128), nullable=True)
    repurpose_opportunities: Mapped[str | None] = mapped_column(Text, nullable=True)
    idea_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="Idea", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    insight: Mapped["Insight | None"] = relationship(
        "Insight", back_populates="content_ideas", lazy="select"
    )
    call: Mapped["Call | None"] = relationship(
        "Call", back_populates="content_ideas", lazy="select"
    )


class Goal(Base, SoftDeleteMixin):
    """Goal associated with a member or lead."""

    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    goal_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    member: Mapped["Member | None"] = relationship(
        "Member", back_populates="goals", lazy="select"
    )
    lead: Mapped["Lead | None"] = relationship("Lead", back_populates="goals", lazy="select")


class PainPoint(Base, SoftDeleteMixin):
    """Recurring pain point associated with a member or lead."""

    __tablename__ = "pain_points"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    frequency_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    member: Mapped["Member | None"] = relationship(
        "Member", back_populates="pain_points", lazy="select"
    )
    lead: Mapped["Lead | None"] = relationship(
        "Lead", back_populates="pain_points", lazy="select"
    )


class Win(Base, SoftDeleteMixin):
    """Positive outcome or success story for a member."""

    __tablename__ = "wins"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    win_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    win_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    impact_area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    member: Mapped["Member | None"] = relationship(
        "Member", back_populates="wins", lazy="select"
    )


class Objection(Base, SoftDeleteMixin):
    """Sales objection raised by a lead during a call."""

    __tablename__ = "objections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    objection_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_offered: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    lead: Mapped["Lead | None"] = relationship(
        "Lead", back_populates="objections", lazy="select"
    )


class ICP(Base, SoftDeleteMixin):
    """Ideal Customer Profile segment."""

    __tablename__ = "icp"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    segment: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    demographics: Mapped[str | None] = mapped_column(Text, nullable=True)
    psychographics: Mapped[str | None] = mapped_column(Text, nullable=True)
    pain_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    buying_triggers: Mapped[str | None] = mapped_column(Text, nullable=True)
    common_objections: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LeadNote(Base):
    """Append-only staff journal entry attached to a Lead.

    Distinct from ``lead.notes`` (which carries the immutable provider
    payload, e.g. the raw GHL webhook body). Each row is one staff-side
    observation/reminder, displayed as a timeline on the lead detail
    page. Most recent first.
    """

    __tablename__ = "lead_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable: covers system-generated notes, mock-mode posts, and rows
    # whose author was later deleted (FK is SET NULL).
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="staff_notes")


class MemberNote(Base):
    """Append-only staff journal entry attached to a Member.

    Mirrors ``LeadNote`` for the fulfillment side. Each row is one
    staff-side observation/reminder, displayed as a timeline on the
    member detail page. Most recent first.
    """

    __tablename__ = "member_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable: covers system-generated notes, mock-mode posts, and rows
    # whose author was later deleted (FK is SET NULL).
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    member: Mapped["Member"] = relationship("Member", back_populates="staff_notes")


class EmailThread(Base):
    """One Gmail thread linked to a lead via the email-address match.

    Created by the nightly Celery sync task (and the per-lead on-demand
    variant). The same Gmail thread can in theory match multiple leads
    if they share an email address — but `Lead.email` is unique-indexed,
    so one (lead_id, provider_thread_id) row per real thread is enough.

    last_message_at + message_count are denormalised so the lead-detail
    GET doesn't need an aggregate query per row. The upsert helper keeps
    them in sync whenever a new message lands.
    """

    __tablename__ = "email_threads"
    __table_args__ = (
        UniqueConstraint(
            "lead_id", "provider_thread_id",
            name="uq_email_threads_lead_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="email_threads")
    messages: Mapped[list["EmailMessage"]] = relationship(
        "EmailMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="EmailMessage.sent_at",
        lazy="select",
    )


class EmailMessage(Base):
    """One Gmail message inside a thread.

    Body is plain-text only (the ``text/plain`` MIME part); we explicitly
    don't store or render HTML. Attachments are recorded as metadata
    (filename + size + mime) but bytes are not downloaded — staff click
    through to Gmail for the file itself.
    """

    __tablename__ = "email_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_message_id: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True,
    )
    from_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_addresses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cc_addresses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    has_attachments: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    attachments_meta: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    thread: Mapped["EmailThread"] = relationship(
        "EmailThread", back_populates="messages",
    )


class GoogleDriveFile(Base):
    """One file in a connected user's Drive.

    Synced by ``tasks/drive_sync.py``. The same Drive file appearing in
    two users' mailboxes lands as two rows (different
    ``connected_via_user_id``); dedup happens on read in the chat
    surface and lead documents card.

    ``extracted_text`` caches the plain-text body produced by
    ``drive_client.fetch_file_content`` — parsed once at sync time and
    re-used by the embed worker. ``content_hash`` is the sha256 of
    ``extracted_text or name`` and is diffed against the most-recent
    ``embeddings`` row to decide whether to re-embed.
    """

    __tablename__ = "google_drive_files"
    __table_args__ = (
        UniqueConstraint(
            "provider_file_id", "connected_via_user_id",
            name="uq_google_drive_files_provider_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    connected_via_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_file_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    modified_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    web_view_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_folder_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
    )
    parent_folder_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSONB array of lowercase emails. GIN-indexed for containment queries
    # in the lead documents card ("files where lead.email ∈ shared_with").
    shared_with: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_trashed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GoogleCalendarEvent(Base):
    """One calendar event from a connected user's Google Workspace.

    Synced by ``tasks/calendar_sync.py``. The same event in two users'
    calendars (e.g. a shared meeting) lands as two rows (different
    ``connected_via_user_id``). Dedup happens on read.

    Recurring events are stored as **expanded instances** —
    ``events.list?singleEvents=true`` on the Google API returns one
    row per occurrence, each with its own ``provider_event_id``
    (parent id + RFC5545 timestamp suffix). That way the chat can
    answer "what's on Tuesday at 9am" with a concrete row, not by
    computing recurrence client-side.

    ``extracted_text`` caches the title + description + attendees
    concatenation used by the embed worker. ``content_hash`` is the
    sha256 of that text and gates re-embedding.
    """

    __tablename__ = "google_calendar_events"
    __table_args__ = (
        UniqueConstraint(
            "provider_event_id", "connected_via_user_id",
            name="uq_google_calendar_events_provider_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    connected_via_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(256), nullable=False)
    calendar_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    organizer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # JSONB array of {email, displayName, responseStatus} dicts.
    # GIN-indexed; lead-detail card and chat tool filter on it.
    attendees: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    is_all_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    event_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recurring_event_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EmbedPending(Base):
    """FIFO queue of (source_table, source_id) waiting to be embedded.

    Generic across sources — Drive files, email messages, lead notes,
    and call insights all enqueue into the same table. The embed worker
    drains in ``created_at`` order without caring about source type.
    """

    __tablename__ = "embed_pending"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_table: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    text_to_embed: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Embedding(Base):
    """One pgvector-1024 chunk embedding.

    Polymorphic via (source_table, source_id). ``chunk_index`` lets one
    source row produce many chunks; the UNIQUE on the triple makes the
    INSERT idempotent.
    """

    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint(
            "source_table", "source_id", "chunk_index",
            name="uq_embeddings_source_chunk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_table: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )
    text_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class EmbeddingBudget(Base):
    """Single-row global daily-token cap.

    The embed worker checks ``tokens_used_today`` against
    ``daily_token_cap`` before each batch; if at cap, it skips the tick
    and logs. ``usage_window_started_at`` rolls over after 24h, at
    which point the worker resets ``tokens_used_today`` to 0.
    """

    __tablename__ = "embedding_budget"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, server_default="1",
    )
    daily_token_cap: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="50000000",
    )
    tokens_used_today: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0",
    )
    usage_window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class UserIntegrationCredential(Base):
    """Per-user OAuth refresh-token storage for third-party integrations.

    Companion to the deployment-wide ``Integration`` row. Each user
    that connects their own Google account gets one row per provider.
    The encrypted blob carries the refresh token (long-lived) + the
    most recent access token + the token endpoint + the client_id and
    secret used to mint it.

    Used today by the Gmail per-user sync; Drive and Calendar will
    reuse the same table with different ``provider`` values.
    """

    __tablename__ = "user_integration_credentials"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "provider",
            name="uq_user_integration_credentials_user_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    connected_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
