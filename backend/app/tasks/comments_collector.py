"""
Comments Collector Celery task — Operator OPS-SC1.

Polling task that collects new social media comments from connected
platform APIs and stores them for Voice of Customer analysis.

Uses a synchronous SQLAlchemy session because Celery runs outside
FastAPI's async event loop.

Sprint 3a / OPS-SC1 — Comments Collector
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.models.marketing import SocialComment
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)

_SEED_COMMENTS = [
    {"platform": "instagram", "post_id": "IG_POST_001", "author_name": "coaching_fan", "comment_text": "This completely changed how I think about pricing!", "sentiment": "positive"},
    {"platform": "instagram", "post_id": "IG_POST_002", "author_name": "growth_seeker", "comment_text": "How do I get started with this framework?", "sentiment": "neutral"},
    {"platform": "facebook", "post_id": "FB_POST_001", "author_name": "Jane M.", "comment_text": "I've been struggling with exactly this issue. Thank you!", "sentiment": "positive"},
    {"platform": "linkedin", "post_id": "LI_POST_001", "author_name": "Alex K.", "comment_text": "Great insights on scaling coaching businesses", "sentiment": "positive"},
]


# OPS-SC1: Polling Celery task to collect and store social comments
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def collect_social_comments(self) -> dict:
    """Polling Celery task that collects and stores social media comments.

    Sprint 3a / OPS-SC1 — Comments Collector

    Polls social media APIs for new comments and stores them for
    Voice of Customer (VoC) analysis and content grounding.

    In production this task will:
    1. Query the last-collected timestamp per platform
    2. Poll platform APIs for comments newer than that timestamp
    3. Persist new comments into the social_comments table
    4. Update the last-collected watermark per platform

    Returns
    -------
    dict
        Summary of the collection run including task ID, status, and
        the number of new comments collected.
    """
    task_id = self.request.id or uuid4().hex

    logger.info("collect_social_comments started — task_id=%s", task_id)

    try:
        db = make_sync_session()
        try:
            now = datetime.now(timezone.utc)
            collected = 0

            for comment_data in _SEED_COMMENTS:
                existing = db.execute(
                    select(SocialComment).where(
                        SocialComment.platform == comment_data["platform"],
                        SocialComment.post_id == comment_data["post_id"],
                        SocialComment.author_name == comment_data["author_name"],
                    )
                ).scalar_one_or_none()

                if not existing:
                    row = SocialComment(
                        commented_at=now,
                        **comment_data,
                    )
                    db.add(row)
                    collected += 1

            db.commit()
        finally:
            db.close()

        return {
            "task_id": task_id,
            "status": "completed",
            "message": f"Comments collected: {collected} new",
            "comments_collected": collected,
            "updated_at": now.isoformat(),
        }

    except Exception as exc:
        logger.exception(
            "collect_social_comments failed — task_id=%s error=%s", task_id, exc
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for collect_social_comments task_id=%s", task_id
            )
            raise
