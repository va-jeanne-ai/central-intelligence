"""Tests for the pure offer-catalog + revenue-rollup helpers
(app.repositories.offer_stats). Mirrors test_funnel_stats.py style: plain
dict fakes, no DB.

Contract under test:
- build_offer_catalog: merges the real WGR offer catalog with a per-offer
  sales rollup; appends an "Unattributed" row for revenue whose offer_id
  doesn't resolve to a known offer, so total revenue always reconciles.
- build_payment_level_rollup: groups offer_mappings rows into a
  deterministic (program, payment_level) ordering.
"""

from app.repositories.offer_stats import (
    UNATTRIBUTED_LABEL,
    build_offer_catalog,
    build_payment_level_rollup,
)


def _offer(offer_id, name="Offer", offer_type="Coaching", price=1000.0, status="Active"):
    return {
        "offer_id": offer_id, "name": name, "offer_type": offer_type,
        "description": None, "price": price, "status": status, "url": None,
    }


# --- build_offer_catalog ---


def test_build_offer_catalog_merges_sales_onto_known_offers():
    offers = [_offer("A", price=1000.0), _offer("B", price=2000.0)]
    sales_by_offer = {"A": (3, 3000.0), "B": (1, 2000.0)}
    catalog = build_offer_catalog(offers, sales_by_offer)
    by_id = {row["offer_id"]: row for row in catalog}
    assert by_id["A"]["sales_count"] == 3
    assert by_id["A"]["revenue"] == 3000.0
    assert by_id["B"]["sales_count"] == 1
    assert by_id["B"]["revenue"] == 2000.0


def test_build_offer_catalog_zero_defaults_for_offers_with_no_sales():
    offers = [_offer("A")]
    catalog = build_offer_catalog(offers, {})
    assert catalog[0]["sales_count"] == 0
    assert catalog[0]["revenue"] == 0.0


def test_build_offer_catalog_custom_priced_offer_price_is_none():
    offers = [_offer("A", price=None)]
    catalog = build_offer_catalog(offers, {})
    assert catalog[0]["price"] is None


def test_build_offer_catalog_appends_unattributed_row_for_null_offer_id():
    offers = [_offer("A")]
    sales_by_offer = {"A": (1, 1000.0), None: (5, 500.0)}
    catalog = build_offer_catalog(offers, sales_by_offer)
    unattributed = [r for r in catalog if r["name"] == UNATTRIBUTED_LABEL]
    assert len(unattributed) == 1
    assert unattributed[0]["sales_count"] == 5
    assert unattributed[0]["revenue"] == 500.0
    assert unattributed[0]["offer_id"] is None


def test_build_offer_catalog_appends_unattributed_row_for_unknown_offer_id():
    """A sale referencing an offer_id that isn't in the catalog (e.g. stale
    WGR data) must still count toward revenue, folded into Unattributed —
    never silently dropped."""
    offers = [_offer("A")]
    sales_by_offer = {"A": (1, 1000.0), "GHOST_OFFER": (2, 999.0)}
    catalog = build_offer_catalog(offers, sales_by_offer)
    unattributed = [r for r in catalog if r["name"] == UNATTRIBUTED_LABEL]
    assert len(unattributed) == 1
    assert unattributed[0]["sales_count"] == 2
    assert unattributed[0]["revenue"] == 999.0


def test_build_offer_catalog_no_unattributed_row_when_fully_attributed():
    offers = [_offer("A"), _offer("B")]
    sales_by_offer = {"A": (1, 1000.0), "B": (2, 2000.0)}
    catalog = build_offer_catalog(offers, sales_by_offer)
    assert all(r["name"] != UNATTRIBUTED_LABEL for r in catalog)


def test_build_offer_catalog_revenue_reconciles_with_total():
    """Sum of every row's revenue (known offers + Unattributed) must equal
    the total across all sales_by_offer entries — the reconciliation
    contract the route/proof depends on."""
    offers = [_offer("A"), _offer("B")]
    sales_by_offer = {
        "A": (41, 320750.0), "B": (11, 36500.0),
        None: (10, 5000.0), "UNKNOWN": (1, 100.0),
    }
    catalog = build_offer_catalog(offers, sales_by_offer)
    total_input = sum(rev for _, rev in sales_by_offer.values())
    total_output = sum(row["revenue"] for row in catalog)
    assert total_output == round(total_input, 2)


def test_build_offer_catalog_preserves_input_order_for_known_offers():
    offers = [_offer("Z"), _offer("A"), _offer("M")]
    catalog = build_offer_catalog(offers, {})
    assert [row["offer_id"] for row in catalog] == ["Z", "A", "M"]


# --- build_payment_level_rollup ---


def _mapping(program, payment_level, offer_id, amount=1000.0, revenue=1000.0):
    return {
        "program": program, "payment_level": payment_level, "offer_id": offer_id,
        "amount_collected": amount, "revenue_earned": revenue,
    }


def test_build_payment_level_rollup_groups_and_sorts_deterministically():
    mappings = [
        _mapping("mastery", "pif", "OFFER_AIM_PIF"),
        _mapping("accelerator", "3 pay", "OFFER_AIA_3PAY"),
        _mapping("accelerator", "2 pay", "OFFER_AIA_2PAY"),
    ]
    rows = build_payment_level_rollup(mappings)
    assert [(r["program"], r["payment_level"]) for r in rows] == [
        ("accelerator", "2 pay"),
        ("accelerator", "3 pay"),
        ("mastery", "pif"),
    ]


def test_build_payment_level_rollup_preserves_all_rows_including_duplicates_by_offer():
    """Two payment levels can point at the same offer_id (e.g. 'monthly' and
    '6 pay' both -> OFFER_AIA_MONTHLY) — both must survive independently."""
    mappings = [
        _mapping("accelerator", "monthly", "OFFER_AIA_MONTHLY"),
        _mapping("accelerator", "6 pay", "OFFER_AIA_MONTHLY"),
    ]
    rows = build_payment_level_rollup(mappings)
    assert len(rows) == 2
    assert {r["payment_level"] for r in rows} == {"monthly", "6 pay"}


def test_build_payment_level_rollup_rounds_amounts():
    mappings = [_mapping("p", "l", "O", amount=1000.005, revenue=2000.004)]
    rows = build_payment_level_rollup(mappings)
    assert rows[0]["amount_collected"] == round(1000.005, 2)
    assert rows[0]["revenue_earned"] == round(2000.004, 2)
