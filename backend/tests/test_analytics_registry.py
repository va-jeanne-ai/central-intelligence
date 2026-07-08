"""Unit tests for the declarative metric catalog (app.analytics.registry).

Self-contained: runs with plain `python -m tests.test_analytics_registry` (pytest
is not installed in this env). Covers the catalog's own contract — every metric
must be well-formed and unique — not the SQL correctness against a live schema
(that needs Postgres and is out of scope here).
"""

from __future__ import annotations

from app.analytics.registry import REGISTRY, Metric, all_metrics, get_metric, metrics_for_area

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


_VALID_UNITS = {"ratio", "score", "count", "currency"}


def test_registry_is_non_empty() -> None:
    check("registry has metrics", len(REGISTRY) > 0)


def test_every_metric_has_required_fields() -> None:
    for m in REGISTRY:
        check(f"{m.key}: key is non-empty str", isinstance(m.key, str) and bool(m.key.strip()))
        check(f"{m.key}: area is non-empty str", isinstance(m.area, str) and bool(m.area.strip()))
        check(f"{m.key}: label is non-empty str", isinstance(m.label, str) and bool(m.label.strip()))
        check(f"{m.key}: unit is valid", m.unit in _VALID_UNITS)
        check(f"{m.key}: higher_is_better is bool", isinstance(m.higher_is_better, bool))
        check(f"{m.key}: sql is set", m.sql is not None)


def test_every_metric_sql_binds_since() -> None:
    # The SQL contract requires a single :since bind param (module docstring).
    for m in REGISTRY:
        sql_text = str(m.sql)
        check(f"{m.key}: sql references :since", ":since" in sql_text)


def test_every_metric_sql_selects_value_and_sample_size() -> None:
    for m in REGISTRY:
        sql_text = str(m.sql).lower()
        check(f"{m.key}: sql aliases value", "as value" in sql_text or " value" in sql_text)
        check(f"{m.key}: sql aliases sample_size", "sample_size" in sql_text)


def test_keys_are_unique() -> None:
    keys = [m.key] if False else [m.key for m in REGISTRY]
    check("keys unique", len(keys) == len(set(keys)))


def test_key_matches_area_prefix() -> None:
    # Convention observed across the catalog: key is "<area>.<name>".
    for m in REGISTRY:
        check(f"{m.key}: key prefixed by its area", m.key.startswith(f"{m.area}."))


def test_all_metrics_returns_a_copy() -> None:
    a = all_metrics()
    a.append(
        Metric(
            key="test.injected",
            area="test",
            label="Injected",
            unit="count",
            higher_is_better=True,
            sql=REGISTRY[0].sql,
        )
    )
    check("mutating all_metrics() result doesn't affect REGISTRY", len(REGISTRY) != len(a))
    check("REGISTRY unaffected", get_metric("test.injected") is None)


def test_metrics_for_area_filters_correctly() -> None:
    sales = metrics_for_area("sales")
    check("metrics_for_area returns only that area", all(m.area == "sales" for m in sales))
    check("metrics_for_area matches manual filter", len(sales) == len([m for m in REGISTRY if m.area == "sales"]))
    check("unknown area returns empty", metrics_for_area("nonexistent_area_xyz") == [])


def test_get_metric_lookup() -> None:
    first = REGISTRY[0]
    check("get_metric finds a real key", get_metric(first.key) is first)
    check("get_metric returns None for unknown key", get_metric("nonexistent.metric.key") is None)


def test_has_asof_property() -> None:
    # has_asof should be True only when ALL four asof_* fields are populated.
    for m in REGISTRY:
        all_present = bool(m.asof_table and m.asof_date_col and m.asof_value_expr and m.asof_sample_expr)
        check(f"{m.key}: has_asof matches field completeness", m.has_asof == all_present)

    partial = Metric(
        key="test.partial_asof",
        area="test",
        label="Partial",
        unit="count",
        higher_is_better=True,
        sql=REGISTRY[0].sql,
        asof_table="some_table",
        asof_date_col="created_at",
        # asof_value_expr / asof_sample_expr intentionally missing
    )
    check("partial asof fields → has_asof False", partial.has_asof is False)


def main() -> int:
    for fn in (
        test_registry_is_non_empty,
        test_every_metric_has_required_fields,
        test_every_metric_sql_binds_since,
        test_every_metric_sql_selects_value_and_sample_size,
        test_keys_are_unique,
        test_key_matches_area_prefix,
        test_all_metrics_returns_a_copy,
        test_metrics_for_area_filters_correctly,
        test_get_metric_lookup,
        test_has_asof_property,
    ):
        print(fn.__name__)
        fn()
    if _failures:
        print(f"\n{len(_failures)} FAILED: {_failures}")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
