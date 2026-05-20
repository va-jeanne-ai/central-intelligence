"""
Offer Generator Celery task — Operator OPS-O1.

Scheduled/triggered task that auto-generates offer drafts using seed data
derived from ICP + pain_points. Persists structured offer records via
OfferRepository for human review before activation.

Sprint 4b / OPS-O1 — Offer Generator operator
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.models.intelligence import Offer
from app.models.operational import ICP, PainPoint
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)

# Seed offer templates keyed by offer_type.
# In production, Claude SDK will synthesise these from live ICP + pain point data.
_SEED_OFFERS: dict[str, list[dict]] = {
    "Coaching": [
        {
            "name": "90-Day Business Clarity Intensive",
            "description": (
                "A structured 90-day 1:1 coaching programme designed to help "
                "founders move from scattered execution to focused growth. "
                "Weekly sessions, async support, and a clear 30-60-90 day roadmap."
            ),
            "price": 3500.0,
            "notes": "Auto-generated from ICP + pain point data. Requires human review.",
        },
        {
            "name": "Monthly Revenue Accelerator",
            "description": (
                "Monthly retainer coaching for service-based business owners "
                "looking to scale past their first $10K month. Includes bi-weekly "
                "calls, content review, and offer positioning support."
            ),
            "price": 1200.0,
            "notes": "Auto-generated from ICP + pain point data. Requires human review.",
        },
        {
            "name": "VIP Strategy Day",
            "description": (
                "Full-day intensive strategy session to audit your current offers, "
                "identify bottlenecks, and build a 60-day action plan. "
                "Delivered live via Zoom with follow-up notes."
            ),
            "price": 1800.0,
            "notes": "Auto-generated from ICP + pain point data. Requires human review.",
        },
    ],
    "Course": [
        {
            "name": "Offer Architecture Blueprint",
            "description": (
                "Self-paced course covering how to craft, price, and position "
                "your core offer for a premium audience. Includes workbooks, "
                "templates, and a private community."
            ),
            "price": 497.0,
            "notes": "Auto-generated from ICP + pain point data. Requires human review.",
        },
        {
            "name": "DM Mastery for Coaches",
            "description": (
                "A 4-week live cohort programme teaching repeatable DM outreach "
                "systems that book qualified discovery calls without paid ads."
            ),
            "price": 997.0,
            "notes": "Auto-generated from ICP + pain point data. Requires human review.",
        },
        {
            "name": "Content Engine Workshop",
            "description": (
                "3-hour live workshop showing how to build a 30-day content "
                "calendar from a single client call, repurposed across all platforms."
            ),
            "price": 197.0,
            "notes": "Auto-generated from ICP + pain point data. Requires human review.",
        },
    ],
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def generate_offers(self, offer_type: str = "Coaching", max_offers: int = 3) -> dict:
    """Celery task that auto-generates offer drafts using seed data.

    Sprint 4b / OPS-O1 — Offer Generator operator.

    Loads ICP segments and top pain points from the database to build
    context, then persists up to max_offers seed offer drafts for the
    given offer_type into the offers table via direct ORM writes.
    All generated offers land in 'Draft' status for human review.

    Returns
    -------
    dict
        Summary including task_id, status, offer_type, offers_generated count, and updated_at.
    """
    task_id = self.request.id or uuid4().hex

    logger.info(
        "generate_offers started — task_id=%s offer_type=%s max_offers=%s",
        task_id,
        offer_type,
        max_offers,
    )

    try:
        db = make_sync_session()
        try:
            now = datetime.now(timezone.utc)

            # Load ICP context (informational — used for logging / future Claude prompt)
            icp_rows = db.execute(
                select(ICP).where(ICP.deleted_at.is_(None)).limit(5)
            ).scalars().all()

            # Load top pain points for context
            pain_rows = db.execute(
                select(PainPoint).where(PainPoint.deleted_at.is_(None)).limit(10)
            ).scalars().all()

            logger.info(
                "generate_offers context — icp_count=%s pain_points=%s",
                len(icp_rows),
                len(pain_rows),
            )

            templates = _SEED_OFFERS.get(offer_type, _SEED_OFFERS["Coaching"])
            templates = templates[:max_offers]
            generated = 0

            for template in templates:
                offer_id = f"gen-{offer_type.lower()}-{uuid4().hex[:8]}"

                # Skip if an offer with the same name+type already exists (idempotency)
                existing = db.execute(
                    select(Offer).where(
                        Offer.name == template["name"],
                        Offer.offer_type == offer_type,
                        Offer.status == "Draft",
                    )
                ).scalar_one_or_none()

                if existing:
                    logger.debug(
                        "generate_offers — skipping duplicate offer name='%s'",
                        template["name"],
                    )
                    continue

                offer = Offer(
                    offer_id=offer_id,
                    name=template["name"],
                    offer_type=offer_type,
                    description=template["description"],
                    price=template.get("price"),
                    status="Draft",
                    notes=template.get("notes"),
                )
                db.add(offer)
                generated += 1

            db.commit()
        finally:
            db.close()

        logger.info(
            "generate_offers completed — task_id=%s offers_generated=%s",
            task_id,
            generated,
        )

        return {
            "task_id": task_id,
            "status": "completed",
            "message": f"Generated {generated} offer draft(s) for type '{offer_type}'",
            "offer_type": offer_type,
            "offers_generated": generated,
            "updated_at": now.isoformat(),
        }

    except Exception as exc:
        logger.exception(
            "generate_offers failed — task_id=%s error=%s", task_id, exc
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for generate_offers task_id=%s", task_id
            )
            raise
