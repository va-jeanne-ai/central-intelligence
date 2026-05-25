"""add google_drive_files + embeddings infrastructure (pgvector)

Lands the storage layer for the RAG ingest pipeline:

  * ``CREATE EXTENSION IF NOT EXISTS vector`` — pgvector on Supabase.
  * ``google_drive_files`` — per-user Drive file index with cached
    extracted text + content_hash for change detection.
  * ``embed_pending`` — generic Celery queue table; the embed worker
    drains rows from it regardless of source. ``(source_table, source_id)``
    is the polymorphic key.
  * ``embeddings`` — pgvector 1024-d embeddings keyed by the same
    polymorphic pair plus a ``chunk_index``. IVFFLAT index on the
    embedding column powers the ``ORDER BY embedding <=> :q`` query
    used by ``search_knowledge_base``.
  * ``embedding_budget`` — single-row table holding a global
    daily-token cap. The embed worker pauses when ``tokens_used_today``
    crosses ``daily_token_cap``; resets on a 24h window.

Drive ingest lands first; email/lead_note/insight backfill pipelines
share this infra without further schema changes.

Revision ID: k2b3c4d5e6f7
Revises: j1a2b3c4d5e6
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "k2b3c4d5e6f7"
down_revision: Union[str, None] = "j1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # pgvector extension — must come before any vector(...) column.
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------
    # google_drive_files — per-user file index.
    # ------------------------------------------------------------------
    op.create_table(
        "google_drive_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connected_via_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_file_id", sa.String(128), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("owner_email", sa.String(255), nullable=True),
        sa.Column("modified_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("web_view_link", sa.Text(), nullable=True),
        sa.Column("parent_folder_id", sa.String(128), nullable=True),
        sa.Column("parent_folder_name", sa.Text(), nullable=True),
        # Lowercase email array; GIN index for JSONB containment lookups.
        sa.Column("shared_with", postgresql.JSONB, nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "is_trashed",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        # Cached plain-text extraction — Drive bytes get parsed once
        # at sync time. Empty for unsupported mime types.
        sa.Column("extracted_text", sa.Text(), nullable=True),
        # sha256(extracted_text or name)[:64]. Diffed against the
        # most-recent embeddings row to decide whether to re-embed.
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("last_extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider_file_id", "connected_via_user_id",
            name="uq_google_drive_files_provider_user",
        ),
    )
    op.create_index(
        "ix_google_drive_files_user_modified",
        "google_drive_files",
        ["connected_via_user_id", sa.text("modified_time DESC")],
        unique=False,
    )
    # GIN on shared_with JSONB — for "find files where lead.email is in
    # shared_with" containment queries on the lead documents card.
    op.execute(
        "CREATE INDEX ix_google_drive_files_shared_with "
        "ON google_drive_files USING GIN (shared_with)"
    )

    # ------------------------------------------------------------------
    # embed_pending — generic Celery queue. Drained by tasks/embed_worker.
    # ------------------------------------------------------------------
    op.create_table(
        "embed_pending",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_table", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("text_to_embed", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_embed_pending_created_at",
        "embed_pending",
        ["created_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # embeddings — pgvector storage. (source_table, source_id, chunk_index)
    # is the UNIQUE that lets the worker INSERT ... ON CONFLICT DO UPDATE.
    # ------------------------------------------------------------------
    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_table", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("text_chunk", sa.Text(), nullable=False),
        # vector(1024) — Voyage voyage-3 output dimension. Declared via
        # raw SQL since Alembic doesn't know the pgvector type natively.
        sa.Column(
            "embedding",
            sa.dialects.postgresql.ARRAY(sa.Float),  # placeholder; replaced below
            nullable=True,
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "embedded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "source_table", "source_id", "chunk_index",
            name="uq_embeddings_source_chunk",
        ),
    )
    # Swap the placeholder column for the real pgvector column. Doing it
    # this way avoids needing a custom SQLAlchemy type at migration time.
    op.execute("ALTER TABLE embeddings DROP COLUMN embedding")
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding vector(1024)")
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding SET NOT NULL")

    # IVFFLAT cosine index — lists=100 covers ~10k-1M rows comfortably.
    # Recalibrate (rebuild with sqrt(rows)) when the corpus crosses ~1M.
    op.execute(
        "CREATE INDEX ix_embeddings_cosine ON embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    # Composite lookup on (source_table, source_id) — used by the
    # backfill tasks to "find rows that haven't been embedded yet".
    op.create_index(
        "ix_embeddings_source",
        "embeddings",
        ["source_table", "source_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # embedding_budget — global daily token cap.
    # ------------------------------------------------------------------
    op.create_table(
        "embedding_budget",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "daily_token_cap",
            sa.BigInteger(),
            server_default=sa.text("50000000"),
            nullable=False,
        ),
        sa.Column(
            "tokens_used_today",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "usage_window_started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Seed the single row. ON CONFLICT DO NOTHING keeps re-running the
    # migration safe even if someone INSERTed manually.
    op.execute(
        "INSERT INTO embedding_budget (id, daily_token_cap, tokens_used_today) "
        "VALUES (1, 50000000, 0) ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("embedding_budget")
    op.execute("DROP INDEX IF EXISTS ix_embeddings_cosine")
    op.drop_index("ix_embeddings_source", table_name="embeddings")
    op.drop_table("embeddings")
    op.drop_index("ix_embed_pending_created_at", table_name="embed_pending")
    op.drop_table("embed_pending")
    op.execute("DROP INDEX IF EXISTS ix_google_drive_files_shared_with")
    op.drop_index(
        "ix_google_drive_files_user_modified",
        table_name="google_drive_files",
    )
    op.drop_table("google_drive_files")
    # Leave the vector extension in place — other tables may use it.
