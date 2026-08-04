"""Pure offer-catalog + revenue-rollup helpers, built on the real WGR
mirrors (``wgr_offers`` / ``wgr_offer_mappings``) and ``closed_sales``.

CI's own ``offers`` table (app-CRUD, 18 rows of test data — "This is a new
offer", "just checking") never got the real catalog synced into it. The
real catalog lives in ``wgr_offers`` (11 rows) / ``wgr_offer_mappings`` (15
rows); ``closed_sales.offer_id`` references WGR offer ids, so revenue per
offer is a join away.

These helpers are pure (no DB) so they're unit-testable against fake rows —
mirrors ``test_leads_channel.py``/``test_funnel_stats.py``'s style. The
route layer does the DB reads (``wgr_offers``, ``wgr_offer_mappings``,
``closed_sales`` grouped by ``offer_id``) and hands plain dicts to these
functions.
"""

from __future__ import annotations

from typing import Any, Sequence

UNATTRIBUTED_LABEL = "Unattributed"


def _float(value: object) -> float:
    """Return value as float, falling back to 0.0 for None or non-numeric values."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def build_offer_catalog(
    offers: Sequence[Any],
    sales_by_offer: dict[str | None, tuple[int, float]],
) -> list[dict]:
    """Merge the real offer catalog with per-offer sales rollups.

    ``offers``: rows/objects exposing offer_id/name/offer_type/description/
    price/status/url (as returned by a ``wgr_offers`` read — attribute or
    mapping access via ``getattr``-style dicts is fine, this only reads via
    ``[]`` so pass dicts or RowMappings).

    ``sales_by_offer``: dict of ``offer_id -> (sales_count, revenue)``, one
    entry per distinct ``closed_sales.offer_id`` value (including a ``None``
    key for sales whose offer_id didn't resolve to a known offer — the
    caller pre-aggregates this from ``closed_sales`` GROUP BY offer_id).

    Returns one dict per real offer: {offer_id, name, offer_type, description,
    price, status, url, sales_count, revenue} — sales_count/revenue default
    to 0/0.0 for offers with no closed sales. Order is preserved from the
    input ``offers`` sequence (the route controls sort — e.g. by name or by
    revenue).

    An **"Unattributed" row** is appended when ``sales_by_offer`` contains
    revenue under a key that doesn't match any known offer_id (including the
    explicit ``None`` key for sales with no/unknown offer_id) — so the sum
    of every row's revenue always equals total closed-sales revenue,
    regardless of catalog coverage gaps.
    """
    known_ids = {o["offer_id"] for o in offers if o.get("offer_id")}
    catalog: list[dict] = []
    for o in offers:
        oid = o.get("offer_id")
        sales_count, revenue = sales_by_offer.get(oid, (0, 0.0))
        catalog.append(
            {
                "offer_id": oid,
                "name": o.get("name"),
                "offer_type": o.get("offer_type"),
                "description": o.get("description"),
                "price": _float(o.get("price")) if o.get("price") is not None else None,
                "status": o.get("status"),
                "url": o.get("url"),
                "sales_count": _int(sales_count),
                "revenue": round(_float(revenue), 2),
            }
        )

    unattributed_count = 0
    unattributed_revenue = 0.0
    for key, (count, revenue) in sales_by_offer.items():
        if key not in known_ids:
            unattributed_count += _int(count)
            unattributed_revenue += _float(revenue)

    if unattributed_count > 0 or unattributed_revenue != 0.0:
        catalog.append(
            {
                "offer_id": None,
                "name": UNATTRIBUTED_LABEL,
                "offer_type": None,
                "description": None,
                "price": None,
                "status": None,
                "url": None,
                "sales_count": unattributed_count,
                "revenue": round(unattributed_revenue, 2),
            }
        )
    return catalog


def build_payment_level_rollup(mappings: Sequence[Any]) -> list[dict]:
    """Group ``wgr_offer_mappings`` rows by program, one row per
    (program, payment_level) with its amount_collected/revenue_earned and
    the offer_id it points at.

    ``mappings``: rows/objects exposing program/payment_level/offer_id/
    amount_collected/revenue_earned (dict-style ``[]`` access).

    Returns a list ordered by program name ascending, then payment_level
    ascending (deterministic — no reliance on read order): [{program,
    payment_level, offer_id, amount_collected, revenue_earned}, ...].
    """
    rows = [
        {
            "program": m.get("program"),
            "payment_level": m.get("payment_level"),
            "offer_id": m.get("offer_id"),
            "amount_collected": round(_float(m.get("amount_collected")), 2),
            "revenue_earned": round(_float(m.get("revenue_earned")), 2),
        }
        for m in mappings
    ]
    rows.sort(key=lambda r: (r["program"] or "", r["payment_level"] or ""))
    return rows


__all__ = [
    "UNATTRIBUTED_LABEL",
    "build_offer_catalog",
    "build_payment_level_rollup",
]
