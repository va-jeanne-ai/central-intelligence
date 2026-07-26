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
