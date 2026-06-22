"""Pure WGR-row → CI-model-kwargs mapping functions.

One function per source table. Each takes a raw WGR row dict (as produced by
``wgr_client``) and returns a dict of CI model column kwargs — or ``None`` to
skip the row (test data, empties). Pure and side-effect-free so they're unit
tested against documented sample rows without a DB.

Conventions:
  * Shared-domain tables (lead/call/appointment) get ``source='wgr'`` +
    ``external_id=<wgr PK>`` for idempotent dedup against CI's existing schema.
  * WGR-only tables (sales_*, webinar, opt-in) keep WGR's native PK as the CI PK,
    so no source/external_id is needed.
  * Phones normalised to E.164-ish; rep identity always keyed on rep_id, never
    the dirty owner-name strings.
  * Test/junk call rows (``TEST_`` ids) are filtered out (return None).
"""

from __future__ import annotations

import re
from typing import Any, Optional

WGR_SOURCE = "wgr"


# ---------------------------------------------------------------------------
# Small shared transforms
# ---------------------------------------------------------------------------

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Best-effort E.164. WGR phones are mixed (``12143365496`` / ``+15612...``).

    Keeps a leading '+', strips other non-digits, and assumes a bare 10-digit
    US number gets a '+1'. Returns None for empty/garbage."""
    if not phone:
        return None
    p = phone.strip()
    if not p:
        return None
    had_plus = p.startswith("+")
    digits = re.sub(r"\D", "", p)
    if not digits:
        return None
    if had_plus:
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits


def _clean(v: Any) -> Any:
    """Trim strings, pass through everything else; '' -> None."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def is_test_call(call_id: Optional[str]) -> bool:
    """WGR has Greg's manual test rows (``TEST_T1_Alice`` etc.) that should not
    pollute CI's call corpus."""
    if not call_id:
        return False
    return call_id.upper().startswith("TEST_") or "TEST_T" in call_id.upper()


# Map WGR appointment outcome / call_result strings → CI status enums-ish.
_APPT_OUTCOME_TO_STATUS = {
    "showed": "completed",
    "confirmed": "scheduled",
    "cancelled": "cancelled",
    "no show": "no_show",
    "invalid": "cancelled",
}


def map_appointment_status(outcome: Optional[str]) -> Optional[str]:
    if not outcome:
        return None
    return _APPT_OUTCOME_TO_STATUS.get(outcome.strip().lower(), outcome.strip().lower())


# ---------------------------------------------------------------------------
# Shared-domain tables (source='wgr' + external_id; CI UUID/string PKs)
# ---------------------------------------------------------------------------

