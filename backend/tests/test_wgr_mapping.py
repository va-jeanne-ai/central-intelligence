"""Unit tests for WGR → CI mapping functions (app.services.wgr_sync.mapping).

Self-contained: runs with plain `python -m tests.test_wgr_mapping` (pytest is
not installed in this env). Each check is an assert; a final summary prints
pass/fail. Sample rows mirror the documented WGR schemas + data-quality notes
in docs/client-supabase-schema.md / greg-database-analysis.html.
"""

from __future__ import annotations

from app.services.wgr_sync import mapping as m

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def test_normalize_phone() -> None:
    check("phone bare-10 → +1", m.normalize_phone("2143365496") == "+12143365496")
    check("phone 11-with-1 → +1", m.normalize_phone("12143365496") == "+12143365496")
    check("phone keeps +", m.normalize_phone("+15612210606") == "+15612210606")
    check("phone strips formatting", m.normalize_phone("(561) 221-0606") == "+15612210606")
    check("phone empty → None", m.normalize_phone("") is None)
    check("phone None → None", m.normalize_phone(None) is None)
    check("phone garbage → None", m.normalize_phone("n/a") is None)


def test_test_call_filter() -> None:
    check("TEST_ id is test", m.is_test_call("TEST_T1_Alice") is True)
    check("real id not test", m.is_test_call("CALL_Nelson_20260526") is False)
    check("None not test", m.is_test_call(None) is False)
    # map_call returns None for test rows
    check("map_call filters test row", m.map_call({"call_id": "TEST_T1_Alice"}) is None)


def test_map_lead() -> None:
    row = {"lead_id": "LEAD_abc", "name": " Brian Shatto ", "email": "B@vip.com",
           "phone": "12143365496", "pipeline_stage": None, "notes": "  ",
           "entry_date": "2026-01-15"}
    out = m.map_lead(row)
    check("lead source=wgr", out["source"] == "wgr")
    check("lead external_id", out["external_id"] == "LEAD_abc")
    check("lead name trimmed", out["name"] == "Brian Shatto")
    check("lead phone normalized", out["phone"] == "+12143365496")
    check("lead blank notes → None", out["notes"] is None)
    check("lead null pipeline_stage → None status", out["status"] is None)
    check("lead entry_date passed through", out["entry_date"] == "2026-01-15")
    check("lead missing entry_date → None", m.map_lead({"lead_id": "L"})["entry_date"] is None)
    check("lead missing id → None", m.map_lead({"lead_id": ""}) is None)


def test_map_appointment_status() -> None:
    check("appt Showed→completed", m.map_appointment_status("Showed") == "completed")
    check("appt No Show→no_show", m.map_appointment_status("No Show") == "no_show")
    check("appt Cancelled→cancelled", m.map_appointment_status("Cancelled") == "cancelled")
    check("appt unknown passthrough lower", m.map_appointment_status("Weird") == "weird")
    out = m.map_appointment({"appointment_id": "APT_1", "outcome": "Showed",
                             "lead_id": "LEAD_abc", "call_number": "Discovery"})
    check("appt source=wgr", out["source"] == "wgr")
    check("appt carries wgr lead id", out["_wgr_lead_id"] == "LEAD_abc")
    check("appt type from call_number", out["appointment_type"] == "Discovery")


def test_map_insight() -> None:
    row = {"insight_id": "INS_1", "call_id": "CALL_x", "raw_quote": "I'm not clear",
           "the_real_problem": "decision paralysis", "frequency_score": None}
    out = m.map_insight(row)
    check("insight id", out["id"] == "INS_1")
    check("insight rich field mapped", out["the_real_problem"] == "decision paralysis")
    check("insight null freq → 0", out["frequency_score"] == 0)


def test_map_content_idea() -> None:
    out = m.map_content_idea({"content_id": "CONT_1", "hook_opening_line": "Hook",
                              "idea_score": 10, "status": None})
    check("content id", out["id"] == "CONT_1")
    check("content default status", out["status"] == "Idea")
    check("content idea_score", out["idea_score"] == 10)


def test_map_market_signal() -> None:
    out = m.map_market_signal({"signal_family": "Income & Money", "signal": "wants more",
                               "total_mentions": "5", "last_7_days": None})
    check("signal mentions int-coerced", out["total_mentions"] == 5)
    check("signal null window → 0", out["last_7_days"] == 0)
    check("signal empty → None", m.map_market_signal({"signal": "", "signal_family": ""}) is None)


def test_map_sales_rep() -> None:
    out = m.map_sales_rep({"rep_id": "REP_COLTON", "full_name": "Colton Lindsay",
                           "status": None, "capabilities": ["a", "b"], "business_id": 1})
    check("rep id", out["rep_id"] == "REP_COLTON")
    check("rep default status active", out["status"] == "active")
    check("rep capabilities list", out["capabilities"] == ["a", "b"])


def test_map_closed_sale_and_activity() -> None:
    cs = m.map_closed_sale({"sale_id": "SALE_1", "rep_id": None, "amount_collected": 10000})
    check("closed sale unattributed rep ok (None)", cs["rep_id"] is None)
    check("closed sale amount", cs["amount_collected"] == 10000)
    act = m.map_sales_activity({"activity_id": "ACTV_1", "rep_id": None,
                                "metadata": {"x": 1}, "body": "hi"})
    check("activity null rep ok", act["rep_id"] is None)
    check("activity metadata → activity_metadata", act["activity_metadata"] == {"x": 1})


def test_map_webinar_and_optin() -> None:
    w = m.map_webinar_engagement({"engagement_id": "ENG_1", "watched_live": True,
                                  "phone": "5612210606"})
    check("webinar watched_live bool", w["watched_live"] is True)
    check("webinar phone normalized", w["phone"] == "+15612210606")
    o = m.map_opt_in_event({"opt_in_event_id": "uuid-1", "lead_id": "LEAD_abc",
                            "source": "everwebinar"})
    check("optin source", o["source"] == "everwebinar")
    check("optin requires lead_id", m.map_opt_in_event({"opt_in_event_id": "x", "lead_id": ""}) is None)


def main() -> int:
    for fn in (
        test_normalize_phone, test_test_call_filter, test_map_lead,
        test_map_appointment_status, test_map_insight, test_map_content_idea,
        test_map_market_signal, test_map_sales_rep, test_map_closed_sale_and_activity,
        test_map_webinar_and_optin,
    ):
        print(f"\n{fn.__name__}:")
        fn()
    print(f"\n{'='*40}")
    if _failures:
        print(f"FAILED: {len(_failures)} check(s): {_failures}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
