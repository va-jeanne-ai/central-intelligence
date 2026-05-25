"""Google Drive API client — read-only fetch for the RAG ingest pipeline.

Two public entry points:

  * :func:`fetch_all_files` — paginates ``files.list`` for the calling
    user, yielding one parsed dict per file. Optional ``since_iso``
    incrementalizes the sweep.
  * :func:`fetch_file_content` — mime-dispatched content extractor.
    Google Docs / Sheets / Slides come back via ``files.export``;
    PDF / DOCX / plain-text via ``files.get_media``. Returns ``None``
    for unsupported mime types so the caller can skip them cleanly.

Heavy parsing libs (``pdfplumber``, ``python-docx``) are imported lazily
inside the handler that needs them — keeps the import graph slim for
the Celery worker even if Drive isn't being touched on a given run.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Iterator

from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)


# Drive file mime types we know how to extract content from.
GOOGLE_DOC = "application/vnd.google-apps.document"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE = "application/vnd.google-apps.presentation"
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT = "text/plain"
MD = "text/markdown"

# Per-file content extraction cap. Drive lets you download larger files,
# but parsing a 50MB PDF in a Celery worker is a memory disaster — we
# skip and only index the metadata. 15MB lets through most decks +
# reports while still keeping pdfplumber's peak memory bounded
# (pdfplumber typically uses 5–10x the raw byte size during extraction).
_MAX_CONTENT_BYTES = 15 * 1024 * 1024  # 15MB

# Trash folders, app-data, and Google-Sites are noise we never want
# to index even if the user happens to share them.
_SKIP_MIME_TYPES = {
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.site",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.script",
}


# Fields list — keep tight; Drive's quota is per-field on list calls.
_LIST_FIELDS = (
    "nextPageToken, files(id, name, mimeType, owners(emailAddress), "
    "modifiedTime, webViewLink, parents, size, trashed, "
    "permissions(emailAddress, type, role), headRevisionId)"
)


def _build_service(credentials: Credentials):
    """Construct a Drive v3 service from a Credentials object."""
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def fetch_all_files(
    credentials: Credentials,
    since_iso: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield parsed Drive file dicts.

    Each yielded dict:

        {
          "provider_file_id": str,
          "name": str | None,
          "mime_type": str | None,
          "owner_email": str | None,
          "modified_time": datetime | None,
          "web_view_link": str | None,
          "parent_folder_id": str | None,
          "shared_with": list[str],          # lowercase emails
          "size_bytes": int | None,
          "is_trashed": bool,
          "head_revision_id": str | None,    # used as content-hash for binary files
        }

    Folders, Sites, Forms, and Scripts are filtered out before yielding.
    The parent folder *name* (vs. id) is fetched lazily by the caller
    if needed — paying for an extra round-trip per file inside the
    iterator is too expensive.
    """
    service = _build_service(credentials)

    q_parts: list[str] = ["trashed = false"]
    if since_iso:
        # Drive's `modifiedTime >` accepts RFC 3339; the caller-supplied
        # ISO string is already in that shape.
        q_parts.append(f"modifiedTime > '{since_iso}'")
    query = " and ".join(q_parts)

    page_token: str | None = None
    page_count = 0
    while True:
        try:
            list_resp = service.files().list(
                q=query,
                pageSize=100,
                pageToken=page_token,
                fields=_LIST_FIELDS,
                # corpora=user grabs files owned by + shared with the user.
                corpora="user",
                spaces="drive",
                includeItemsFromAllDrives=False,
                supportsAllDrives=False,
            ).execute()
        except HttpError as exc:
            logger.warning("drive: files.list failed — %s", exc)
            return

        page_count += 1
        for f in list_resp.get("files") or []:
            mime = f.get("mimeType")
            if mime in _SKIP_MIME_TYPES:
                continue
            yield _parse_file(f)

        page_token = list_resp.get("nextPageToken")
        if not page_token:
            break

    logger.info("drive fetch_all_files: drained %d page(s)", page_count)


def _parse_file(f: dict) -> dict[str, Any]:
    """Translate Drive's response shape into the upsert-ready dict."""
    owners = f.get("owners") or []
    owner_email = owners[0].get("emailAddress") if owners else None

    permissions = f.get("permissions") or []
    shared_with: list[str] = []
    for p in permissions:
        addr = p.get("emailAddress")
        if addr:
            shared_with.append(addr.lower())

    return {
        "provider_file_id": f.get("id"),
        "name": f.get("name"),
        "mime_type": f.get("mimeType"),
        "owner_email": owner_email,
        "modified_time": _parse_rfc3339(f.get("modifiedTime")),
        "web_view_link": f.get("webViewLink"),
        "parent_folder_id": (f.get("parents") or [None])[0],
        "shared_with": shared_with,
        "size_bytes": int(f["size"]) if f.get("size") and str(f["size"]).isdigit() else None,
        "is_trashed": bool(f.get("trashed")),
        "head_revision_id": f.get("headRevisionId"),
    }


