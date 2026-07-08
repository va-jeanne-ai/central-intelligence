"""Unit tests for the LLM JSON-object extractor (app.analytics._json).

Self-contained: runs with plain `python -m tests.test_analytics_json_extract`
(pytest is not installed in this env). Pure string parsing, no DB, no LLM call.
"""

from __future__ import annotations

import json

import pytest

from app.analytics._json import extract_json_object

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def test_plain_json_passthrough() -> None:
    raw = '{"a": 1, "b": [1, 2]}'
    check("plain JSON round-trips", json.loads(extract_json_object(raw)) == {"a": 1, "b": [1, 2]})


def test_fenced_json_block() -> None:
    raw = '```json\n{"a": 1}\n```'
    check("fenced json extracted", extract_json_object(raw) == '{"a": 1}')


def test_fenced_without_language_tag() -> None:
    raw = '```\n{"a": 1}\n```'
    check("bare fence extracted", extract_json_object(raw) == '{"a": 1}')


def test_leading_prose_before_object() -> None:
    raw = 'Here is the JSON you asked for:\n{"a": 1, "nested": {"x": 2}}'
    check("prose-prefixed object extracted", extract_json_object(raw) == '{"a": 1, "nested": {"x": 2}}')


def test_trailing_prose_after_object() -> None:
    raw = '{"a": 1}\nLet me know if you need anything else.'
    check("trailing prose stripped", extract_json_object(raw) == '{"a": 1}')


def test_nested_braces_balanced_correctly() -> None:
    raw = 'prose {"outer": {"inner": {"deep": 1}}, "list": [{"x": 1}]} more prose'
    extracted = extract_json_object(raw)
    check("nested braces balanced", json.loads(extracted) == {"outer": {"inner": {"deep": 1}}, "list": [{"x": 1}]})


def test_no_json_object_raises() -> None:
    with pytest.raises(ValueError):
        extract_json_object("no braces here at all")


def test_unbalanced_object_raises() -> None:
    with pytest.raises(ValueError):
        extract_json_object('{"a": 1, "b": {"c": 2}')


def test_whitespace_padded_fence() -> None:
    raw = '  \n```json\n  {"a": 1}  \n```  \n'
    check("padded fence trimmed", extract_json_object(raw) == '{"a": 1}')


def main() -> int:
    for fn in (
        test_plain_json_passthrough,
        test_fenced_json_block,
        test_fenced_without_language_tag,
        test_leading_prose_before_object,
        test_trailing_prose_after_object,
        test_nested_braces_balanced_correctly,
        test_whitespace_padded_fence,
    ):
        print(fn.__name__)
        fn()

    # The two "raises" tests use pytest.raises and aren't runnable via plain
    # `python -m` without pytest installed; they still collect fine under pytest.
    print("test_no_json_object_raises (pytest-only, skipped in plain run)")
    print("test_unbalanced_object_raises (pytest-only, skipped in plain run)")

    if _failures:
        print(f"\n{len(_failures)} FAILED: {_failures}")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
