"""Unit tests for the pure LLM-output validation in app.analytics.overall_insight.

Self-contained: runs with plain `python -m tests.test_overall_insight_coerce`
(pytest is not installed in this env). Covers only ``_coerce`` — the
deterministic normalize/validate step applied to parsed LLM JSON. The LLM call
itself (``_synthesize``) and DB-coupled gathering/persistence are out of scope
(no live Postgres, no real Anthropic calls).
"""

from __future__ import annotations

from app.analytics.overall_insight import _VALID_VERDICTS, _coerce

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def test_valid_input_passes_through() -> None:
    parsed = {
        "health_verdict": "healthy",
        "narrative": "  Things look good.  ",
        "key_shifts": ["Sales up", "  Marketing flat  ", ""],
    }
    out = _coerce(parsed)
    check("verdict kept", out["health_verdict"] == "healthy")
    check("narrative trimmed", out["narrative"] == "Things look good.")
    check("shifts trimmed and empties dropped", out["key_shifts"] == ["Sales up", "Marketing flat"])


def test_verdict_case_insensitive() -> None:
    out = _coerce({"health_verdict": "AT_RISK", "narrative": "x", "key_shifts": []})
    check("verdict lowercased", out["health_verdict"] == "at_risk")


def test_invalid_verdict_defaults_to_watch() -> None:
    out = _coerce({"health_verdict": "on_fire", "narrative": "x", "key_shifts": []})
    check("invalid verdict → watch", out["health_verdict"] == "watch")


def test_missing_verdict_defaults_to_watch() -> None:
    out = _coerce({"narrative": "x", "key_shifts": []})
    check("missing verdict → watch", out["health_verdict"] == "watch")


def test_all_valid_verdicts_accepted() -> None:
    for v in _VALID_VERDICTS:
        out = _coerce({"health_verdict": v, "narrative": "x", "key_shifts": []})
        check(f"verdict '{v}' accepted verbatim", out["health_verdict"] == v)


def test_missing_narrative_gets_placeholder() -> None:
    out = _coerce({"health_verdict": "healthy", "key_shifts": []})
    check("missing narrative placeholder", out["narrative"] == "No assessment text was produced.")


def test_blank_narrative_gets_placeholder() -> None:
    out = _coerce({"health_verdict": "healthy", "narrative": "   ", "key_shifts": []})
    check("blank narrative placeholder", out["narrative"] == "No assessment text was produced.")


def test_non_string_narrative_gets_placeholder() -> None:
    out = _coerce({"health_verdict": "healthy", "narrative": 12345, "key_shifts": []})
    check("non-string narrative placeholder", out["narrative"] == "No assessment text was produced.")


def test_missing_key_shifts_defaults_empty() -> None:
    out = _coerce({"health_verdict": "healthy", "narrative": "x"})
    check("missing key_shifts → []", out["key_shifts"] == [])


def test_non_list_key_shifts_defaults_empty() -> None:
    out = _coerce({"health_verdict": "healthy", "narrative": "x", "key_shifts": "not a list"})
    check("non-list key_shifts → []", out["key_shifts"] == [])


def test_key_shifts_coerced_to_strings() -> None:
    out = _coerce({"health_verdict": "healthy", "narrative": "x", "key_shifts": [1, 2.5, "ok"]})
    check("non-string items stringified", out["key_shifts"] == ["1", "2.5", "ok"])


def main() -> int:
    for fn in (
        test_valid_input_passes_through,
        test_verdict_case_insensitive,
        test_invalid_verdict_defaults_to_watch,
        test_missing_verdict_defaults_to_watch,
        test_all_valid_verdicts_accepted,
        test_missing_narrative_gets_placeholder,
        test_blank_narrative_gets_placeholder,
        test_non_string_narrative_gets_placeholder,
        test_missing_key_shifts_defaults_empty,
        test_non_list_key_shifts_defaults_empty,
        test_key_shifts_coerced_to_strings,
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
