"""Unit tests for duplicate-email lead merging in the WGR sync
(app.services.wgr_sync.upsert.plan_lead_writes).

WGR's leads table has no unique constraint on email — the same person can
appear as two rows with different lead_ids (seen live: morrisshort@mac.com,
mwolfenow@aol.com, gwheeler10@gmail.com). CI's ``leads.email`` is globally
unique, so blindly inserting the second row aborts the whole sync with
UniqueViolationError. ``plan_lead_writes`` is the pure insert/update planner
that must collapse those duplicates: merge into the existing CI lead (latest
data wins), never emit an INSERT that would trip ``ix_leads_email``.

Self-contained: runs with plain `python -m tests.test_wgr_lead_email_merge`
(no pytest, no live DB).
"""

from __future__ import annotations

import uuid
from datetime import date

from app.services.wgr_sync.upsert import plan_lead_writes

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def _lead(ext: str, email: str | None, *, name: str | None = None,
          status: str | None = None, entry: date | None = None) -> dict:
    """Shape produced by mapping.map_lead."""
    return {
        "source": "wgr",
        "external_id": ext,
        "name": name,
        "email": email,
        "phone": None,
        "status": status,
        "entry_date": entry,
        "notes": None,
    }


def test_existing_email_new_external_id_merges() -> None:
    # The reported bug: CI already holds this email under a different WGR
    # lead_id. Expect an UPDATE of the existing row, no INSERT, and the
    # identity keys (source/external_id/email) left untouched so the CI row
    # doesn't flip-flop between the two upstream duplicates.
    existing_id = uuid.uuid4()
    maps = [_lead("LEAD_NEW", "morrisshort@mac.com",
                  name="Morris Short", status="applied", entry=date(2026, 7, 14))]
    inserts, updates = plan_lead_writes(
        maps, by_ext={}, id_by_email={"morrisshort@mac.com": existing_id},
    )
    check("no insert emitted", inserts == [])
    check("one update emitted", len(updates) == 1)
    target_id, values = updates[0]
    check("updates the existing lead", target_id == existing_id)
    check("data fields carried", values.get("name") == "Morris Short"
          and values.get("status") == "applied")
    check("external_id not overwritten", "external_id" not in values)
    check("source not overwritten", "source" not in values)
    check("email not overwritten", "email" not in values)


def test_email_match_is_case_insensitive() -> None:
    existing_id = uuid.uuid4()
    maps = [_lead("LEAD_NEW", "MorrisShort@Mac.com")]
    inserts, updates = plan_lead_writes(
        maps, by_ext={}, id_by_email={"morrisshort@mac.com": existing_id},
    )
    check("case-insensitive: no insert", inserts == [])
    check("case-insensitive: update targets existing",
          len(updates) == 1 and updates[0][0] == existing_id)


def test_in_batch_duplicate_emails_latest_entry_date_wins() -> None:
    # Two upstream rows for the same person arrive in one batch. Only one row
    # may survive (a single INSERT with both would violate ix_leads_email),
    # and it must be the freshest by entry_date — regardless of batch order,
    # so the newer row is listed FIRST here.
    newer = _lead("LEAD_B", "dup@x.com", name="New Name", entry=date(2026, 7, 14))
    older = _lead("LEAD_A", "dup@x.com", name="Old Name", entry=date(2026, 1, 12))
    inserts, updates = plan_lead_writes([newer, older], by_ext={}, id_by_email={})
    check("collapsed to one insert", len(inserts) == 1)
    check("no updates", updates == [])
    check("latest entry_date wins", inserts[0]["external_id"] == "LEAD_B"
          and inserts[0]["name"] == "New Name")


def test_in_batch_duplicate_emails_no_entry_date_last_wins() -> None:
    a = _lead("LEAD_A", "dup@x.com", name="First")
    b = _lead("LEAD_B", "dup@x.com", name="Second")
    inserts, updates = plan_lead_writes([a, b], by_ext={}, id_by_email={})
    check("collapsed to one insert (no dates)", len(inserts) == 1)
    check("batch order breaks the tie (last wins)",
          inserts[0]["external_id"] == "LEAD_B")


def test_external_id_match_keeps_full_update() -> None:
    # Pre-existing behavior: a row whose (source='wgr', external_id) is
    # already in CI updates every mapped column, email included.
    existing_id = uuid.uuid4()
    maps = [_lead("LEAD_KNOWN", "known@x.com", name="Known", status="closed")]
    inserts, updates = plan_lead_writes(
        maps, by_ext={"LEAD_KNOWN": existing_id}, id_by_email={},
    )
    check("ext match: no insert", inserts == [])
    check("ext match: one update", len(updates) == 1)
    target_id, values = updates[0]
    check("ext match: right target", target_id == existing_id)
    check("ext match: full values", values.get("email") == "known@x.com"
          and values.get("external_id") == "LEAD_KNOWN")


def test_in_batch_external_id_dedup_last_wins() -> None:
    # Pre-existing behavior preserved: same external_id twice → last wins.
    a = _lead("LEAD_A", "a@x.com", name="First")
    b = _lead("LEAD_A", "a@x.com", name="Second")
    inserts, _ = plan_lead_writes([a, b], by_ext={}, id_by_email={})
    check("ext dedup last wins", len(inserts) == 1 and inserts[0]["name"] == "Second")


def test_fresh_lead_inserts() -> None:
    maps = [_lead("LEAD_FRESH", "fresh@x.com", name="Fresh")]
    inserts, updates = plan_lead_writes(maps, by_ext={}, id_by_email={})
    check("fresh lead inserts", len(inserts) == 1 and updates == [])


def test_null_email_rows_never_collapse() -> None:
    # Plenty of WGR leads have no email; they must all insert independently.
    a = _lead("LEAD_A", None, name="NoMail A")
    b = _lead("LEAD_B", None, name="NoMail B")
    inserts, updates = plan_lead_writes([a, b], by_ext={}, id_by_email={})
    check("null emails both insert", len(inserts) == 2 and updates == [])


def main() -> int:
    for fn in sorted(k for k in globals() if k.startswith("test_")):
        print(fn)
        globals()[fn]()
    if _failures:
        print(f"\n{len(_failures)} FAILURE(S): {_failures}")
        return 1
    print("\nall ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
