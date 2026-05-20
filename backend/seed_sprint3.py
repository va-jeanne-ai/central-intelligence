"""Seed script for Sprint 3 marketing tables.

Populates social_stats, social_comments, email_campaigns, funnel_events,
and funnel_stats with realistic mock data so the API returns real values
and the frontend can display meaningful KPIs.

Usage:
    cd backend
    source .venv/bin/activate
    PYTHONPATH=. python seed_sprint3.py
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.marketing import (
    EmailCampaign,
    FunnelEvent,
    FunnelStats,
    SocialComment,
    SocialStats,
)


def _get_sync_db_url(async_url: str) -> str:
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def make_session() -> Session:
    sync_url = _get_sync_db_url(settings.database_url)
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()


def seed_social_stats(db: Session) -> int:
    """Seed social_stats with 2 months of data for 4 platforms."""
    now = datetime.now(timezone.utc)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    prev_month_end = current_month_start - timedelta(seconds=1)

    platforms = {
        "instagram": [
            {"followers": 11200, "posts_count": 74, "engagement_rate": 2.9, "reach": 38000, "impressions": 110000},
            {"followers": 12450, "posts_count": 87, "engagement_rate": 3.2, "reach": 45000, "impressions": 128000},
        ],
        "facebook": [
            {"followers": 7800, "posts_count": 48, "engagement_rate": 1.5, "reach": 18000, "impressions": 54000},
            {"followers": 8320, "posts_count": 54, "engagement_rate": 1.8, "reach": 22000, "impressions": 67000},
        ],
        "linkedin": [
            {"followers": 4600, "posts_count": 26, "engagement_rate": 3.8, "reach": 14000, "impressions": 35000},
            {"followers": 5100, "posts_count": 32, "engagement_rate": 4.1, "reach": 18000, "impressions": 42000},
        ],
        "tiktok": [
            {"followers": 1800, "posts_count": 15, "engagement_rate": 5.9, "reach": 72000, "impressions": 240000},
            {"followers": 3200, "posts_count": 23, "engagement_rate": 6.5, "reach": 95000, "impressions": 310000},
        ],
    }

    count = 0
    for platform, months in platforms.items():
        for i, (period_start, period_end, metrics) in enumerate([
            (prev_month_start, prev_month_end, months[0]),
            (current_month_start, now, months[1]),
        ]):
            existing = db.execute(
                select(SocialStats).where(
                    SocialStats.platform == platform,
                    SocialStats.period_start == period_start,
                )
            ).scalar_one_or_none()

            if existing:
                for k, v in metrics.items():
                    setattr(existing, k, v)
                existing.period_end = period_end
            else:
                db.add(SocialStats(
                    platform=platform,
                    period_start=period_start,
                    period_end=period_end,
                    **metrics,
                ))
            count += 1

    return count


def seed_social_comments(db: Session) -> int:
    """Seed social_comments with realistic VoC data."""
    comments = [
        {"platform": "instagram", "post_id": "IG_POST_001", "author_name": "coaching_fan_22", "comment_text": "This completely changed how I think about pricing my offers. Thank you!", "sentiment": "positive", "commented_at": datetime(2026, 4, 2, 14, 30, tzinfo=timezone.utc)},
        {"platform": "instagram", "post_id": "IG_POST_001", "author_name": "growth_mentor_jk", "comment_text": "How do I get started with this framework? Is there a course?", "sentiment": "neutral", "commented_at": datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc)},
        {"platform": "instagram", "post_id": "IG_POST_002", "author_name": "mindset_queen", "comment_text": "NEEDED this today. Saving for later.", "sentiment": "positive", "commented_at": datetime(2026, 4, 3, 9, 15, tzinfo=timezone.utc)},
        {"platform": "instagram", "post_id": "IG_POST_003", "author_name": "biz_builder_99", "comment_text": "I tried this exact strategy and went from 2 clients to 8 in a month", "sentiment": "positive", "commented_at": datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc)},
        {"platform": "facebook", "post_id": "FB_POST_001", "author_name": "Jane Morrison", "comment_text": "I've been struggling with exactly this issue for months. The accountability framework is gold.", "sentiment": "positive", "commented_at": datetime(2026, 4, 1, 8, 30, tzinfo=timezone.utc)},
        {"platform": "facebook", "post_id": "FB_POST_002", "author_name": "Tom K.", "comment_text": "What's the difference between this and the free content you already share?", "sentiment": "neutral", "commented_at": datetime(2026, 4, 3, 14, 0, tzinfo=timezone.utc)},
        {"platform": "facebook", "post_id": "FB_POST_003", "author_name": "Sarah C.", "comment_text": "Just enrolled in the program. Can't wait to start!", "sentiment": "positive", "commented_at": datetime(2026, 4, 5, 10, 20, tzinfo=timezone.utc)},
        {"platform": "linkedin", "post_id": "LI_POST_001", "author_name": "Alex Karev", "comment_text": "Great insights on scaling coaching businesses. The data-driven approach is refreshing.", "sentiment": "positive", "commented_at": datetime(2026, 4, 2, 7, 0, tzinfo=timezone.utc)},
        {"platform": "linkedin", "post_id": "LI_POST_002", "author_name": "Maria Chen", "comment_text": "Would love to see a case study on this. How does it work for B2B coaching?", "sentiment": "neutral", "commented_at": datetime(2026, 4, 4, 9, 30, tzinfo=timezone.utc)},
        {"platform": "tiktok", "post_id": "TT_POST_001", "author_name": "coach_life_tips", "comment_text": "this is the best advice ive seen on tiktok hands down", "sentiment": "positive", "commented_at": datetime(2026, 4, 3, 20, 0, tzinfo=timezone.utc)},
        {"platform": "tiktok", "post_id": "TT_POST_001", "author_name": "entrepreneur_daily", "comment_text": "Do you offer 1:1 coaching? DM me!", "sentiment": "positive", "commented_at": datetime(2026, 4, 3, 21, 15, tzinfo=timezone.utc)},
        {"platform": "tiktok", "post_id": "TT_POST_002", "author_name": "skeptic_steve", "comment_text": "Sounds too good to be true honestly", "sentiment": "negative", "commented_at": datetime(2026, 4, 5, 18, 0, tzinfo=timezone.utc)},
    ]

    count = 0
    for c in comments:
        existing = db.execute(
            select(SocialComment).where(
                SocialComment.platform == c["platform"],
                SocialComment.post_id == c["post_id"],
                SocialComment.author_name == c["author_name"],
            )
        ).scalar_one_or_none()

        if not existing:
            db.add(SocialComment(**c))
            count += 1

    return count


def seed_email_campaigns(db: Session) -> int:
    """Seed email_campaigns with realistic campaign data."""
    now = datetime.now(timezone.utc)

    campaigns = [
        {"name": "Weekly Newsletter #40", "subject": "3 Lessons From This Week's Coaching Calls", "campaign_type": "nurture", "status": "sent", "sent_at": now - timedelta(days=21), "recipients_count": 2280, "open_count": 798, "click_count": 160, "unsubscribe_count": 9, "bounce_count": 5, "open_rate": 35.0, "click_rate": 7.0},
        {"name": "Weekly Newsletter #41", "subject": "Why Your Funnel Isn't Converting (And How to Fix It)", "campaign_type": "nurture", "status": "sent", "sent_at": now - timedelta(days=14), "recipients_count": 2350, "open_count": 846, "click_count": 188, "unsubscribe_count": 11, "bounce_count": 6, "open_rate": 36.0, "click_rate": 8.0},
        {"name": "Weekly Newsletter #42", "subject": "This Week in Coaching: The Pricing Mindset Shift", "campaign_type": "nurture", "status": "sent", "sent_at": now - timedelta(days=7), "recipients_count": 2450, "open_count": 882, "click_count": 196, "unsubscribe_count": 12, "bounce_count": 8, "open_rate": 36.0, "click_rate": 8.0},
        {"name": "New Program Launch", "subject": "Introducing: Scale Your Practice in 90 Days", "campaign_type": "broadcast", "status": "sent", "sent_at": now - timedelta(days=10), "recipients_count": 3100, "open_count": 1178, "click_count": 341, "unsubscribe_count": 25, "bounce_count": 15, "open_rate": 38.0, "click_rate": 11.0},
        {"name": "Re-engagement Sequence #1", "subject": "We miss you! Here's what's new in the community", "campaign_type": "sequence", "status": "sent", "sent_at": now - timedelta(days=5), "recipients_count": 890, "open_count": 178, "click_count": 45, "unsubscribe_count": 8, "bounce_count": 3, "open_rate": 20.0, "click_rate": 5.1},
        {"name": "Black Friday Early Access", "subject": "You're on the VIP list — early access inside", "campaign_type": "broadcast", "status": "sent", "sent_at": now - timedelta(days=18), "recipients_count": 3400, "open_count": 1530, "click_count": 476, "unsubscribe_count": 18, "bounce_count": 10, "open_rate": 45.0, "click_rate": 14.0},
        {"name": "Welcome Sequence — Day 1", "subject": "Welcome to the hive! Here's your first step", "campaign_type": "sequence", "status": "sent", "sent_at": now - timedelta(days=3), "recipients_count": 180, "open_count": 126, "click_count": 63, "unsubscribe_count": 1, "bounce_count": 0, "open_rate": 70.0, "click_rate": 35.0},
        {"name": "April Webinar Invite", "subject": "Free live training: Build Your $10K/mo Coaching Biz", "campaign_type": "broadcast", "status": "draft", "sent_at": None, "recipients_count": 0, "open_count": 0, "click_count": 0, "unsubscribe_count": 0, "bounce_count": 0, "open_rate": None, "click_rate": None},
    ]

    count = 0
    for c in campaigns:
        existing = db.execute(
            select(EmailCampaign).where(EmailCampaign.name == c["name"])
        ).scalar_one_or_none()

        if existing:
            for k, v in c.items():
                if k != "name" and hasattr(existing, k):
                    setattr(existing, k, v)
        else:
            db.add(EmailCampaign(**c))
        count += 1

    return count


def seed_funnel_events(db: Session) -> int:
    """Seed funnel_events with realistic conversion funnel data."""
    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=30)

    # Simulate a coaching program funnel with realistic drop-off
    stages_with_counts = [
        ("awareness", 450),
        ("interest", 280),
        ("consideration", 145),
        ("intent", 72),
        ("purchase", 31),
    ]

    # Also a webinar funnel
    webinar_stages = [
        ("registered", 320),
        ("attended", 180),
        ("stayed_to_end", 95),
        ("clicked_offer", 48),
        ("purchased", 18),
    ]

    count = 0
    for funnel_id, stages in [("coaching-program-v2", stages_with_counts), ("webinar-apr-2026", webinar_stages)]:
        for stage, num_events in stages:
            for i in range(num_events):
                # Spread events across the last 30 days
                event_time = base_time + timedelta(
                    days=i % 30,
                    hours=(i * 3) % 24,
                    minutes=(i * 7) % 60,
                )
                db.add(FunnelEvent(
                    funnel_id=funnel_id,
                    event_type=stage,
                    stage=stage,
                    metadata_json=f'{{"source": "seed", "index": {i}}}',
                    received_at=event_time,
                ))
                count += 1

    return count


def seed_funnel_stats(db: Session) -> int:
    """Seed funnel_stats with pre-aggregated data matching the events."""
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = now

    funnels = {
        "coaching-program-v2": [
            ("awareness", 450, None),
            ("interest", 280, 62.2),
            ("consideration", 145, 51.8),
            ("intent", 72, 49.7),
            ("purchase", 31, 43.1),
        ],
        "webinar-apr-2026": [
            ("registered", 320, None),
            ("attended", 180, 56.3),
            ("stayed_to_end", 95, 52.8),
            ("clicked_offer", 48, 50.5),
            ("purchased", 18, 37.5),
        ],
    }

    count = 0
    for funnel_id, stages in funnels.items():
        for stage, event_count, conversion_rate in stages:
            existing = db.execute(
                select(FunnelStats).where(
                    FunnelStats.funnel_id == funnel_id,
                    FunnelStats.stage == stage,
                    FunnelStats.period_start == period_start,
                )
            ).scalar_one_or_none()

            if existing:
                existing.event_count = event_count
                existing.conversion_rate = conversion_rate
                existing.period_end = period_end
            else:
                db.add(FunnelStats(
                    funnel_id=funnel_id,
                    stage=stage,
                    event_count=event_count,
                    conversion_rate=conversion_rate,
                    period_start=period_start,
                    period_end=period_end,
                ))
            count += 1

    return count


def main():
    print("Connecting to database...")
    db = make_session()

    try:
        print("\n--- Seeding social_stats ---")
        n = seed_social_stats(db)
        print(f"  Upserted {n} social stats rows (4 platforms x 2 months)")

        print("\n--- Seeding social_comments ---")
        n = seed_social_comments(db)
        print(f"  Inserted {n} new social comments")

        print("\n--- Seeding email_campaigns ---")
        n = seed_email_campaigns(db)
        print(f"  Upserted {n} email campaigns")

        print("\n--- Seeding funnel_events ---")
        n = seed_funnel_events(db)
        print(f"  Inserted {n} funnel events (2 funnels)")

        print("\n--- Seeding funnel_stats ---")
        n = seed_funnel_stats(db)
        print(f"  Upserted {n} funnel stats rows")

        db.commit()
        print("\n All seed data committed successfully!")

    except Exception as e:
        db.rollback()
        print(f"\n ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
