"""Read-time canonical-channel resolution via attribution_taxonomy.

Implements Greg's taxonomy contract (WGR migration 20260724_000000): raw UTMs
are never rewritten; matching is case-insensitive; NULL observed_* is a
wildcard; the MOST SPECIFIC matching row wins (specificity = count of
concrete fields, so content+source+medium beats source+medium beats
source-only), ties broken by lowest id; no match surfaces loudly as
``unmapped:<source>/<medium>``; include_in_channel_reporting=false rows are
honest origins but not marketing touches.

``utm_campaign`` is intentionally NOT part of this contract — Greg's taxonomy
has no observed_campaign column; campaign is mirrored data, never matched on
(the resolve() signature enforces this).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import NamedTuple, Optional, Sequence


class Resolution(NamedTuple):
    channel: Optional[str]
    platform: Optional[str]
    reportable: bool


def _norm(v) -> Optional[str]:
    # Defensive: mirrored columns are text, but never crash on a stray
    # non-string — coerce, trim, casefold to lower.
    v = str(v).strip().lower() if v is not None else ""
    return v or None


def _label_part(v: Optional[str]) -> str:
    """Unmapped labels embed raw UTM values (Greg's surface-loudly contract).
    Keep them display/CSV-safe: printable chars only, length-capped, no
    spreadsheet-formula lead characters."""
    v = "".join(ch for ch in (v or "")[:64] if ch.isprintable())
    return v.lstrip("=+@\t") or "-"


class Resolver:
    def __init__(self, rows: Sequence) -> None:
        # Precompute normalized match keys once; row order irrelevant.
        self._rows = [
            (
                _norm(r.observed_source), _norm(r.observed_medium),
                _norm(r.observed_content),
                # specificity = how many concrete (non-wildcard) fields
                sum(x is not None for x in (
                    _norm(r.observed_source), _norm(r.observed_medium),
                    _norm(r.observed_content),
                )),
                r,
            )
            for r in rows
        ]

    def resolve(self, source, medium, content) -> Resolution:
        s, m, c = _norm(source), _norm(medium), _norm(content)
        if s is None and m is None and c is None:
            return Resolution(None, None, False)
        best = None  # (neg_specificity, id) minimized
        for rs, rm, rc, spec, row in self._rows:
            if rs is not None and rs != s:
                continue
            if rm is not None and rm != m:
                continue
            if rc is not None and rc != c:
                continue
            key = (-spec, row.id)
            if best is None or key < best[0]:
                best = (key, row)
        if best is None:
            return Resolution(
                f"unmapped:{_label_part(s)}/{_label_part(m)}", None, True
            )
        row = best[1]
        return Resolution(
            row.canonical_channel, row.platform,
            bool(row.include_in_channel_reporting),
        )


def build_resolver(rows: Sequence) -> Resolver:
    return Resolver(rows)


def channel_for_lead(resolver: Resolver, lead) -> Resolution:
    """Row-level first-touch preferred; fall back to last-touch (Greg's grouping rule).
    Never mixes first/last fields. `lead` exposes utm_*_first / utm_*_last attributes."""
    if lead.utm_source_first or lead.utm_medium_first or lead.utm_content_first:
        return resolver.resolve(
            lead.utm_source_first, lead.utm_medium_first, lead.utm_content_first
        )
    return resolver.resolve(
        lead.utm_source_last, lead.utm_medium_last, lead.utm_content_last
    )


def bucket_channel_combos(combos, resolver: Resolver, *, unmapped_top_n: int = 8):
    """Core bucketing shared by the breakdown and the server-side channel filter.

    combos: iterable of (utm_source_first, utm_medium_first, utm_content_first,
    utm_source_last, utm_medium_last, utm_content_last, count). Resolves each
    combo via channel_for_lead semantics and applies the bucket rules:
    all-null -> 'No attribution'; reportable=False -> 'Non-marketing';
    'unmapped:*' capped to unmapped_top_n by descending count, remainder folded
    into 'other unmapped'.

    Returns (mapping, buckets):
    - mapping: {(sf, mf, cf, sl, ml, cl): final bucket label} for every input
      combo — post-rollup, so an overflow dialect maps to 'other unmapped'.
      This is what lets a route translate a bucket label back into the exact
      UTM combos to filter on in SQL.
    - buckets: list[dict(channel, platform, reportable, count)] — the same
      aggregate shape summarize_channels has always returned.
    """
    buckets: dict[str, dict] = {}
    prelim: dict[tuple, str] = {}

    for sf, mf, cf, sl, ml, cl, count in combos:
        lead = SimpleNamespace(
            utm_source_first=sf, utm_medium_first=mf, utm_content_first=cf,
            utm_source_last=sl, utm_medium_last=ml, utm_content_last=cl,
        )
        res = channel_for_lead(resolver, lead)

        if res.channel is None:
            channel, platform, reportable = "No attribution", None, False
        elif not res.reportable:
            channel, platform, reportable = "Non-marketing", None, False
        else:
            channel, platform, reportable = res.channel, res.platform, res.reportable

        prelim[(sf, mf, cf, sl, ml, cl)] = channel
        if channel in buckets:
            buckets[channel]["count"] += count
        else:
            buckets[channel] = {
                "channel": channel, "platform": platform,
                "reportable": reportable, "count": count,
            }

    overflow: set[str] = set()
    unmapped_keys = [k for k in buckets if k.startswith("unmapped:")]
    if len(unmapped_keys) > unmapped_top_n:
        unmapped_keys.sort(key=lambda k: buckets[k]["count"], reverse=True)
        overflow = set(unmapped_keys[unmapped_top_n:])
        overflow_count = sum(buckets[k]["count"] for k in overflow)
        for k in overflow:
            del buckets[k]
        if "other unmapped" in buckets:
            buckets["other unmapped"]["count"] += overflow_count
        else:
            buckets["other unmapped"] = {
                "channel": "other unmapped", "platform": None,
                "reportable": True, "count": overflow_count,
            }

    mapping = {
        key: ("other unmapped" if label in overflow else label)
        for key, label in prelim.items()
    }
    return mapping, list(buckets.values())


def summarize_channels(combos, resolver: Resolver, *, unmapped_top_n: int = 8):
    """Aggregate view of bucket_channel_combos — see its docstring for the
    bucket rules. Kept as the breakdown's entry point; behavior unchanged."""
    _, buckets = bucket_channel_combos(combos, resolver, unmapped_top_n=unmapped_top_n)
    return buckets
