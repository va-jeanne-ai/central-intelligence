"""Upsert helper for Drive files → google_drive_files + embed_pending.

Called once per file dict yielded by ``drive_client.fetch_all_files``.
Finds-or-creates the per-user ``google_drive_files`` row keyed on
``(provider_file_id, connected_via_user_id)``. When the file is new
or its ``content_hash`` differs from the previously-stored value, the
helper also enqueues an ``embed_pending`` row so the next embed
worker tick picks it up.

Sync session only — caller (Celery task) owns the transaction.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operational import EmbedPending, GoogleDriveFile

logger = logging.getLogger(__name__)


SOURCE_TABLE = "google_drive_files"


def compute_content_hash(text: str | None, fallback: str | None = None) -> str:
    """sha256(text or fallback)[:64] — keeps the column ≤64 chars."""
    src = text if (text and text.strip()) else (fallback or "")
    return hashlib.sha256(src.encode("utf-8", errors="replace")).hexdigest()[:64]


def upsert_drive_file_sync(
    session: Session,
    user_id: uuid.UUID,
    file_dict: dict[str, Any],
    extracted_text: str | None,
    parent_folder_name: str | None = None,
) -> tuple[bool, bool]:
    """Upsert one Drive file. Returns ``(inserted, content_changed)``.

    ``content_changed`` is True when (a) the row is new, or (b) the
    computed ``content_hash`` differs from the stored value. The
    caller uses this to decide whether to enqueue an embed_pending row.
    """
    provider_file_id: str | None = file_dict.get("provider_file_id")
    if not provider_file_id:
        logger.warning("drive_upsert: missing provider_file_id; skipping")
        return False, False

    # Belt-and-braces: strip NUL bytes if any extractor returned them.
    # Postgres text columns reject them; the embed worker downstream
    # also breaks on NUL inputs. The Drive client sanitises already,
    # but this guards against direct callers and future ingest sources.
    if extracted_text is not None and "\x00" in extracted_text:
        extracted_text = extracted_text.replace("\x00", "")
        if not extracted_text.strip():
            extracted_text = None

    new_hash = compute_content_hash(
        extracted_text,
        fallback=file_dict.get("name"),
    )

    row = session.execute(
        select(GoogleDriveFile).where(
            GoogleDriveFile.provider_file_id == provider_file_id,
            GoogleDriveFile.connected_via_user_id == user_id,
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    inserted = False
    content_changed = False

    if row is None:
        row = GoogleDriveFile(
            id=uuid.uuid4(),
            connected_via_user_id=user_id,
            provider_file_id=provider_file_id,
            name=file_dict.get("name"),
            mime_type=file_dict.get("mime_type"),
            owner_email=file_dict.get("owner_email"),
            modified_time=file_dict.get("modified_time"),
            web_view_link=file_dict.get("web_view_link"),
            parent_folder_id=file_dict.get("parent_folder_id"),
            parent_folder_name=parent_folder_name,
            shared_with=file_dict.get("shared_with") or [],
            size_bytes=file_dict.get("size_bytes"),
            is_trashed=bool(file_dict.get("is_trashed")),
            extracted_text=extracted_text,
            content_hash=new_hash,
            last_extracted_at=now if extracted_text else None,
        )
        session.add(row)
        session.flush()  # populate row.id for the embed_pending FK-less link
        inserted = True
        content_changed = True
    else:
        # Always refresh metadata — filename / sharing list / parent
        # can drift independently of content.
        row.name = file_dict.get("name") or row.name
        row.mime_type = file_dict.get("mime_type") or row.mime_type
        row.owner_email = file_dict.get("owner_email") or row.owner_email
        if file_dict.get("modified_time") is not None:
            row.modified_time = file_dict["modified_time"]
        row.web_view_link = file_dict.get("web_view_link") or row.web_view_link
        row.parent_folder_id = file_dict.get("parent_folder_id") or row.parent_folder_id
        if parent_folder_name:
            row.parent_folder_name = parent_folder_name
        if file_dict.get("shared_with") is not None:
            row.shared_with = file_dict["shared_with"]
        row.size_bytes = file_dict.get("size_bytes") or row.size_bytes
        row.is_trashed = bool(file_dict.get("is_trashed"))

        if new_hash != (row.content_hash or ""):
            row.extracted_text = extracted_text
            row.content_hash = new_hash
            row.last_extracted_at = now if extracted_text else None
            content_changed = True

    # If the content changed and we actually have something embeddable,
    # enqueue. Pure-metadata files (extracted_text=None) get stored but
    # not embedded — there's nothing semantic to embed for an .xlsx.
    if content_changed and extracted_text and extracted_text.strip():
        session.add(EmbedPending(
            id=uuid.uuid4(),
            source_table=SOURCE_TABLE,
            source_id=str(row.id),
            text_to_embed=extracted_text,
            content_hash=new_hash,
        ))

    return inserted, content_changed
