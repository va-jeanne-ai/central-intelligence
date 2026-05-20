"""Cross-domain intelligence repository for aggregated market analysis queries."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import (
    BusinessProfile,
    InsightTag,
    MarketSignal,
    MonthlyPreference,
    Offer,
    TagDictionary,
)
from app.models.operational import Insight
from app.repositories.base import RepositoryBase


class MarketSignalRepository(RepositoryBase[MarketSignal]):
    """Repository for MarketSignal aggregation records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MarketSignal)

    async def find_by_signal_family(
        self, signal_family: str, limit: int = 50
    ) -> list[MarketSignal]:
        """Return market signals belonging to a specific family, ranked by total_mentions."""
        stmt = (
            select(MarketSignal)
            .where(MarketSignal.signal_family == signal_family)
            .order_by(MarketSignal.total_mentions.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_trending(self, limit: int = 20) -> list[MarketSignal]:
        """Return signals with the highest activity in the last 7 days."""
        stmt = (
            select(MarketSignal)
            .where(MarketSignal.last_7_days > 0)
            .order_by(MarketSignal.last_7_days.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_top_overall(self, limit: int = 20) -> list[MarketSignal]:
        """Return the most-mentioned signals across all time."""
        stmt = (
            select(MarketSignal)
            .order_by(MarketSignal.total_mentions.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_signal(
        self,
        signal_family: str,
        signal: str,
        insight_type: str | None = None,
        example_quote: str | None = None,
        example_call_id: str | None = None,
    ) -> MarketSignal:
        """Increment counters on an existing signal row, or create it.

        This is a simple application-level upsert. For high-concurrency use,
        consider a database-level INSERT ... ON CONFLICT.
        """
        stmt = select(MarketSignal).where(
            MarketSignal.signal_family == signal_family,
            MarketSignal.signal == signal,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            row = MarketSignal(
                signal_family=signal_family,
                signal=signal,
                insight_type=insight_type,
                total_mentions=1,
                last_30_days=1,
                last_7_days=1,
                example_quote=example_quote,
                example_call_id=example_call_id,
            )
            self.session.add(row)
        else:
            row.total_mentions = (row.total_mentions or 0) + 1
            row.last_30_days = (row.last_30_days or 0) + 1
            row.last_7_days = (row.last_7_days or 0) + 1
            if example_quote:
                row.example_quote = example_quote
            if example_call_id:
                row.example_call_id = example_call_id

        await self.session.flush()
        await self.session.refresh(row)
        return row


class InsightTagRepository(RepositoryBase[InsightTag]):
    """Repository for InsightTag association records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InsightTag)

    async def find_by_insight(self, insight_id: str) -> list[InsightTag]:
        """Return all tags attached to an insight."""
        stmt = select(InsightTag).where(InsightTag.insight_id == insight_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_tag(self, tag: str, limit: int = 100) -> list[InsightTag]:
        """Return all InsightTag rows carrying a specific tag."""
        stmt = select(InsightTag).where(InsightTag.tag == tag).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def tag_frequency(self, limit: int = 30) -> list[dict[str, Any]]:
        """Return tags ranked by how many insights they label.

        Returns a list of dicts with keys ``tag`` and ``count``.
        """
        stmt = (
            select(InsightTag.tag, func.count(InsightTag.id).label("count"))
            .group_by(InsightTag.tag)
            .order_by(func.count(InsightTag.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [{"tag": row.tag, "count": row.count} for row in result.all()]


class TagDictionaryRepository(RepositoryBase[TagDictionary]):
    """Repository for the canonical tag vocabulary."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TagDictionary)

    async def find_by_type(self, tag_type: str) -> list[TagDictionary]:
        """Return all dictionary entries belonging to a tag type."""
        stmt = select(TagDictionary).where(TagDictionary.tag_type == tag_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def all_tags(self) -> list[str]:
        """Return all canonical tag strings."""
        stmt = select(TagDictionary.tag).order_by(TagDictionary.tag)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class OfferRepository(RepositoryBase[Offer]):
    """Repository for Offer catalog records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Offer)

    async def find_active(self) -> list[Offer]:
        """Return all offers with status 'Active'."""
        stmt = select(Offer).where(Offer.status == "Active").order_by(Offer.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_type(self, offer_type: str) -> list[Offer]:
        """Return offers filtered by type, e.g. 'Coaching', 'Course', 'Product'."""
        stmt = select(Offer).where(Offer.offer_type == offer_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_generated_offer(
        self,
        offer_id: str,
        name: str,
        offer_type: str,
        description: str,
        price: float | None = None,
        notes: str | None = None,
    ) -> Offer:
        """Persist a generated offer draft to the offers table.

        Sprint 4b / OPS-O3 — Store to offers table.
        Sets status to 'Draft' for human review before activation.
        """
        offer = Offer(
            offer_id=offer_id,
            name=name,
            offer_type=offer_type,
            description=description,
            price=price,
            status="Draft",
            notes=notes,
        )
        self.session.add(offer)
        await self.session.flush()
        await self.session.refresh(offer)
        return offer


class BusinessProfileRepository(RepositoryBase[BusinessProfile]):
    """Repository for the singleton BusinessProfile configuration."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, BusinessProfile)

    async def get_active(self) -> BusinessProfile | None:
        """Return the most recently updated business profile record."""
        stmt = select(BusinessProfile).order_by(BusinessProfile.updated_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, **kwargs: Any) -> BusinessProfile:
        """Update the active profile or create one if none exists."""
        profile = await self.get_active()
        if profile is None:
            profile = BusinessProfile(**kwargs)
            self.session.add(profile)
        else:
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile


class MonthlyPreferenceRepository(RepositoryBase[MonthlyPreference]):
    """Repository for MonthlyPreference campaign settings."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MonthlyPreference)

    async def find_by_month_year(
        self, month: int, year: int
    ) -> MonthlyPreference | None:
        """Return the preference record for a specific month/year combination."""
        stmt = select(MonthlyPreference).where(
            MonthlyPreference.month == month,
            MonthlyPreference.year == year,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_year(self, year: int) -> list[MonthlyPreference]:
        """Return all monthly preference records for the given year."""
        stmt = (
            select(MonthlyPreference)
            .where(MonthlyPreference.year == year)
            .order_by(MonthlyPreference.month)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class IntelligenceRepository:
    """Facade for cross-domain intelligence queries.

    Composes multiple sub-repositories to answer analytical questions that
    span insight, tag, market-signal, and offer data in a single call.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.market_signals = MarketSignalRepository(session)
        self.insight_tags = InsightTagRepository(session)
        self.tag_dictionary = TagDictionaryRepository(session)
        self.offers = OfferRepository(session)
        self.business_profile = BusinessProfileRepository(session)
        self.monthly_preferences = MonthlyPreferenceRepository(session)

    # ------------------------------------------------------------------
    # Cross-domain aggregation queries
    # ------------------------------------------------------------------

    async def get_signal_family_summary(
        self, signal_family: str
    ) -> dict[str, Any]:
        """Return a summary dict for a signal family.

        Includes the list of signals, aggregate mention counts, and the
        corresponding top-frequency insights.
        """
        signals = await self.market_signals.find_by_signal_family(signal_family)

        insight_stmt = (
            select(Insight)
            .where(Insight.signal_family == signal_family)
            .order_by(Insight.frequency_score.desc())
            .limit(10)
        )
        insight_result = await self.session.execute(insight_stmt)
        top_insights = list(insight_result.scalars().all())

        total = sum(s.total_mentions or 0 for s in signals)

        return {
            "signal_family": signal_family,
            "total_mentions": total,
            "signal_count": len(signals),
            "signals": [
                {
                    "signal": s.signal,
                    "total_mentions": s.total_mentions,
                    "last_30_days": s.last_30_days,
                    "last_7_days": s.last_7_days,
                }
                for s in signals
            ],
            "top_insights": [
                {
                    "id": i.id,
                    "raw_quote": i.raw_quote,
                    "frequency_score": i.frequency_score,
                    "insight_type": i.insight_type,
                }
                for i in top_insights
            ],
        }

    async def get_top_tags_with_insights(
        self, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return top tags with example insights attached to each.

        Useful for building a 'what is the market talking about' dashboard.
        """
        top_tags = await self.insight_tags.tag_frequency(limit=limit)
        enriched: list[dict[str, Any]] = []

        for entry in top_tags:
            tag_rows = await self.insight_tags.find_by_tag(entry["tag"], limit=3)
            insight_ids = [r.insight_id for r in tag_rows if r.insight_id]
            examples: list[dict[str, Any]] = []
            for iid in insight_ids:
                ins_stmt = select(Insight).where(Insight.id == iid)
                ins_result = await self.session.execute(ins_stmt)
                ins = ins_result.scalar_one_or_none()
                if ins:
                    examples.append(
                        {"id": ins.id, "raw_quote": ins.raw_quote, "insight_type": ins.insight_type}
                    )
            enriched.append(
                {
                    "tag": entry["tag"],
                    "count": entry["count"],
                    "example_insights": examples,
                }
            )

        return enriched

    async def get_content_intelligence_brief(self) -> dict[str, Any]:
        """Compile a cross-domain brief for content planning.

        Returns trending signals, top tags, active offers, and current
        monthly preferences in one round-trip.
        """
        trending = await self.market_signals.find_trending(limit=10)
        top_tags = await self.insight_tags.tag_frequency(limit=15)
        active_offers = await self.offers.find_active()
        profile = await self.business_profile.get_active()

        from datetime import datetime

        now = datetime.utcnow()
        monthly_pref = await self.monthly_preferences.find_by_month_year(now.month, now.year)

        return {
            "generated_at": now.isoformat(),
            "trending_signals": [
                {
                    "signal_family": s.signal_family,
                    "signal": s.signal,
                    "last_7_days": s.last_7_days,
                    "best_marketing_angle": s.best_marketing_angle,
                }
                for s in trending
            ],
            "top_tags": top_tags,
            "active_offers": [
                {"offer_id": o.offer_id, "name": o.name, "offer_type": o.offer_type}
                for o in active_offers
            ],
            "business_profile": {
                "business_name": profile.business_name if profile else None,
                "brand_voice": profile.brand_voice if profile else None,
                "primary_market": profile.primary_market if profile else None,
            },
            "monthly_preferences": {
                "month": monthly_pref.month if monthly_pref else now.month,
                "year": monthly_pref.year if monthly_pref else now.year,
                "primary_goal": monthly_pref.primary_goal if monthly_pref else None,
                "emails_per_week": monthly_pref.emails_per_week if monthly_pref else None,
                "active_offers": monthly_pref.active_offers if monthly_pref else [],
            },
        }