def _parse_rfc3339(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def fetch_parent_folder_name(
    credentials: Credentials, folder_id: str,
) -> str | None:
    """One-off ``files.get`` for the parent folder's display name.

    Called lazily — only after the sync has decided this file is
    worth indexing, so we don't pay the cost for every result page.
    """
    if not folder_id:
        return None
    try:
        service = _build_service(credentials)
        resp = service.files().get(
            fileId=folder_id, fields="name", supportsAllDrives=False,
        ).execute()
        return resp.get("name")
    except HttpError as exc:
        logger.warning("drive: get folder %s failed — %s", folder_id, exc)
        return None


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------


def fetch_file_content(
    credentials: Credentials, file_id: str, mime_type: str,
    size_bytes: int | None = None,
) -> str | None:
    """Return plain-text content for ``file_id`` or ``None`` if unsupported.

    Mime dispatch:

      * Google Docs   → ``files.export(text/plain)``
      * Google Sheets → ``files.export(text/csv)``
      * Google Slides → ``files.export(text/plain)``
      * PDF           → ``files.get_media`` + pdfplumber
      * DOCX          → ``files.get_media`` + python-docx
      * text/plain, text/markdown → ``files.get_media`` + UTF-8 decode

    Files larger than 15MB are skipped. Returns ``None`` for any other
    mime type so the caller knows to leave ``extracted_text`` empty.
    """
    if size_bytes is not None and size_bytes > _MAX_CONTENT_BYTES:
        logger.info(
            "drive: skipping content extraction for %s (%d bytes > cap)",
            file_id, size_bytes,
        )
        return None

    service = _build_service(credentials)

    try:
        text: str | None
        if mime_type == GOOGLE_DOC:
            text = _export(service, file_id, "text/plain")
        elif mime_type == GOOGLE_SHEET:
            text = _export(service, file_id, "text/csv")
        elif mime_type == GOOGLE_SLIDE:
            text = _export(service, file_id, "text/plain")
        elif mime_type == PDF:
            data = _download_media(service, file_id)
            text = _parse_pdf_bytes(data) if data else None
        elif mime_type == DOCX:
            data = _download_media(service, file_id)
            text = _parse_docx_bytes(data) if data else None
        elif mime_type in (TXT, MD):
            data = _download_media(service, file_id)
            text = data.decode("utf-8", errors="replace") if data else None
        else:
            return None
        # Postgres text columns reject NUL (0x00). PDFs and Google Docs
        # exports occasionally emit them; strip before returning so the
        # downstream insert + embed pipeline doesn't choke. Same for
        # surrogate halves from broken UTF-8.
        return _sanitize_text(text)
    except HttpError as exc:
        logger.warning(
            "drive fetch_file_content: API error file=%s mime=%s — %s",
            file_id, mime_type, exc,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "drive fetch_file_content: parse error file=%s mime=%s — %s",
            file_id, mime_type, exc,
        )
        return None

    return None


def _sanitize_text(text: str | None) -> str | None:
    """Drop characters Postgres ``text`` columns can't store.

    Postgres rejects NUL (0x00) in text values. PDF + Google Docs
    extractions occasionally emit them. We also drop lone surrogate
    halves which break UTF-8 round-tripping. Returns ``None`` if the
    sanitised result is empty/whitespace so the caller treats it the
    same as "no extractable content".
    """
    if text is None:
        return None
    cleaned = text.replace("\x00", "")
    # Lone surrogates (0xD800-0xDFFF) sneak in from broken decoders
    # and corrupt the asyncpg binding.
    cleaned = "".join(
        ch for ch in cleaned
        if not (0xD800 <= ord(ch) <= 0xDFFF)
    )
    return cleaned if cleaned.strip() else None


def _export(service, file_id: str, mime: str) -> str | None:
    """Drive ``files.export`` returns the bytes directly (no resumable)."""
    raw = service.files().export(fileId=file_id, mimeType=mime).execute()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        return raw
    return None


def _download_media(service, file_id: str) -> bytes | None:
    """Download a binary file using the resumable media downloader."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request, chunksize=1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
        if buf.tell() > _MAX_CONTENT_BYTES:
            logger.info(
                "drive: aborting download of %s — exceeded %d bytes",
                file_id, _MAX_CONTENT_BYTES,
            )
            return None
    return buf.getvalue()


def _parse_pdf_bytes(data: bytes) -> str | None:
    """Extract text from a PDF byte string via pdfplumber."""
    import pdfplumber  # lazy import — only loaded when a PDF lands

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages) if pages else None


def _parse_docx_bytes(data: bytes) -> str | None:
    """Extract paragraph text from a .docx byte string via python-docx."""
    import docx as python_docx  # lazy import

    document = python_docx.Document(io.BytesIO(data))
    paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    return "\n\n".join(paragraphs) if paragraphs else None
