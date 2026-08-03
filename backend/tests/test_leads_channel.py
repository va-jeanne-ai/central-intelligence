"""Tests for channel_for_lead + summarize_channels (pure helpers built on the
attribution Resolver). Mirrors test_attribution_resolver.py style: SimpleNamespace
fakes, no DB, no app import beyond app.services.attribution.

Contract under test:
- channel_for_lead: row-level first-touch preferred, falls back to last-touch
  only when ALL first-touch fields are null; never mixes first/last fields.
- summarize_channels: resolves distinct (first*3, last*3, count) combos via
  channel_for_lead semantics, merges counts per bucket, caps unmapped
  cardinality at unmapped_top_n by descending count, with excess folded into
  "other unmapped". All-null -> "No attribution" (reportable=False).
  reportable=False resolutions -> "Non-marketing". Sum of output counts must
  equal sum of input counts.
"""
from types import SimpleNamespace

from app.services.attribution import build_resolver, channel_for_lead, summarize_channels


def _row(id, src, med, cont, channel, platform=None, reportable=True):
    return SimpleNamespace(
        id=id, observed_source=src, observed_medium=med, observed_content=cont,
        canonical_channel=channel, platform=platform,
        include_in_channel_reporting=reportable,
    )


ROWS = [
    _row(1, "ig", None, None, "instagram_organic"),
    _row(2, "ig", "paid", None, "meta_paid", platform="ig"),
    _row(4, None, "email", None, "email"),
    _row(5, "manual", None, None, "manual_entry", reportable=False),
]


def _lead(sf=None, mf=None, cf=None, sl=None, ml=None, cl=None):
    return SimpleNamespace(
        utm_source_first=sf, utm_medium_first=mf, utm_content_first=cf,
        utm_source_last=sl, utm_medium_last=ml, utm_content_last=cl,
    )


def _combo(sf=None, mf=None, cf=None, sl=None, ml=None, cl=None, count=1):
    return (sf, mf, cf, sl, ml, cl, count)


# --- channel_for_lead ---


def test_channel_for_lead_prefers_first_touch_when_present():
    r = build_resolver(ROWS)
    lead = _lead(sf="ig", mf="paid", sl="manual")
    res = channel_for_lead(r, lead)
    assert res.channel == "meta_paid"


def test_channel_for_lead_falls_back_to_last_touch_when_first_all_null():
    r = build_resolver(ROWS)
    lead = _lead(sl="ig", ml="paid")
    res = channel_for_lead(r, lead)
    assert res.channel == "meta_paid"


def test_channel_for_lead_returns_none_when_everything_null():
    r = build_resolver(ROWS)
    lead = _lead()
    res = channel_for_lead(r, lead)
    assert res.channel is None


def test_channel_for_lead_never_mixes_first_and_last_fields():
    # utm_source_first="ig" makes first-touch "present", so resolution must
    # be computed strictly on (ig, None, None) from the first-touch triple —
    # never combined with utm_medium_last="paid".
    r = build_resolver(ROWS)
    lead = _lead(sf="ig", ml="paid")
    res = channel_for_lead(r, lead)
    assert res.channel == "instagram_organic"


# --- summarize_channels ---


def test_summarize_channels_merges_combos_into_same_channel_bucket():
    r = build_resolver(ROWS)
    combos = [
        _combo(sf="ig", mf="paid", count=3),
        _combo(sl="ig", ml="paid", count=5),  # first-touch all null -> falls back
    ]
    result = summarize_channels(combos, r)
    bucket = {row["channel"]: row for row in result}
    assert bucket["meta_paid"]["count"] == 8


def test_summarize_channels_routes_no_attribution_non_marketing_and_caps_unmapped():
    r = build_resolver(ROWS)
    combos = [
        _combo(count=2),  # all-null -> No attribution
        _combo(sf="manual", count=4),  # reportable=False -> Non-marketing
    ]
    # 10 distinct unmapped combos with descending counts so top_n=8 caps two.
    for i in range(10):
        combos.append(_combo(sf=f"src{i}", mf="mystery", count=10 - i))

    result = summarize_channels(combos, r, unmapped_top_n=8)
    bucket = {row["channel"]: row for row in result}

    assert bucket["No attribution"]["count"] == 2
    assert bucket["No attribution"]["reportable"] is False
    assert bucket["Non-marketing"]["count"] == 4

    unmapped_channels = [c for c in bucket if c.startswith("unmapped:")]
    assert len(unmapped_channels) == 8
    # top 8 by count are counts 10..3; remaining two (2 + 1) fold into other unmapped
    assert bucket["other unmapped"]["count"] == 2 + 1


def test_summarize_channels_output_counts_sum_to_input_counts():
    r = build_resolver(ROWS)
    combos = [
        _combo(sf="ig", mf="paid", count=3),
        _combo(count=2),
        _combo(sf="manual", count=4),
        _combo(sf="unknownsrc", mf="unknownmed", count=7),
    ]
    result = summarize_channels(combos, r)
    assert sum(row["count"] for row in result) == sum(c[-1] for c in combos)
