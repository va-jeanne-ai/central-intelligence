"""Unit tests for the shared insight taxonomy (app.prompts._taxonomy).

Self-contained: runs with plain `python -m tests.test_taxonomy` (pytest is not
installed in this env). Covers the best_use_case shape rule — the guardrail that
keeps the field from sprawling back into free text.
"""

from __future__ import annotations

from app.prompts import _taxonomy as t

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def test_seed_is_clean() -> None:
    # Every seed value must itself satisfy the shape rule (no slashes, ≤3 words).
    for v in t.BEST_USE_CASE_SEED:
        check(f"seed '{v}' passes shape rule", t.normalize_best_use_case(v) == v)
    check("seed has no duplicates", len(set(t.BEST_USE_CASE_SEED)) == len(t.BEST_USE_CASE_SEED))
    check("seed rendered into list str", "`Email Subject`" in t.BEST_USE_CASE_SEED_LIST_STR)


def test_normalize_best_use_case() -> None:
    n = t.normalize_best_use_case
    # seed value kept
    check("seed value kept", n("Email Subject") == "Email Subject")
    # clean new single-purpose value kept (membership NOT required)
    check("clean new value kept", n("Quiz Hook") == "Quiz Hook")
    check("3-word value kept", n("Lead Magnet Topic") == "Lead Magnet Topic")
    # slash-combo rejected
    check("slash-combo → None", n("Instagram Reel / Email subject line") is None)
    # sentence (>3 words) rejected
    check(
        "sentence → None",
        n("Email nurture sequence for cold leads who are satisfied") is None,
    )
    check("4 words → None", n("Email Subject And Body") is None)
    # whitespace handling
    check("trimmed", n("  Ad Copy  ") == "Ad Copy")
    check("empty → None", n("") is None)
    check("whitespace-only → None", n("   ") is None)
    # passthrough for non-strings / None
    check("None passthrough", n(None) is None)
    check("int passthrough", n(123) == 123)


def main() -> int:
    for fn in (test_seed_is_clean, test_normalize_best_use_case):
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
