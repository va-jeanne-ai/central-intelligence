"""Repository layer — all database access flows through these classes."""

from app.repositories.base import RepositoryBase
from app.repositories.intelligence import (
    BusinessProfileRepository,
    InsightTagRepository,
    IntelligenceRepository,
    MarketSignalRepository,
    MonthlyPreferenceRepository,
    OfferRepository,
    TagDictionaryRepository,
)
from app.repositories.marketing import (
    AdsStatsRepository,
    DmStatsRepository,
    EmailCampaignRepository,
    FunnelEventRepository,
    FunnelStatsRepository,
    PromotionRepository,
    SocialCommentRepository,
    SocialStatsRepository,
)
from app.repositories.operational import (
    CallRepository,
    ContentIdeaRepository,
    GoalRepository,
    InsightRepository,
    LeadRepository,
    MemberRepository,
    ObjectionRepository,
    PainPointRepository,
    WinRepository,
)

__all__ = [
    "RepositoryBase",
    # operational
    "LeadRepository",
    "MemberRepository",
    "CallRepository",
    "InsightRepository",
    "ContentIdeaRepository",
    "GoalRepository",
    "PainPointRepository",
    "WinRepository",
    "ObjectionRepository",
    # intelligence
    "IntelligenceRepository",
    "MarketSignalRepository",
    "InsightTagRepository",
    "TagDictionaryRepository",
    "OfferRepository",
    "BusinessProfileRepository",
    "MonthlyPreferenceRepository",
    # marketing
    "SocialStatsRepository",
    "SocialCommentRepository",
    "EmailCampaignRepository",
    "FunnelEventRepository",
    "FunnelStatsRepository",
    "AdsStatsRepository",
    "DmStatsRepository",
    "PromotionRepository",
]
