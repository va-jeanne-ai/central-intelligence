"""Mirror WGR comment-lead attribution (deliverable 1 — social page rebuild).

Greg's own tracking page (`central-intelligence-greg/index.html`,
`view-mkt-social`) renders the Instagram tab from the live Graph API (not
a DB table — no mirror needed for posts/profile/insights; ``instagram_posts``
already covers our own richer post mirror). Its "Leads by Day" table and
per-keyword lead stat cards are backed by two Express routes
(`/api/social/comment-leads`, `/api/social/comment-leads-by-day`) reading
WGR's `comment_event_counts_by_post_keyword` view and `comment_leads_by_day()`
RPC — both built on real, non-trivial data:

  * ``comment_events`` (15,855 rows) — one row per IG/FB comment that matched
    a configured keyword, with ``occurred_at`` for day-bucketing. Mirrored
    here as ``wgr_comment_events`` so the day-bucketed leads table can be
    rebuilt in CI without depending on the client's Express/Supabase RPC.
  * ``post_comment_leads`` (2,754 rows) — precomputed per-post/keyword
    rollup (``keyword_counts`` jsonb + ``total_leads``), keyed by
    ``ig_media_id``. Mirrored here as ``wgr_post_comment_leads`` — feeds the
    per-post lead counts joined against ``instagram_posts``.

Both are snapshot-reconciled (same precedent as `wgr_offers` / `lead_journey`
/ `meta_campaigns`) — small-to-medium upstream tables with no watermark
column, natural upstream PKs (`comment_events.id` uuid — verified unique/
non-null; `post_comment_leads.ig_media_id` — verified unique/non-null,
probe 2026-08-04), full re-read each sync.

Reads: GET /social/overview (routes/social.py)
Writes: app/services/wgr_sync/upsert.py sync_all() (snapshot reconcile)

Revision ID: c2df94038d03
Revises: e79cc79ec06b
Create Date: 2026-08-04 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2df94038d03"
down_revision: Union[str, None] = "e79cc79ec06b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wgr_comment_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("ghl_contact_id", sa.Text(), nullable=True),
        sa.Column("ghl_conversation_id", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("keyword", sa.String(128), nullable=True),
        sa.Column("post_id", sa.Text(), nullable=True),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("comment_text", sa.Text(), nullable=True),
        sa.Column("fb_page_id", sa.Text(), nullable=True),
        sa.Column("fb_page_name", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_wgr_comment_events_occurred_at", "wgr_comment_events", ["occurred_at"]
    )
    op.create_index(
        "ix_wgr_comment_events_post_id", "wgr_comment_events", ["post_id"]
    )
    op.create_index(
        "ix_wgr_comment_events_platform", "wgr_comment_events", ["platform"]
    )

    op.create_table(
        "wgr_post_comment_leads",
        sa.Column("ig_media_id", sa.String(64), primary_key=True),
        sa.Column("shortcode", sa.String(64), nullable=True),
        sa.Column("permalink", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("media_type", sa.String(32), nullable=True),
        sa.Column("is_reel", sa.Boolean(), nullable=True),
        sa.Column("keyword_counts", sa.JSON(), nullable=True),
        sa.Column("total_leads", sa.Integer(), nullable=True),
        sa.Column("first_lead_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_lead_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_wgr_post_comment_leads_shortcode", "wgr_post_comment_leads", ["shortcode"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wgr_post_comment_leads_shortcode", table_name="wgr_post_comment_leads"
    )
    op.drop_table("wgr_post_comment_leads")
    op.drop_index("ix_wgr_comment_events_platform", table_name="wgr_comment_events")
    op.drop_index("ix_wgr_comment_events_post_id", table_name="wgr_comment_events")
    op.drop_index("ix_wgr_comment_events_occurred_at", table_name="wgr_comment_events")
    op.drop_table("wgr_comment_events")
