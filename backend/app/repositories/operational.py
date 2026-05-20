"""Concrete repositories for all operational domain models."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational import (
    Call,
    ContentIdea,
    Goal,
    ICP,
    Insight,
    Lead,
    Member,
    Objection,
    PainPoint,
    Win,
)
from app.repositories.base import RepositoryBase


class LeadRepository(RepositoryBase[Lead]):
    """Repository for the Lead model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Lead)

    async def find_by_email(self, email: str) -> Optional[Lead]:
        """Look up a lead by their unique email address."""
        stmt = self._base_select().where(Lead.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_status(self, status: str, limit: int = 100, offset: int = 0) -> list[Lead]:
        """Return all leads in a given status, e.g. 'New', 'Contacted', 'Qualified'."""
        stmt = self._base_select().where(Lead.status == status).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_source(self, source: str, limit: int = 100, offset: int = 0) -> list[Lead]:
        """Return leads acquired from a particular source channel."""
        stmt = self._base_select().where(Lead.source == source).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_created_by(self, user_id: UUID) -> list[Lead]:
        """Return all leads created by a specific user."""
        stmt = self._base_select().where(Lead.created_by == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class MemberRepository(RepositoryBase[Member]):
    """Repository for the Member model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Member)

    async def find_by_email(self, email: str) -> Optional[Member]:
        """Look up a member by their unique email address."""
        stmt = self._base_select().where(Member.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_coach(self, coach_id: UUID) -> list[Member]:
        """Return all active members assigned to a specific coach."""
        stmt = self._base_select().where(Member.coach_id == coach_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> list[Member]:
        """Return members filtered by enrollment status."""
        stmt = self._base_select().where(Member.status == status).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_enrolled_after(self, since: datetime) -> list[Member]:
        """Return members who enrolled after the given date."""
        stmt = self._base_select().where(Member.enrollment_date >= since)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CallRepository(RepositoryBase[Call]):
    """Repository for the Call model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Call)

    async def find_by_type(
        self, call_type: str, limit: int = 100, offset: int = 0
    ) -> list[Call]:
        """Return calls filtered by call_type, e.g. 'Strategy', 'Sales', 'Onboarding'."""
        stmt = self._base_select().where(Call.call_type == call_type).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_member(self, member_id: UUID, limit: int = 100) -> list[Call]:
        """Return all calls associated with a member, most recent first."""
        stmt = (
            self._base_select()
            .where(Call.member_id == member_id)
            .order_by(Call.date.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_lead(self, lead_id: UUID, limit: int = 100) -> list[Call]:
        """Return all calls associated with a lead, most recent first."""
        stmt = (
            self._base_select()
            .where(Call.lead_id == lead_id)
            .order_by(Call.date.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_unprocessed(self) -> list[Call]:
        """Return calls that have a transcript_uid but no processed_date."""
        stmt = self._base_select().where(
            Call.transcript_uid.is_not(None),
            Call.processed_date.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_in_date_range(self, start: datetime, end: datetime) -> list[Call]:
        """Return calls that occurred within the given date window."""
        stmt = self._base_select().where(Call.date >= start, Call.date <= end)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_transcript_source(self, source: str) -> list[Call]:
        """Return calls ingested from a specific transcript source.

        Parameters
        ----------
        source:
            e.g. ``"transcriber_operator"``, ``"whisper"``, ``"manual"``
        """
        stmt = self._base_select().where(Call.transcript_source == source)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_url_hash(self, url_hash: str) -> Optional[Call]:
        """Find a call by its video URL SHA-256 hash for deduplication.

        Parameters
        ----------
        url_hash:
            64-character hex digest of the video URL.

        Returns
        -------
        Call | None
            The matching Call record, or ``None`` if no record exists.
        """
        stmt = select(Call).where(Call.video_url_hash == url_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class InsightRepository(RepositoryBase[Insight]):
    """Repository for the Insight model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Insight)

    async def find_by_call(self, call_id: str) -> list[Insight]:
        """Return all insights extracted from a specific call."""
        stmt = self._base_select().where(Insight.call_id == call_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_insight_type(
        self, insight_type: str, limit: int = 100, offset: int = 0
    ) -> list[Insight]:
        """Return insights of a given type, e.g. 'Pain', 'Goal', 'Objection'."""
        stmt = (
            self._base_select()
            .where(Insight.insight_type == insight_type)
            .order_by(Insight.frequency_score.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_signal_family(
        self, signal_family: str, limit: int = 100, offset: int = 0
    ) -> list[Insight]:
        """Return insights belonging to the given signal family."""
        stmt = (
            self._base_select()
            .where(Insight.signal_family == signal_family)
            .order_by(Insight.frequency_score.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_high_frequency(self, min_score: int = 3, limit: int = 50) -> list[Insight]:
        """Return insights whose frequency_score meets or exceeds the threshold."""
        stmt = (
            self._base_select()
            .where(Insight.frequency_score >= min_score)
            .order_by(Insight.frequency_score.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_speaker(self, speaker_name: str) -> list[Insight]:
        """Return all insights attributed to a particular speaker."""
        stmt = self._base_select().where(Insight.speaker_name == speaker_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ContentIdeaRepository(RepositoryBase[ContentIdea]):
    """Repository for the ContentIdea model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ContentIdea)

    async def find_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> list[ContentIdea]:
        """Return content ideas filtered by status, e.g. 'Idea', 'Draft', 'Published'."""
        stmt = (
            self._base_select()
            .where(ContentIdea.status == status)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_platform(self, platform: str) -> list[ContentIdea]:
        """Return ideas best suited for a specific platform."""
        stmt = self._base_select().where(ContentIdea.best_platform == platform)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_top_scored(self, limit: int = 20) -> list[ContentIdea]:
        """Return the highest-scoring content ideas."""
        stmt = (
            self._base_select()
            .where(ContentIdea.idea_score.is_not(None))
            .order_by(ContentIdea.idea_score.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_insight(self, insight_id: str) -> list[ContentIdea]:
        """Return all content ideas derived from a given insight."""
        stmt = self._base_select().where(ContentIdea.insight_id == insight_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_format(self, content_format: str) -> list[ContentIdea]:
        """Return content ideas for a specific format, e.g. 'Email', 'Reel', 'Post'."""
        stmt = self._base_select().where(ContentIdea.content_format == content_format)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class GoalRepository(RepositoryBase[Goal]):
    """Repository for the Goal model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Goal)

    async def find_by_member(self, member_id: UUID) -> list[Goal]:
        """Return all active goals for a member."""
        stmt = self._base_select().where(Goal.member_id == member_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_lead(self, lead_id: UUID) -> list[Goal]:
        """Return all active goals associated with a lead."""
        stmt = self._base_select().where(Goal.lead_id == lead_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_status(self, status: str) -> list[Goal]:
        """Return goals by status, e.g. 'active', 'completed', 'abandoned'."""
        stmt = self._base_select().where(Goal.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_overdue(self, as_of: datetime) -> list[Goal]:
        """Return active goals whose target_date has passed."""
        stmt = self._base_select().where(
            Goal.status == "active",
            Goal.target_date < as_of,
            Goal.target_date.is_not(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class PainPointRepository(RepositoryBase[PainPoint]):
    """Repository for the PainPoint model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PainPoint)

    async def find_by_member(self, member_id: UUID) -> list[PainPoint]:
        """Return all pain points linked to a member."""
        stmt = self._base_select().where(PainPoint.member_id == member_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_lead(self, lead_id: UUID) -> list[PainPoint]:
        """Return all pain points linked to a lead."""
        stmt = self._base_select().where(PainPoint.lead_id == lead_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_category(self, category: str) -> list[PainPoint]:
        """Return pain points grouped under a specific category."""
        stmt = (
            self._base_select()
            .where(PainPoint.category == category)
            .order_by(PainPoint.frequency_count.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_most_frequent(self, limit: int = 20) -> list[PainPoint]:
        """Return the most frequently mentioned pain points across all subjects."""
        stmt = (
            self._base_select()
            .order_by(PainPoint.frequency_count.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def increment_frequency(self, pain_point_id: UUID) -> Optional[PainPoint]:
        """Atomically increment the frequency_count for a pain point."""
        instance = await self.get(pain_point_id)
        if instance is None:
            return None
        instance.frequency_count = (instance.frequency_count or 0) + 1
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance


class WinRepository(RepositoryBase[Win]):
    """Repository for the Win model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Win)

    async def find_by_member(self, member_id: UUID) -> list[Win]:
        """Return all wins recorded for a member, most recent first."""
        stmt = (
            self._base_select()
            .where(Win.member_id == member_id)
            .order_by(Win.win_date.desc().nullslast())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_impact_area(self, impact_area: str) -> list[Win]:
        """Return wins grouped by impact area, e.g. 'Revenue', 'Mindset', 'Health'."""
        stmt = (
            self._base_select()
            .where(Win.impact_area == impact_area)
            .order_by(Win.win_date.desc().nullslast())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_in_date_range(self, start: datetime, end: datetime) -> list[Win]:
        """Return wins that occurred within the given date range."""
        stmt = self._base_select().where(Win.win_date >= start, Win.win_date <= end)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ObjectionRepository(RepositoryBase[Objection]):
    """Repository for the Objection model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Objection)

    async def find_by_lead(self, lead_id: UUID) -> list[Objection]:
        """Return all objections raised by a specific lead."""
        stmt = self._base_select().where(Objection.lead_id == lead_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_unresolved(self) -> list[Objection]:
        """Return objections for which no resolution was offered."""
        stmt = self._base_select().where(Objection.resolution_offered.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_text(self, keyword: str, limit: int = 50) -> list[Objection]:
        """Full-text ILIKE search across objection_text.

        Not a replacement for a proper FTS index, but useful for low-volume searches.
        """
        stmt = (
            self._base_select()
            .where(Objection.objection_text.ilike(f"%{keyword}%"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ICPRepository(RepositoryBase[ICP]):
    """Repository for Ideal Customer Profile segments.

    Enforces the invariant that only one segment can have ``is_primary=True``
    at a time.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ICP)

    # ------------------------------------------------------------------
    # Core writes
    # ------------------------------------------------------------------

    async def create_or_update_segment(
        self,
        segment: str,
        description: str | None = None,
        demographics: str | None = None,
        psychographics: str | None = None,
        pain_summary: str | None = None,
        goal_summary: str | None = None,
        buying_triggers: str | None = None,
        common_objections: str | None = None,
        is_primary: bool = False,
        status: str = "active",
    ) -> ICP:
        """Upsert an ICP segment by name.

        If a segment with the same ``segment`` name already exists (and is not
        soft-deleted), its fields are updated in-place.  Otherwise a new row
        is created.

        When ``is_primary=True``, all other active segments are demoted to
        ``is_primary=False`` before setting the new primary, enforcing the
        single-primary invariant.

        Returns
        -------
        ICP
            The created or updated instance (refreshed from DB).
        """
        stmt = self._base_select().where(ICP.segment == segment)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if is_primary:
            await self._demote_all_primaries(exclude_segment=segment)

        if row is None:
            row = ICP(
                segment=segment,
                description=description,
                demographics=demographics,
                psychographics=psychographics,
                pain_summary=pain_summary,
                goal_summary=goal_summary,
                buying_triggers=buying_triggers,
                common_objections=common_objections,
                is_primary=is_primary,
                status=status,
            )
            self.session.add(row)
        else:
            if description is not None:
                row.description = description
            if demographics is not None:
                row.demographics = demographics
            if psychographics is not None:
                row.psychographics = psychographics
            if pain_summary is not None:
                row.pain_summary = pain_summary
            if goal_summary is not None:
                row.goal_summary = goal_summary
            if buying_triggers is not None:
                row.buying_triggers = buying_triggers
            if common_objections is not None:
                row.common_objections = common_objections
            row.is_primary = is_primary
            row.status = status

        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def _demote_all_primaries(self, exclude_segment: str | None = None) -> None:
        """Set ``is_primary=False`` on all active primary ICP rows.

        Parameters
        ----------
        exclude_segment:
            Segment name to exclude from the demotion (the one that is about
            to become primary), to avoid a redundant UPDATE on that row.
        """
        stmt = (
            update(ICP)
            .where(ICP.deleted_at.is_(None))
            .where(ICP.is_primary.is_(True))
            .values(is_primary=False)
        )
        if exclude_segment:
            stmt = stmt.where(ICP.segment != exclude_segment)
        await self.session.execute(stmt)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_primary(self) -> ICP | None:
        """Return the single active primary ICP segment, or None."""
        stmt = self._base_select().where(ICP.is_primary.is_(True)).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, status: str | None = None) -> list[ICP]:
        """Return all active ICP segments, primary first.

        Parameters
        ----------
        status:
            Optional filter on the ``status`` column (e.g. ``"active"``).
        """
        stmt = self._base_select().order_by(ICP.is_primary.desc(), ICP.created_at.asc())
        if status is not None:
            stmt = stmt.where(ICP.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_status(self, status: str) -> list[ICP]:
        """Return ICP segments filtered by status."""
        stmt = self._base_select().where(ICP.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Soft-delete helpers
    # ------------------------------------------------------------------

    async def soft_delete_old_segments(self, keep_segment_names: list[str]) -> int:
        """Soft-delete all active segments whose names are NOT in ``keep_segment_names``.

        Used after a fresh ICP generation run to retire stale segments while
        keeping the newly generated ones.

        Parameters
        ----------
        keep_segment_names:
            Segment names produced by the latest Claude output.

        Returns
        -------
        int
            Number of segments that were soft-deleted.
        """
        stmt = self._base_select().where(ICP.segment.notin_(keep_segment_names))
        result = await self.session.execute(stmt)
        stale = list(result.scalars().all())

        now = datetime.now(tz=timezone.utc)
        for row in stale:
            row.deleted_at = now  # type: ignore[attr-defined]

        await self.session.flush()
        return len(stale)


class SharedIntelligenceQueryRepository:
    """Read-only aggregator for the shared intelligence pool.

    Queries pain_points, wins, objections, goals, and insights tables to
    build the prompt payload for the ICP Generator Celery task.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def aggregate_for_icp(self, date_range_days: int = 90) -> dict[str, Any]:
        """Return a prompt-ready dict with aggregated intelligence pool data.

        Returns
        -------
        dict
            Keys: ``pain_points``, ``wins``, ``objections``, ``goals``,
            ``insights``, ``total_leads``, ``total_members``,
            ``total_calls_analyzed``, ``date_range_days``.
        """
        # Pain points — aggregate by text, sum frequencies
        pain_stmt = (
            select(
                PainPoint.text,
                PainPoint.category,
                func.sum(PainPoint.frequency_count).label("frequency_count"),
            )
            .where(PainPoint.deleted_at.is_(None))
            .group_by(PainPoint.text, PainPoint.category)
            .order_by(func.sum(PainPoint.frequency_count).desc())
            .limit(50)
        )
        pain_result = await self.session.execute(pain_stmt)
        pain_points = [
            {"text": r.text, "category": r.category, "frequency_count": r.frequency_count}
            for r in pain_result.all()
        ]

        # Wins — most recent 30
        win_stmt = (
            select(Win)
            .where(Win.deleted_at.is_(None))
            .order_by(Win.created_at.desc())
            .limit(30)
        )
        win_result = await self.session.execute(win_stmt)
        wins = [
            {
                "win_text": w.win_text,
                "impact_area": w.impact_area,
                "win_date": w.win_date.isoformat() if w.win_date else None,
            }
            for w in win_result.scalars().all()
        ]

        # Objections — most recent 30
        obj_stmt = (
            select(Objection)
            .where(Objection.deleted_at.is_(None))
            .order_by(Objection.created_at.desc())
            .limit(30)
        )
        obj_result = await self.session.execute(obj_stmt)
        objections = [
            {
                "objection_text": o.objection_text,
                "context": o.context,
                "resolution_offered": o.resolution_offered,
            }
            for o in obj_result.scalars().all()
        ]

        # Goals — active ones, most recent 50
        goal_stmt = (
            select(Goal)
            .where(Goal.deleted_at.is_(None))
            .where(Goal.status == "active")
            .order_by(Goal.created_at.desc())
            .limit(50)
        )
        goal_result = await self.session.execute(goal_stmt)
        goals = [
            {"goal_text": g.goal_text, "status": g.status}
            for g in goal_result.scalars().all()
        ]

        # Insights — top by frequency_score
        ins_stmt = (
            select(Insight)
            .order_by(Insight.frequency_score.desc())
            .limit(50)
        )
        ins_result = await self.session.execute(ins_stmt)
        insights = [
            {
                "insight_type": i.insight_type,
                "signal_family": i.signal_family,
                "signal": i.signal,
                "frequency_score": i.frequency_score,
                "what_they_say": i.what_they_say,
                "the_real_problem": i.the_real_problem,
                "emotional_driver": i.emotional_driver,
                "core_fear_revealed": i.core_fear_revealed,
                "false_belief_revealed": i.false_belief_revealed,
                "buying_trigger": i.buying_trigger,
                "marketing_translation": i.marketing_translation,
            }
            for i in ins_result.scalars().all()
        ]

        # Counts
        lead_count = (await self.session.execute(
            select(func.count()).select_from(Lead).where(Lead.deleted_at.is_(None))
        )).scalar_one()

        member_count = (await self.session.execute(
            select(func.count()).select_from(Member).where(Member.deleted_at.is_(None))
        )).scalar_one()

        call_count = (await self.session.execute(
            select(func.count()).select_from(Call)
        )).scalar_one()

        return {
            "pain_points": pain_points,
            "wins": wins,
            "objections": objections,
            "goals": goals,
            "insights": insights,
            "total_leads": lead_count,
            "total_members": member_count,
            "total_calls_analyzed": call_count,
            "date_range_days": date_range_days,
        }
