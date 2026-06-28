"""SQLAlchemy model registry.

Import order matters: meta must come before operational (User/Team are FK targets),
and intelligence must come before the forward-reference resolution at the bottom of
operational.py.  All 21 models are exposed at the package level so Alembic's
autogenerate can discover every table via Base.metadata.
"""

from app.models.base import Base, SoftDeleteMixin, TimestampMixin  # noqa: F401

# meta — no internal FK dependencies
from app.models.meta import Team, User  # noqa: F401

# intelligence — TagDictionary & InsightTag must exist before Insight.tags resolves
from app.models.intelligence import (  # noqa: F401
    BusinessProfile,
    InsightTag,
    MarketSignal,
    MonthlyPreference,
    Offer,
    TagDictionary,
)

# operational — depends on User (created_by / coach_id) and InsightTag (relationship)
from app.models.operational import (  # noqa: F401
    Appointment,
    Call,
    ContentIdea,
    EmailMessage,
    EmailThread,
    EmbedPending,
    Embedding,
    EmbeddingBudget,
    Goal,
    GoogleCalendarEvent,
    GoogleDriveFile,
    Insight,
    Lead,
    LeadNote,
    Member,
    MemberNote,
    Objection,
    SupportTicket,
    PainPoint,
    UserIntegrationCredential,
    Win,
)

# marketing — Sprint 3/4 social/email/funnel/ads/dm/promo + WGR webinar/opt-in
from app.models.marketing import (  # noqa: F401
    AdsStats,
    DmStats,
    EmailCampaign,
    FunnelEvent,
    FunnelStats,
    InstagramPost,
    OptInEvent,
    Promotion,
    SocialComment,
    SocialStats,
    WebinarEngagement,
)

# sales — WGR-sourced rep/coaching/revenue/activity subsystems (rep_id self-FKs)
from app.models.sales import (  # noqa: F401
    CallScore,
    ClosedSale,
    CoachingStrike,
    EodReport,
    RepOverride,
    SalesActivity,
    SalesRep,
    ScorecardCategory,
    StrikeAction,
    StrikeEvidence,
    StrikeRule,
)

# audit — depends on User (user_id FK)
from app.models.audit import (  # noqa: F401
    AuditLog,
    ErrorLog,
    IdempotencyKey,
    SyncLog,
)

# integrations — no FK dependencies (tenant_id is FK-less for now)
from app.models.integration import Integration  # noqa: F401

# chat — depends on User (user_id FK)
from app.models.chat import ChatMessage, ChatSession  # noqa: F401

__all__ = [
    # base
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    # meta
    "User",
    "Team",
    # intelligence
    "InsightTag",
    "TagDictionary",
    "MarketSignal",
    "Offer",
    "BusinessProfile",
    "MonthlyPreference",
    # operational
    "Lead",
    "Member",
    "Appointment",
    "SupportTicket",
    "Call",
    "Insight",
    "ContentIdea",
    "Goal",
    "PainPoint",
    "Win",
    "LeadNote",
    "MemberNote",
    "EmailThread",
    "EmailMessage",
    "UserIntegrationCredential",
    "GoogleDriveFile",
    "GoogleCalendarEvent",
    "EmbedPending",
    "Embedding",
    "EmbeddingBudget",
    "Objection",
    # marketing
    "SocialStats",
    "SocialComment",
    "InstagramPost",
    "EmailCampaign",
    "FunnelEvent",
    "FunnelStats",
    "AdsStats",
    "DmStats",
    "Promotion",
    "WebinarEngagement",
    "OptInEvent",
    # sales (WGR)
    "SalesRep",
    "RepOverride",
    "ScorecardCategory",
    "CallScore",
    "StrikeRule",
    "CoachingStrike",
    "StrikeAction",
    "StrikeEvidence",
    "EodReport",
    "ClosedSale",
    "SalesActivity",
    # audit
    "AuditLog",
    "ErrorLog",
    "SyncLog",
    "IdempotencyKey",
    # integrations
    "Integration",
    # chat
    "ChatSession",
    "ChatMessage",
]
