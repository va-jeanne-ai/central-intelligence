"""Gmail API client — read-only fetch for the lead email-thread sync.

Wraps ``googleapiclient.discovery.build('gmail', 'v1', credentials=...)``
with a service-account credential and domain-wide delegation. The
public surface is one function, ``fetch_messages_for_email()``, which
paginates ``users.messages.list`` for messages where a given email
address appears (From/To/Cc/Bcc), fetches each message in full, and
yields a parsed dict ready for direct DB upsert.

The fiddly part is the MIME walk to pull a single ``text/plain`` body
from what Gmail might serve as multipart/alternative or multipart/
mixed with nested boundaries. ``_extract_plain_text`` handles the
common shapes; HTML is intentionally ignored.

Attachments are recorded as metadata only — filename, MIME, size — so
the lead detail page can show "📎 contract.pdf · 240 KB" tags without
us downloading bytes.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any, Iterator

from google.auth.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Client construction
# ---------------------------------------------------------------------------


def _build_service(credentials: Credentials):
    """Construct a Gmail v1 service from a Credentials object.

    The caller passes whatever Credentials variant is appropriate — for
    the per-user OAuth flow that's a
    ``google.oauth2.credentials.Credentials``; in theory the same
    function works with a service-account credential too. The
    downstream client only calls ``.refresh()`` and ``.request()``
    methods that both variants implement.
    """
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


# ---------------------------------------------------------------------------
# MIME parsing
# ---------------------------------------------------------------------------


def _decode_b64url(data: str | None) -> bytes:
    """Gmail uses URL-safe base64 with no padding."""
    if not data:
        return b""
    # Pad to a multiple of 4
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _walk_parts(payload: dict) -> Iterator[dict]:
    """Yield every leaf part of a Gmail message payload."""
    if "parts" in payload:
        for part in payload["parts"]:
            yield from _walk_parts(part)
    else:
        yield payload


def _extract_plain_text(payload: dict) -> str | None:
    """Find the first ``text/plain`` body in the payload tree.

    Falls back to None if the message is HTML-only — we intentionally
    don't transcode HTML for the v1 surface.
    """
    for part in _walk_parts(payload):
        mime_type = part.get("mimeType", "")
        if mime_type != "text/plain":
            continue
        body = part.get("body") or {}
        data = body.get("data")
        if not data:
            continue
        try:
            return _decode_b64url(data).decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            logger.warning("gmail: failed to decode text/plain body — %s", exc)
            return None
    return None


def _extract_attachments_meta(payload: dict) -> list[dict[str, Any]]:
    """Collect filename + size + mime for each attachment part.

    We don't fetch the bytes — Gmail requires a separate
    ``users.messages.attachments.get`` call which is out of scope for
    v1. Tags rendered in the UI are enough.
    """
    out: list[dict[str, Any]] = []
    for part in _walk_parts(payload):
        filename = part.get("filename")
        if not filename:
            continue
        body = part.get("body") or {}
        out.append({
            "filename": filename,
            "size": int(body.get("size") or 0),
            "mime_type": part.get("mimeType") or "application/octet-stream",
        })
    return out


def _header(headers: list[dict], name: str) -> str | None:
    """Case-insensitive header lookup."""
    name_low = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_low:
            return h.get("value")
    return None


def _parse_address_list(raw: str | None) -> list[str]:
    """Split a To/Cc header into a list of bare email addresses."""
    if not raw:
        return []
    parsed = getaddresses([raw])
    return [addr for _, addr in parsed if addr]


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _build_query(email_address: str, since_iso: str | None = None) -> str:
    """Compose the Gmail search query for one lead.

    Gmail's search syntax: `from:X OR to:X OR cc:X OR bcc:X`. The
    `after:` filter accepts a unix timestamp (seconds) — we use the
    last successful sync time so incremental runs don't re-fetch
    everything.
    """
    safe_email = email_address.replace('"', "")
    address_clause = (
        f'(from:"{safe_email}" OR to:"{safe_email}" '
        f'OR cc:"{safe_email}" OR bcc:"{safe_email}")'
    )
    if since_iso:
        try:
            dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
            unix_ts = int(dt.timestamp())
            return f"{address_clause} after:{unix_ts}"
        except (ValueError, AttributeError):
            pass
    return address_clause


def fetch_messages_for_email(
    credentials: Credentials,
    email_address: str,
    since_iso: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield parsed messages where ``email_address`` appears.

    Auth-agnostic — give it a usable ``Credentials`` object (today,
    a per-user OAuth credential built by
    ``services/google_oauth_credentials.py``) and it'll paginate
    that user's mailbox for messages matching the address.

    Each yielded dict is shaped for direct ``email_messages`` upsert:

        {
          "provider_thread_id": str,
          "provider_message_id": str,
          "from_address": str | None,
          "to_addresses": list[str],
          "cc_addresses": list[str],
          "subject": str | None,
          "body_text": str | None,
          "sent_at": datetime | None,
          "has_attachments": bool,
          "attachments_meta": list[{filename, size, mime_type}],
        }

    Errors per-message are logged and skipped — one malformed message
    shouldn't break the whole sync.
    """
    service = _build_service(credentials)
    query = _build_query(email_address, since_iso)

    page_token: str | None = None
    page_count = 0
    while True:
        list_resp = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=100,
            pageToken=page_token,
        ).execute()
        page_count += 1
        ids = [m["id"] for m in (list_resp.get("messages") or [])]
        for msg_id in ids:
            try:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()
            except Exception as exc:  # noqa: BLE001
                logger.warning("gmail: messages.get failed id=%s — %s", msg_id, exc)
                continue

            payload = msg.get("payload") or {}
            headers = payload.get("headers") or []
            attachments = _extract_attachments_meta(payload)
            sent_at = _parse_date(_header(headers, "Date"))
            if sent_at is None and msg.get("internalDate"):
                try:
                    sent_at = datetime.fromtimestamp(
                        int(msg["internalDate"]) / 1000.0, tz=timezone.utc,
                    )
                except (ValueError, TypeError):
                    sent_at = None

            yield {
                "provider_thread_id": msg.get("threadId"),
                "provider_message_id": msg.get("id"),
                "from_address": _parse_address_list(_header(headers, "From"))[:1] and
                                _parse_address_list(_header(headers, "From"))[0] or None,
                "to_addresses": _parse_address_list(_header(headers, "To")),
                "cc_addresses": _parse_address_list(_header(headers, "Cc")),
                "subject": _header(headers, "Subject"),
                "body_text": _extract_plain_text(payload),
                "sent_at": sent_at,
                "has_attachments": bool(attachments),
                "attachments_meta": attachments,
            }

        page_token = list_resp.get("nextPageToken")
        if not page_token:
            break

    logger.info(
        "gmail fetch_messages_for_email: drained %d page(s) for %s",
        page_count, email_address,
    )