def map_lead(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ext = _clean(row.get("lead_id"))
    if not ext:
        return None
    return {
        "source": WGR_SOURCE,
        "external_id": ext,
        "name": _clean(row.get("name")),
        "email": (_clean(row.get("email")) or None),
        "phone": normalize_phone(row.get("phone")),
        # WGR pipeline_stage is ~94% null and unreliable; leave CI status unset
        # rather than import a misleading funnel field (analysis doc finding).
        "status": _clean(row.get("pipeline_stage")),
        # When the lead entered the funnel upstream. Surfaced as the lead's date
        # in the UI (created_at is sync time, not entry time). Often null in WGR.
        "entry_date": row.get("entry_date"),
        "notes": _clean(row.get("notes")),
    }


def map_call(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ext = _clean(row.get("call_id"))
    if not ext or is_test_call(ext):
        return None
    return {
        # CI Call PK is a string; reuse WGR's call_id so it's stable + readable.
        "id": ext,
        "source": WGR_SOURCE,
        "external_id": ext,
        "date": row.get("date"),
        "call_type": _clean(row.get("call_type")),
        "call_result": _clean(row.get("call_result")),
        # call_owner kept only as a display label; rep identity lives on the
        # sales_* tables keyed by rep_id.
        "call_owner": _clean(row.get("call_owner")),
        "transcript_source": _clean(row.get("transcript_source")),
        "transcript_uid": _clean(row.get("transcript_uid")),
        "transcript_quality": _clean(row.get("transcript_quality")),
        "transcript_link": _clean(row.get("transcript_link")),
        "processed_date": row.get("processed_date"),
        "call_duration_minutes": row.get("call_duration_minutes"),
        "notes": _clean(row.get("notes")),
    }


def map_appointment(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    ext = _clean(row.get("appointment_id"))
    if not ext:
        return None
    return {
        "source": WGR_SOURCE,
        "external_id": ext,
        "status": map_appointment_status(row.get("outcome")),
        "appointment_type": _clean(row.get("call_number")) or _clean(row.get("calendar_name")),
        "scheduled_at": row.get("scheduled_date"),
        "notes": _clean(row.get("notes")),
        # lead linkage resolved at upsert time via the WGR lead_id → CI lead.
        "_wgr_lead_id": _clean(row.get("lead_id")),
    }


# ---------------------------------------------------------------------------
# Call-derived intelligence (CI string PKs == WGR PKs; near 1:1 columns)
# ---------------------------------------------------------------------------

_INSIGHT_FIELDS = (
    "speaker_name", "insight_type", "signal_family", "signal", "signal_strength",
    "pain_layer", "raw_quote", "what_they_say", "the_real_problem", "emotional_driver",
    "core_fear_revealed", "false_belief_revealed", "structural_obstacle",
    "identity_signal", "buying_trigger", "objection_created", "marketing_translation",
    "hook_angle_example", "best_use_case", "quote_confidence",
)


def map_insight(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    iid = _clean(row.get("insight_id"))
    if not iid:
        return None
    out: dict[str, Any] = {"id": iid, "call_id": _clean(row.get("call_id"))}
    for f in _INSIGHT_FIELDS:
        out[f] = _clean(row.get(f))
    fs = row.get("frequency_score")
    out["frequency_score"] = int(fs) if fs is not None else 0
    return out


_CONTENT_FIELDS = (
    "insight_id", "call_id", "source", "market_audience", "content_format",
    "content_angle", "trigger_insight", "raw_quote", "content_premise",
    "hook_opening_line", "teaching_point", "cta_idea", "priority_level",
    "best_platform", "repurpose_opportunities",
)


def map_content_idea(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    cid = _clean(row.get("content_id"))
    if not cid:
        return None
    out: dict[str, Any] = {"id": cid}
    for f in _CONTENT_FIELDS:
        out[f] = _clean(row.get(f))
    out["idea_score"] = row.get("idea_score")
    out["status"] = _clean(row.get("status")) or "Idea"
    return out


def map_market_signal(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    sig = _clean(row.get("signal"))
    fam = _clean(row.get("signal_family"))
    if not sig and not fam:
        return None
    return {
        "signal_family": fam,
        "signal": sig,
        "insight_type": _clean(row.get("insight_type")),
        "total_mentions": int(row.get("total_mentions") or 0),
        "last_30_days": int(row.get("last_30_days") or 0),
        "last_7_days": int(row.get("last_7_days") or 0),
        "example_quote": _clean(row.get("example_quote")),
        "example_call_id": _clean(row.get("example_call_id")),
        "best_marketing_angle": _clean(row.get("best_marketing_angle")),
        "notes": _clean(row.get("notes")),
    }


# ---------------------------------------------------------------------------
# Config-ish (CI string/int PKs)
# ---------------------------------------------------------------------------

def map_offer(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    oid = _clean(row.get("offer_id"))
    if not oid:
        return None
    return {
        "offer_id": oid,
        "name": _clean(row.get("name")),
        "offer_type": _clean(row.get("offer_type")),
        "description": _clean(row.get("description")),
        "price": row.get("price"),
        "status": _clean(row.get("status")) or "active",
        "url": _clean(row.get("url")),
        "notes": _clean(row.get("notes")),
    }


def map_business_profile(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not _clean(row.get("business_name")):
        return None
    return {
        "id": row.get("id"),
        "business_name": _clean(row.get("business_name")),
        "mission": _clean(row.get("mission")),
        "target_audience": _clean(row.get("target_audience")),
        "brand_voice": _clean(row.get("brand_voice")),
        "core_values": _clean(row.get("core_values")),
        "key_differentiators": _clean(row.get("key_differentiators")),
        "primary_market": _clean(row.get("primary_market")),
        "notes": _clean(row.get("notes")),
    }


# ---------------------------------------------------------------------------
# WGR-only tables (native PK kept as CI PK; columns mirror WGR 1:1)
# ---------------------------------------------------------------------------

def map_sales_rep(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    rid = _clean(row.get("rep_id"))
    if not rid:
        return None
    caps = row.get("capabilities")
    return {
        "rep_id": rid,
        "business_id": row.get("business_id"),
        "full_name": _clean(row.get("full_name")) or rid,
        "email": _clean(row.get("email")),
        "ghl_user_id": _clean(row.get("ghl_user_id")),
        "slack_user_id": _clean(row.get("slack_user_id")),
        "role": _clean(row.get("role")),
        "status": _clean(row.get("status")) or "active",
        "probation_start_date": row.get("probation_start_date"),
        "probation_end_date": row.get("probation_end_date"),
        "current_tier_access": row.get("current_tier_access"),
        "historical_aliases": _clean(row.get("historical_aliases")),
        "timezone": _clean(row.get("timezone")),
        "capabilities": list(caps) if isinstance(caps, (list, tuple)) else None,
        "hired_at": row.get("hired_at"),
        "last_login_at": row.get("last_login_at"),
    }


def map_scorecard_category(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    cid = _clean(row.get("category_id"))
    if not cid:
        return None
    return {
        "category_id": cid,
        "display_name": _clean(row.get("display_name")) or cid,
        "description": _clean(row.get("description")),
        "sort_order": row.get("sort_order"),
        "applies_to": _clean(row.get("applies_to")),
        "weight": row.get("weight"),
        "active": bool(row.get("active", True)),
    }


def map_call_score(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    sid = _clean(row.get("score_id"))
    if not sid or row.get("score") is None:
        return None
    return {
        "score_id": sid,
        "call_id": _clean(row.get("call_id")),
        "category_id": _clean(row.get("category_id")),
        "rep_id": _clean(row.get("rep_id")),
        "business_id": row.get("business_id"),
        "score": row.get("score"),
        "notes": _clean(row.get("notes")),
        "scored_at": row.get("scored_at"),
    }


def map_strike_rule(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    rid = _clean(row.get("rule_id"))
    if not rid:
        return None
    roles = row.get("applies_to_roles")
    return {
        "rule_id": rid,
        "name": _clean(row.get("name")) or rid,
        "strike_type": _clean(row.get("strike_type")),
        "call_type": _clean(row.get("call_type")),
        "threshold_score": row.get("threshold_score"),
        "evidence_count": row.get("evidence_count"),
        "window_days": row.get("window_days"),
        "phase": _clean(row.get("phase")),
        "applies_to_roles": list(roles) if isinstance(roles, (list, tuple)) else None,
        "active": bool(row.get("active", True)),
        "notes": _clean(row.get("notes")),
    }


def map_coaching_strike(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    sid = _clean(row.get("strike_id"))
    if not sid:
        return None
    return {
        "strike_id": sid,
        "rep_id": _clean(row.get("rep_id")),
        "business_id": row.get("business_id"),
        "rule_id": _clean(row.get("rule_id")),
        "category_id": _clean(row.get("category_id")),
        "call_type": _clean(row.get("call_type")),
        "status": _clean(row.get("status")) or "open",
        "severity": _clean(row.get("severity")) or "flag",
        "triggered_at": row.get("triggered_at"),
        "activated_at": row.get("activated_at"),
        "resolved_at": row.get("resolved_at"),
        "resolved_by": _clean(row.get("resolved_by")),
        "resolution_notes": _clean(row.get("resolution_notes")),
        "created_by": _clean(row.get("created_by")),
        "ai_summary": _clean(row.get("ai_summary")),
    }


def map_strike_action(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    aid = _clean(row.get("action_id"))
    if not aid:
        return None
    return {
        "action_id": aid,
        "strike_id": _clean(row.get("strike_id")),
        "action": _clean(row.get("action")) or "unknown",
        "from_status": _clean(row.get("from_status")),
        "to_status": _clean(row.get("to_status")),
        "actor": _clean(row.get("actor")),
        "notes": _clean(row.get("notes")),
        "occurred_at": row.get("occurred_at"),
    }


def map_strike_evidence(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    eid = _clean(row.get("evidence_id"))
    if not eid:
        return None
    return {
        "evidence_id": eid,
        "strike_id": _clean(row.get("strike_id")),
        "call_score_id": _clean(row.get("call_score_id")),
        "added_at": row.get("added_at"),
    }


def map_eod_report(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    rid = _clean(row.get("report_id"))
    if not rid:
        return None
    return {
        "report_id": rid,
        "business_id": row.get("business_id"),
        "report_type": _clean(row.get("report_type")),
        "rep_id": _clean(row.get("rep_id")),
        "report_date": row.get("report_date"),
        "generated_at": row.get("generated_at"),
        "content": row.get("content"),
        "slack_delivered_at": row.get("slack_delivered_at"),
        "slack_message_ts": _clean(row.get("slack_message_ts")),
        "slack_channel": _clean(row.get("slack_channel")),
        "delivery_error": _clean(row.get("delivery_error")),
    }


def map_closed_sale(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    sid = _clean(row.get("sale_id"))
    if not sid:
        return None
    return {
        "sale_id": sid,
        "lead_id": _clean(row.get("lead_id")),
        "ghl_contact_id": _clean(row.get("ghl_contact_id")),
        "offer_id": _clean(row.get("offer_id")),
        "rep_id": _clean(row.get("rep_id")),  # ~30/74 null → "Unattributed"
        "product_name": _clean(row.get("product_name")),
        "amount_collected": row.get("amount_collected"),
        "revenue_earned": row.get("revenue_earned"),
        "close_date": row.get("close_date"),
        "time_to_close_days": row.get("time_to_close_days"),
        "notes": _clean(row.get("notes")),
    }


def map_sales_activity(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    aid = _clean(row.get("activity_id"))
    if not aid:
        return None
    return {
        "activity_id": aid,
        "rep_id": _clean(row.get("rep_id")),  # ~83% null (attribution gap)
        "business_id": row.get("business_id"),
        "lead_id": _clean(row.get("lead_id")),
        "activity_type": _clean(row.get("activity_type")),
        "channel": _clean(row.get("channel")),
        "duration_seconds": row.get("duration_seconds"),
        "body": _clean(row.get("body")),
        "ghl_event_type": _clean(row.get("ghl_event_type")),
        "ghl_resource_id": _clean(row.get("ghl_resource_id")),
        "occurred_at": row.get("occurred_at"),
        # SQLAlchemy attr name; the DB column is "metadata". The async ORM path
        # uses this key directly; the bulk loader remaps it to the column name.
        "activity_metadata": row.get("metadata"),
    }


def map_webinar_engagement(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    eid = _clean(row.get("engagement_id"))
    if not eid:
        return None
    return {
        "engagement_id": eid,
        "lead_id": _clean(row.get("lead_id")),
        "ghl_contact_id": _clean(row.get("ghl_contact_id")),
        "email": _clean(row.get("email")),
        "phone": normalize_phone(row.get("phone")),
        "registration_date": row.get("registration_date"),
        "watched_live": bool(row.get("watched_live", False)),
        "time_live_seconds": row.get("time_live_seconds"),
        "watched_replay": bool(row.get("watched_replay", False)),
        "time_replay_seconds": row.get("time_replay_seconds"),
        "total_watched": bool(row.get("total_watched", False)),
        "utm_source": _clean(row.get("utm_source")),
        "utm_medium": _clean(row.get("utm_medium")),
        "utm_campaign": _clean(row.get("utm_campaign")),
        "utm_content": _clean(row.get("utm_content")),
    }


def map_email_campaign(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    """WGR email_campaigns → CI EmailCampaign. Deduped on (source, external_id).

    CI uses unique_opens/unique_clicks as the headline open/click counts (one per
    recipient), keeping total_opens/clicks out — the dashboard reports unique."""
    ext = _clean(row.get("campaign_id"))
    if not ext:
        return None
    return {
        "source": WGR_SOURCE,
        "external_id": str(ext),
        # name is NOT NULL in CI; fall back to the campaign id when WGR's is blank.
        "name": _clean(row.get("campaign_name")) or str(ext),
        "subject": _clean(row.get("subject_line")),
        "campaign_type": _clean(row.get("email_type")),
        # WGR has no draft/sent status; everything mirrored here was sent.
        "status": "sent",
        "sent_at": row.get("send_date"),
        "recipients_count": row.get("total_sent") or 0,
        "open_count": row.get("unique_opens") or 0,
        "click_count": row.get("unique_clicks") or 0,
        "unsubscribe_count": row.get("unsubscribes") or 0,
        "bounce_count": row.get("bounces") or 0,
        "open_rate": row.get("open_rate"),
        "click_rate": row.get("click_rate"),
        "body_html": _clean(row.get("body_copy")),
    }


def map_social_comment(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    """WGR comment_events → CI SocialComment. Deduped on (source, external_id).

    comment_text + post_id are NOT NULL in CI; WGR can leave both blank (a bare
    keyword trigger with no post link), so skip rows with no usable text."""
    ext = _clean(row.get("id"))
    text = _clean(row.get("comment_text"))
    if not ext or not text:
        return None
    return {
        "source": WGR_SOURCE,
        "external_id": str(ext),
        "platform": _clean(row.get("platform")) or "unknown",
        # post_id NOT NULL; fall back to the fb page when WGR has no post id.
        "post_id": _clean(row.get("post_id")) or _clean(row.get("fb_page_id")) or "unknown",
        # WGR comment_events carry no author name (GHL keyword triggers).
        "author_name": None,
        "comment_text": text,
        "commented_at": row.get("occurred_at"),
    }


def map_instagram_post(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    """WGR instagram_posts → CI InstagramPost. Deduped on (source, external_id)."""
    ext = _clean(row.get("ig_media_id"))
    if not ext:
        return None
    return {
        "source": WGR_SOURCE,
        "external_id": str(ext),
        "ig_media_id": str(ext),
        "permalink": _clean(row.get("permalink")),
        "media_type": _clean(row.get("media_type")),
        "is_reel": bool(row.get("is_reel", False)),
        "caption": _clean(row.get("caption")),
        "posted_at": row.get("posted_at"),
        "likes_count": row.get("likes_count"),
        "comments_count": row.get("comments_count"),
        "saves_count": row.get("saves_count"),
        "shares_count": row.get("shares_count"),
        "reach": row.get("reach"),
        "views": row.get("views"),
        "avg_watch_time_sec": row.get("avg_watch_time_sec"),
        "engagement_rate": row.get("engagement_rate"),
        "content_pillar": _clean(row.get("content_pillar")),
        "hook_text": _clean(row.get("hook_text")),
        "hook_type": _clean(row.get("hook_type")),
        "script_transcript": _clean(row.get("script_transcript")),
    }


def map_insight_tag(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    """WGR insight_tags → CI InsightTag. Deduped on (insight_id, tag).

    Keeps WGR's integer PK so re-runs are stable; FK to insights is nullable in
    CI, so a tag whose insight wasn't synced still lands (orphan-tolerant)."""
    tag = _clean(row.get("tag"))
    if not tag:
        return None
    return {
        "id": row.get("id"),
        "insight_id": _clean(row.get("insight_id")),
        "tag": tag,
    }


def map_opt_in_event(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    oid = _clean(row.get("opt_in_event_id"))
    if not oid or not _clean(row.get("lead_id")):
        return None
    return {
        "opt_in_event_id": str(oid),
        "lead_id": _clean(row.get("lead_id")),
        "source": _clean(row.get("source")),
        "occurred_at": row.get("occurred_at"),
        "utm_source": _clean(row.get("utm_source")),
        "utm_medium": _clean(row.get("utm_medium")),
        "utm_campaign": _clean(row.get("utm_campaign")),
        "utm_content": _clean(row.get("utm_content")),
        "external_id": _clean(row.get("external_id")),
        "raw_payload": row.get("raw_payload"),
    }
