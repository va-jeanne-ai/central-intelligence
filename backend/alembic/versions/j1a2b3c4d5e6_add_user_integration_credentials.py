"""add user_integration_credentials table — per-user OAuth refresh-token storage

Per-user companion to the deployment-wide `integrations` row. Each
staff member who connects their Google account gets one row here per
provider (e.g. `'google_workspace'`). Holds the encrypted refresh +
access token pair the backend uses to impersonate that user's mailbox
during the Gmail sync.

`Integration` rows stay as-is — they capture deployment-wide config
(status, provider availability). This table captures per-user secrets.

Future Drive/Calendar reuse the same table by writing rows with
different `provider` values.

Revision ID: j1a2b3c4d5e6
Revises: i9d0e1f2g3h4
Create Date: 2026-05-25 23:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j1a2b3c4d5e6"
down_revision: Union[str, None] = "i9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_integration_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        # Fernet-encrypted JSON of:
        #   { refresh_token, access_token, token_uri,
        #     client_id, client_secret, expires_at }
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        # Granted scopes (audit trail; the integrations registry has the
        # request shape but Google may downscope at consent time).
        sa.Column("scopes", postgresql.JSONB, nullable=True),
        # The Gmail address the user authorized — surfaced in the UI as
        # "Connected as user@example.com". Lets us tell connected
        # mailboxes apart even if the same user re-authorizes a
        # different Google account.
        sa.Column("connected_email", sa.String(255), nullable=True),
        # Per-user sync status. Distinct from
        # integrations.last_synced_at (which is deployment-wide).
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(32), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
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
            "user_id", "provider", name="uq_user_integration_credentials_user_provider",
        ),
    )
    # "Every connected user for provider X" is the dominant access
    # pattern (every sync run does this). The composite unique above
    # already indexes (user_id, provider); add a single-column index
    # on provider so the sync's `WHERE provider='google_workspace'`
    # query stays cheap as the table grows.
    op.create_index(
        op.f("ix_user_integration_credentials_provider"),
        "user_integration_credentials",
        ["provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_integration_credentials_provider"),
        table_name="user_integration_credentials",
    )
    op.drop_table("user_integration_credentials")
