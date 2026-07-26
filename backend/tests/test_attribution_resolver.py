"""Resolver contract tests (Greg's taxonomy contract, migration 20260724_000000):
case-insensitive triple matching; NULL observed_* = wildcard; most-specific
wins (concrete-field count, 3 > 2 > 1); ties by lowest id; unmapped surfaces
loudly with sanitized labels; non-reportable rules resolve but flag False."""
from types import SimpleNamespace

from app.services.attribution import build_resolver


def _row(id, src, med, cont, channel, platform=None, reportable=True):
    return SimpleNamespace(
        id=id, observed_source=src, observed_medium=med, observed_content=cont,
        canonical_channel=channel, platform=platform,
        include_in_channel_reporting=reportable,
    )


ROWS = [
    _row(1, "ig", None, None, "instagram_organic"),
    _row(2, "ig", "paid", None, "meta_paid", platform="ig"),
    _row(3, "ig", "paid", "reel-14", "meta_paid_reels", platform="ig"),
    _row(4, None, "email", None, "email"),
    _row(5, "manual", None, None, "manual_entry", reportable=False),
    _row(6, "IG", "STORIES", None, "instagram_stories"),  # duplicate-ish casing
]


def test_most_specific_match_wins():
    r = build_resolver(ROWS)
    assert r.resolve("ig", "paid", "reel-14").channel == "meta_paid_reels"
    assert r.resolve("ig", "paid", "other").channel == "meta_paid"
    assert r.resolve("ig", "organic", None).channel == "instagram_organic"


def test_case_insensitive_matching():
    r = build_resolver(ROWS)
    assert r.resolve("IG", "Paid", None).channel == "meta_paid"
    assert r.resolve("ig", "stories", None).channel == "instagram_stories"


def test_wildcard_medium_matches_any_source():
    r = build_resolver(ROWS)
    assert r.resolve("activecampaign", "email", None).channel == "email"


def test_unmapped_surfaces_loudly():
    r = build_resolver(ROWS)
    res = r.resolve("tiktok", "bio", None)
    assert res.channel == "unmapped:tiktok/bio"
    assert res.reportable is True  # unmapped is still a marketing touch


def test_no_utms_resolves_to_none():
    r = build_resolver(ROWS)
    assert r.resolve(None, None, None).channel is None
    assert r.resolve("", "", "").channel is None


def test_non_reportable_row_flags_reportable_false():
    r = build_resolver(ROWS)
    res = r.resolve("manual", None, None)
    assert res.channel == "manual_entry"
    assert res.reportable is False


def test_tie_broken_by_lowest_id():
    rows = ROWS + [_row(0, "ig", None, None, "SHOULD_WIN")]
    assert build_resolver(rows).resolve("ig", "organic", None).channel == "SHOULD_WIN"


def test_resolver_contract_excludes_campaign():
    # r7: campaign is mirrored data, NOT part of resolution — encode the
    # contract in the API surface so a downstream implementer can't assume it.
    import inspect
    from app.services.attribution import Resolver
    assert list(inspect.signature(Resolver.resolve).parameters) == [
        "self", "source", "medium", "content"
    ]


def test_content_only_input_gets_placeholder_label():
    # Non-empty content with null source/medium is not "all empty"; the
    # unmapped label uses '-' placeholders, never "unmapped:/".
    r = build_resolver(ROWS)
    assert r.resolve(None, None, "mystery-clip").channel == "unmapped:-/-"


def test_concrete_field_count_defines_specificity():
    # Audit r3 #9: specificity is EXACTLY the count of concrete fields.
    # A content-only wildcard rule (1 concrete) loses to source+medium (2).
    rows = [
        _row(1, None, None, "reel-14", "content_only"),
        _row(2, "ig", "paid", None, "source_medium"),
    ]
    assert build_resolver(rows).resolve("ig", "paid", "reel-14").channel == "source_medium"


def test_unmapped_label_is_sanitized():
    # r3/r5 #13: labels embed raw UTMs — cap length, strip non-printables and
    # spreadsheet-formula lead characters.
    r = build_resolver([])
    hostile = "=cmd|' /C calc'!A0" + "\x07" + "x" * 200
    res = r.resolve(hostile, "ok", None)
    assert res.channel.startswith("unmapped:")
    label_src = res.channel.split(":", 1)[1].split("/", 1)[0]
    assert not label_src.startswith("=")
    assert len(label_src) <= 64
    assert "\x07" not in label_src


def test_resolver_coerces_non_string_inputs():
    # r6: never crash on a stray non-string value from a mirrored column.
    r = build_resolver([_row(1, "123", None, None, "numeric_source")])
    assert r.resolve(123, None, None).channel == "numeric_source"
