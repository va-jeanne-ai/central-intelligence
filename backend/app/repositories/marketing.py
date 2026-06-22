"""Concrete repositories for Sprint 3 marketing domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketing import (
    AdsStats,
    DmStats,
    EmailCampaign,
    FunnelEvent,
    FunnelStats,
    InstagramPost,
    Promotion,
    SocialComment,
    SocialStats,
)
from app.repositories.base import RepositoryBase


class SocialStatsRepository(RepositoryBase[SocialStats]):
    """Repository for SocialStats — aggregated social media metrics."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SocialStats)

    async def find_by_platform(
        self, platform: str, limit: int = 100
    ) -> list[SocialStats]:
        stmt = (
            self._base_select()
            .where(SocialStats.platform == platform)
            .order_by(SocialStats.period_end.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_latest_by_platform(
        self, platform: str
    ) -> Optional[SocialStats]:
        stmt = (
            self._base_select()
            .where(SocialStats.platform == platform)
            .order_by(SocialStats.period_end.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def aggregate_totals(self) -> dict:
        """Return totals across the latest stats row per platform.

        Uses a subquery to pick only the most recent period_end per platform,
        then aggregates across those rows.
        """
        # Subquery: latest period_end per platform
        latest_sq = (
            select(
                SocialStats.platform,
                func.max(SocialStats.period_end).label("max_period_end"),
            )
            .where(SocialStats.deleted_at.is_(None))
            .group_by(SocialStats.platform)
            .subquery()
        )

        stmt = (
            select(
                func.coalesce(func.sum(SocialStats.followers), 0).label("total_followers"),
                func.coalesce(func.sum(SocialStats.posts_count), 0).label("total_posts"),
                func.coalesce(func.avg(SocialStats.engagement_rate), 0.0).label("avg_engagement"),
            )
            .join(
                latest_sq,
                (SocialStats.platform == latest_sq.c.platform)
                & (SocialStats.period_end == latest_sq.c.max_period_end),
            )
            .where(SocialStats.deleted_at.is_(None))
        )

        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "total_followers": int(row.total_followers),
            "total_posts": int(row.total_posts),
            "avg_engagement": float(row.avg_engagement),
        }

    async def upsert_stats(
        self,
        platform: str,
        period_start: datetime,
        period_end: datetime,
        **metrics,
    ) -> SocialStats:
        """Find-or-create a stats row by platform + period_start, then update."""
        stmt = (
            self._base_select()
            .where(SocialStats.platform == platform)
            .where(SocialStats.period_start == period_start)
        )
        result = await self.session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance is None:
            return await self.create(
                platform=platform,
                period_start=period_start,
                period_end=period_end,
                **metrics,
            )

        for key, value in metrics.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        instance.period_end = period_end
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance


class SocialCommentRepository(RepositoryBase[SocialComment]):
    """Repository for SocialComment — collected social media comments."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SocialComment)

    async def find_by_platform(
        self, platform: str, limit: int = 100
    ) -> list[SocialComment]:
        stmt = (
            self._base_select()
            .where(SocialComment.platform == platform)
            .order_by(SocialComment.commented_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_recent(self, limit: int = 50) -> list[SocialComment]:
        stmt = (
            self._base_select()
            .order_by(SocialComment.commented_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_post(self, post_id: str) -> list[SocialComment]:
        stmt = (
            self._base_select()
            .where(SocialComment.post_id == post_id)
            .order_by(SocialComment.commented_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class InstagramPostRepository(RepositoryBase[InstagramPost]):
    """Repository for InstagramPost — per-post Instagram performance (WGR mirror)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InstagramPost)

    async def find_recent(self, limit: int = 12) -> list[InstagramPost]:
        """Most recently published posts first (nulls last)."""
        stmt = (
            self._base_select()
            .order_by(InstagramPost.posted_at.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class EmailCampaignRepository(RepositoryBase[EmailCampaign]):
    """Repository for EmailCampaign — email campaigns with performance metrics."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmailCampaign)

    async def find_by_status(
        self, status: str, limit: int = 100
    ) -> list[EmailCampaign]:
        stmt = (
            self._base_select()
            .where(EmailCampaign.status == status)
            .order_by(EmailCampaign.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_sent(self, limit: int = 100) -> list[EmailCampaign]:
        stmt = (
            self._base_select()
            .where(EmailCampaign.status == "sent")
            .order_by(EmailCampaign.sent_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_drafts(self, limit: int = 50) -> list[EmailCampaign]:
        """Return draft campaigns, newest first by updated_at.

        Drafts have no sent_at, so we order by updated_at — the most
        recently edited drafts sit at the top of the list.
        """
        stmt = (
            self._base_select()
            .where(EmailCampaign.status == "draft")
            .order_by(EmailCampaign.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_archived(self, limit: int = 100) -> list[EmailCampaign]:
        """Return archived campaigns, most-recently-archived first.

        Archived rows are sent campaigns the user has moved out of the
        main list. They're hidden from `find_sent` but stay visible
        under the Archived section on /marketing/email so the user can
        restore them.
        """
        stmt = (
            self._base_select()
            .where(EmailCampaign.status == "archived")
            .order_by(EmailCampaign.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def aggregate_stats(self) -> dict:
        """Return count of sent campaigns and average open/click rates."""
        stmt = (
            select(
                func.count(EmailCampaign.id).label("campaigns"),
                func.coalesce(func.avg(EmailCampaign.open_rate), 0.0).label("avg_open_rate"),
                func.coalesce(func.avg(EmailCampaign.click_rate), 0.0).label("avg_click_rate"),
            )
            .where(EmailCampaign.deleted_at.is_(None))
            .where(EmailCampaign.status == "sent")
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "campaigns": int(row.campaigns),
            "avg_open_rate": round(float(row.avg_open_rate), 2),
            "avg_click_rate": round(float(row.avg_click_rate), 2),
        }

    async def upsert_campaign(self, name: str, **metrics) -> EmailCampaign:
        """Find-or-create a campaign by name, then update metrics."""
        stmt = self._base_select().where(EmailCampaign.name == name)
        result = await self.session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance is None:
            return await self.create(name=name, **metrics)

        for key, value in metrics.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance


class FunnelEventRepository(RepositoryBase[FunnelEvent]):
    """Repository for FunnelEvent — raw funnel webhook events."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FunnelEvent)

    async def find_by_funnel(
        self, funnel_id: str, limit: int = 500
    ) -> list[FunnelEvent]:
        stmt = (
            self._base_select()
            .where(FunnelEvent.funnel_id == funnel_id)
            .order_by(FunnelEvent.received_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_stage(
        self, stage: str, limit: int = 500
    ) -> list[FunnelEvent]:
        stmt = (
            self._base_select()
            .where(FunnelEvent.stage == stage)
            .order_by(FunnelEvent.received_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_funnel_and_stage(self, funnel_id: str) -> list[dict]:
        """Return event counts grouped by stage for a given funnel."""
        stmt = (
            select(
                FunnelEvent.stage,
                func.count(FunnelEvent.id).label("event_count"),
            )
            .where(FunnelEvent.funnel_id == funnel_id)
            .group_by(FunnelEvent.stage)
            .order_by(func.count(FunnelEvent.id).desc())
        )
        result = await self.session.execute(stmt)
        return [
            {"stage": row.stage, "event_count": int(row.event_count)}
            for row in result.all()
        ]


class FunnelStatsRepository(RepositoryBase[FunnelStats]):
    """Repository for FunnelStats — aggregated funnel metrics."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FunnelStats)

    async def find_by_funnel(self, funnel_id: str) -> list[FunnelStats]:
        stmt = (
            self._base_select()
            .where(FunnelStats.funnel_id == funnel_id)
            .order_by(FunnelStats.period_end.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_latest_by_funnel(self, funnel_id: str) -> list[FunnelStats]:
        """Return the most recent period's stats for all stages of a funnel."""
        # Find the latest period_end for this funnel
        latest_sq = (
            select(func.max(FunnelStats.period_end).label("max_period_end"))
            .where(FunnelStats.funnel_id == funnel_id)
            .scalar_subquery()
        )
        stmt = (
            self._base_select()
            .where(FunnelStats.funnel_id == funnel_id)
            .where(FunnelStats.period_end == latest_sq)
            .order_by(FunnelStats.event_count.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_all_latest(self) -> list[FunnelStats]:
        """Return the most recent stats across all funnels."""
        latest_sq = (
            select(
                FunnelStats.funnel_id,
                func.max(FunnelStats.period_end).label("max_period_end"),
            )
            .group_by(FunnelStats.funnel_id)
            .subquery()
        )
        stmt = (
            self._base_select()
            .join(
                latest_sq,
                (FunnelStats.funnel_id == latest_sq.c.funnel_id)
                & (FunnelStats.period_end == latest_sq.c.max_period_end),
            )
            .order_by(FunnelStats.funnel_id, FunnelStats.event_count.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_stats(
        self,
        funnel_id: str,
        stage: str,
        period_start: datetime,
        period_end: datetime,
        event_count: int,
        conversion_rate: float | None = None,
    ) -> FunnelStats:
        """Find-or-create a stats row by funnel_id + stage + period_start."""
        stmt = (
            self._base_select()
            .where(FunnelStats.funnel_id == funnel_id)
            .where(FunnelStats.stage == stage)
            .where(FunnelStats.period_start == period_start)
        )
        result = await self.session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance is None:
            return await self.create(
                funnel_id=funnel_id,
                stage=stage,
                period_start=period_start,
                period_end=period_end,
                event_count=event_count,
                conversion_rate=conversion_rate,
            )

        instance.event_count = event_count
        instance.conversion_rate = conversion_rate
        instance.period_end = period_end
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance


class AdsStatsRepository(RepositoryBase[AdsStats]):
    """Repository for AdsStats — aggregated paid advertising metrics."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AdsStats)

    async def aggregate_totals(self) -> dict:
        """Return totals across the latest stats row per platform+campaign.

        Uses a subquery to pick only the most recent period_end per
        (platform, campaign_name) pair, then aggregates across those rows.
        """
        latest_sq = (
            select(
                AdsStats.platform,
                AdsStats.campaign_name,
                func.max(AdsStats.period_end).label("max_period_end"),
            )
            .where(AdsStats.deleted_at.is_(None))
            .group_by(AdsStats.platform, AdsStats.campaign_name)
            .subquery()
        )

        stmt = (
            select(
                func.count(AdsStats.id).label("total_campaigns"),
                func.coalesce(func.avg(AdsStats.roas), 0.0).label("avg_roas"),
                func.coalesce(func.sum(AdsStats.spend), 0.0).label("total_spend"),
            )
            .join(
                latest_sq,
                (AdsStats.platform == latest_sq.c.platform)
                & (AdsStats.campaign_name == latest_sq.c.campaign_name)
                & (AdsStats.period_end == latest_sq.c.max_period_end),
            )
            .where(AdsStats.deleted_at.is_(None))
        )

        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "total_campaigns": int(row.total_campaigns),
            "avg_roas": round(float(row.avg_roas), 2),
            "total_spend": round(float(row.total_spend), 2),
        }

    async def upsert_stats(
        self,
        platform: str,
        campaign_name: str,
        period_start: datetime,
        period_end: datetime,
        **metrics,
    ) -> AdsStats:
        """Find-or-create a stats row by platform+campaign_name+period_start, then update."""
        stmt = (
            self._base_select()
            .where(AdsStats.platform == platform)
            .where(AdsStats.campaign_name == campaign_name)
            .where(AdsStats.period_start == period_start)
        )
        result = await self.session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance is None:
            return await self.create(
                platform=platform,
                campaign_name=campaign_name,
                period_start=period_start,
                period_end=period_end,
                **metrics,
            )

        for key, value in metrics.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        instance.period_end = period_end
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def find_latest_by_platform(self, platform: str) -> Optional[AdsStats]:
        """Return the latest stats row for a given platform."""
        stmt = (
            self._base_select()
            .where(AdsStats.platform == platform)
            .order_by(AdsStats.period_end.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class DmStatsRepository(RepositoryBase[DmStats]):
    """Repository for DmStats — aggregated DM outreach metrics."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DmStats)

    async def aggregate_totals(self) -> dict:
        """Return totals across the latest stats row per platform.

        Uses a subquery to pick only the most recent period_end per platform,
        then aggregates across those rows.
        """
        latest_sq = (
            select(
                DmStats.platform,
                func.max(DmStats.period_end).label("max_period_end"),
            )
            .where(DmStats.deleted_at.is_(None))
            .group_by(DmStats.platform)
            .subquery()
        )

        stmt = (
            select(
                func.coalesce(func.sum(DmStats.outreach_sent), 0).label("total_outreach_sent"),
                func.coalesce(func.avg(DmStats.conversion_rate), 0.0).label("avg_response_rate"),
                func.coalesce(func.sum(DmStats.meetings_booked), 0).label("total_meetings_booked"),
            )
            .join(
                latest_sq,
                (DmStats.platform == latest_sq.c.platform)
                & (DmStats.period_end == latest_sq.c.max_period_end),
            )
            .where(DmStats.deleted_at.is_(None))
        )

        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "total_outreach_sent": int(row.total_outreach_sent),
            "avg_response_rate": round(float(row.avg_response_rate), 2),
            "total_meetings_booked": int(row.total_meetings_booked),
        }

    async def upsert_stats(
        self,
        platform: str,
        period_start: datetime,
        period_end: datetime,
        **metrics,
    ) -> DmStats:
        """Find-or-create a stats row by platform+period_start, then update."""
        stmt = (
            self._base_select()
            .where(DmStats.platform == platform)
            .where(DmStats.period_start == period_start)
        )
        result = await self.session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance is None:
            return await self.create(
                platform=platform,
                period_start=period_start,
                period_end=period_end,
                **metrics,
            )

        for key, value in metrics.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        instance.period_end = period_end
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance


class PromotionRepository(RepositoryBase[Promotion]):
    """Repository for Promotion — promo calendar entries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Promotion)

    async def find_by_date_range(
        self, start: datetime, end: datetime
    ) -> list[Promotion]:
        """Return promotions whose date range overlaps [start, end]."""
        stmt = (
            self._base_select()
            .where(Promotion.start_date <= end)
            .where(Promotion.end_date >= start)
            .order_by(Promotion.start_date.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_active(self) -> list[Promotion]:
        """Return promotions with status 'active' or 'planned'."""
        stmt = (
            self._base_select()
            .where(Promotion.status.in_(["active", "planned"]))
            .order_by(Promotion.start_date.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_upcoming(self, limit: int = 10) -> list[Promotion]:
        """Return promotions starting in the future, ordered by start_date."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        stmt = (
            self._base_select()
            .where(Promotion.start_date > now)
            .order_by(Promotion.start_date.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
