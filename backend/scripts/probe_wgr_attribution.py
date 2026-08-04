"""Read-only probe: does WGR have the attribution-era columns/tables, are all
columns the mappers consume present, and are the tables populated? Run before
building the attribution sync (plan 2026-07-26).

Per table: verify readability (SELECT * LIMIT 1), diff actual columns against
every column the sync mappers will read (missing ones are named), then print
counts. A pass = readable + all mapped columns present. Type compatibility is
NOT proven here — mappers pass values through; the backfill run is the type
gate.

Usage: cd backend && PYTHONPATH=. .venv/bin/python -m scripts.probe_wgr_attribution
Exits nonzero on any failed gate so scripted executors cannot proceed past it.
"""
from app.services import wgr_client

# table → (columns the mappers consume, count SQL)
CHECKS: dict[str, tuple[set[str], str]] = {
    "leads": (
        {"lead_id", "ghl_contact_id",
         "utm_source_first", "utm_medium_first", "utm_campaign_first", "utm_content_first",
         "utm_source_last", "utm_medium_last", "utm_campaign_last", "utm_content_last"},
        "SELECT count(*) AS total, count(utm_source_first) AS with_first, "
        "count(utm_source_last) AS with_last FROM leads",
    ),
    "attribution_taxonomy": (
        {"id", "observed_source", "observed_medium", "observed_content",
         "canonical_channel", "platform", "include_in_channel_reporting",
         "notes", "created_at", "updated_at"},
        "SELECT count(*) AS n, count(*) FILTER (WHERE include_in_channel_reporting) "
        "AS reportable FROM attribution_taxonomy",
    ),
    "lead_engagements": (
        {"engagement_id", "lead_id", "ghl_contact_id", "engagement_type",
         "engagement_date", "utm_source", "utm_medium", "utm_campaign",
         "utm_content", "source_type", "email_campaign_id", "email_id",
         "offer_id", "page_url", "notes", "created_at"},
        "SELECT count(*) AS n, min(engagement_date) AS oldest, "
        "max(engagement_date) AS newest FROM lead_engagements",
    ),
    "meta_campaigns": (
        {"campaign_id", "meta_campaign_id", "name", "campaign_type", "objective",
         "status", "daily_budget", "lifetime_budget", "targeting_type",
         "targeting_notes", "start_date", "end_date", "notes", "created_at",
         "updated_at"},
        "SELECT count(*) AS n FROM meta_campaigns",
    ),
    "meta_ads": (
        {"ad_id", "campaign_id", "meta_ad_id", "name", "ad_format", "status",
         "hook_text", "hook_type", "script_body", "script_cta", "framework_used",
         "offer_id", "target_audience", "calendar_entry_id", "parent_ad_id",
         "iteration_notes", "result", "launched_date", "kill_date",
         "kill_reason", "notes", "created_at", "updated_at"},
        "SELECT count(*) AS n FROM meta_ads",
    ),
    "meta_ad_performance": (
        {"perf_id", "ad_id", "snapshot_date", "snapshot_type", "amount_spent",
         "impressions", "reach", "leads", "cost_per_lead", "booked_calls",
         "cost_per_booked_call", "link_clicks", "cost_per_link_click",
         "hook_rate", "hold_rate", "ctr", "cpm", "frequency", "kpi_status",
         "metric_notes", "action_taken", "created_at"},
        "SELECT count(*) AS n, min(snapshot_date) AS oldest, "
        "max(snapshot_date) AS newest FROM meta_ad_performance",
    ),
}


def main() -> None:
    # Verify the connection identity at runtime — the ci_reader boundary must
    # be enforced, not assumed. A config mistake (legacy postgres DSN) fails
    # the gate here before any pull.
    ident = list(wgr_client.query(
        "SELECT current_user AS role, "
        "current_setting('transaction_read_only') AS read_only"
    ))[0]
    print(f"connection identity: {ident}")
    if ident["role"] != "ci_reader":
        print("GATE FAILED: not connected as ci_reader — fix CLIENT_DATABASE_URL "
              "(Task 0) before running any pull.")
        raise SystemExit(1)  # scripted executors must not sail past the gate
    failed = []
    for table, (expected_cols, count_sql) in CHECKS.items():
        try:
            sample = list(wgr_client.query(f"SELECT * FROM {table} LIMIT 1"))
            if sample:
                actual = set(sample[0].keys())
            else:
                actual = {
                    r["column_name"] for r in wgr_client.query(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=%s", (table,),
                    )
                }
            missing = expected_cols - actual
            if missing:
                failed.append(table)
                print(f"{table}: MISSING COLUMNS {sorted(missing)}")
            counts = list(wgr_client.query(count_sql))
            print(f"{table}: OK cols={len(actual)} {counts[0]}")
        except Exception as exc:  # absent table / denied permission / bad query
            failed.append(table)
            print(f"{table}: FAILED — {exc}")
    if failed:
        print(f"\nGATE: failures in {failed} — see plan Task 1 Step 2 for go/no-go rules.")
        raise SystemExit(1)  # nonzero exit so automation can't proceed past a failed gate


if __name__ == "__main__":
    main()
