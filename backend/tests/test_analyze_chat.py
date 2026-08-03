"""Unit tests for the Analyze-with-AI follow-up chat (deliverable 8).

Self-contained: runs with plain `python -m tests.test_analyze_chat` (matching
the other tests in this repo) or under pytest. No DB, no network, no real
Anthropic calls — covers only:

1. Message validation (schemas.analyze) — role whitelist, content length cap,
   message count cap.
2. Prompt assembly (narrative.build_chat_system_prompt) — a pure function, so
   we can assert the aggregates JSON and filters echo actually land in the
   system prompt without calling the LLM.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.analytics.view_analysis.narrative import build_chat_system_prompt
from app.schemas.analyze import (
    MAX_CHAT_CONTENT_LEN,
    MAX_CHAT_MESSAGES,
    AnalyzeChatRequest,
    ChatMessageIn,
)

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


# ─── Message validation ──────────────────────────────────────────────────────


def test_valid_messages_pass_through() -> None:
    req = AnalyzeChatRequest(
        messages=[
            {"role": "user", "content": "Which channel drives the most revenue?"},
            {"role": "assistant", "content": "Referral leads close at the highest rate."},
        ]
    )
    check("two valid turns accepted", len(req.messages) == 2)
    check("roles preserved", [m.role for m in req.messages] == ["user", "assistant"])


def test_invalid_role_rejected() -> None:
    try:
        ChatMessageIn(role="system", content="hi")
        check("invalid role raises", False)
    except ValidationError:
        check("invalid role raises", True)


def test_empty_content_allowed_but_capped() -> None:
    # Empty content is permitted by the field default; only the length CAP is
    # a hard validation error, not blankness (the route itself 400s on an
    # empty messages list, not on a blank string within one).
    msg = ChatMessageIn(role="user", content="")
    check("blank content allowed at schema level", msg.content == "")


def test_oversized_content_rejected() -> None:
    too_long = "x" * (MAX_CHAT_CONTENT_LEN + 1)
    try:
        ChatMessageIn(role="user", content=too_long)
        check("oversized content raises", False)
    except ValidationError:
        check("oversized content raises", True)


def test_content_at_cap_accepted() -> None:
    exactly_at_cap = "x" * MAX_CHAT_CONTENT_LEN
    msg = ChatMessageIn(role="user", content=exactly_at_cap)
    check("content exactly at cap accepted", len(msg.content) == MAX_CHAT_CONTENT_LEN)


def test_message_count_over_cap_rejected() -> None:
    too_many = [{"role": "user", "content": "hi"} for _ in range(MAX_CHAT_MESSAGES + 1)]
    try:
        AnalyzeChatRequest(messages=too_many)
        check("over-cap message list raises", False)
    except ValidationError:
        check("over-cap message list raises", True)


def test_message_count_at_cap_accepted() -> None:
    exactly_at_cap = [{"role": "user", "content": "hi"} for _ in range(MAX_CHAT_MESSAGES)]
    req = AnalyzeChatRequest(messages=exactly_at_cap)
    check("message list exactly at cap accepted", len(req.messages) == MAX_CHAT_MESSAGES)


def test_empty_messages_list_is_schema_valid() -> None:
    # The schema itself permits an empty list (default_factory=list); the
    # route layer is what 400s on empty — that's a routing/behavior concern,
    # not a schema-validation one, so it's out of scope for this no-DB suite.
    req = AnalyzeChatRequest(messages=[])
    check("empty messages list is schema-valid", req.messages == [])


# ─── Prompt assembly (pure function) ─────────────────────────────────────────


def test_prompt_contains_aggregates_json() -> None:
    aggregates = {"row_count": 42, "breakdowns": {"channel": [{"label": "referral", "count": 10}]}}
    prompt = build_chat_system_prompt(
        label="leads", filters_echo="status=open", aggregates=aggregates
    )
    check("row_count value present in prompt", "42" in prompt)
    check("breakdown label present in prompt", "referral" in prompt)
    check("breakdown count present in prompt", '"count": 10' in prompt)


def test_prompt_contains_filters_echo() -> None:
    prompt = build_chat_system_prompt(
        label="leads", filters_echo="channel=referral, status=open", aggregates={"row_count": 1}
    )
    check("filters echo present in prompt", "channel=referral, status=open" in prompt)


def test_prompt_contains_surface_label() -> None:
    prompt = build_chat_system_prompt(
        label="sales calls", filters_echo="none", aggregates={"row_count": 0}
    )
    check("surface label present in prompt", "sales calls" in prompt)


def test_prompt_instructs_grounding_only() -> None:
    prompt = build_chat_system_prompt(label="leads", filters_echo="none", aggregates={"row_count": 0})
    check("prompt forbids inventing numbers", "invent" in prompt.lower())
    check("prompt scopes answers to data + conversation", "prior conversation" in prompt.lower())


def test_prompt_is_deterministic_pure_function() -> None:
    aggregates = {"row_count": 5}
    p1 = build_chat_system_prompt(label="leads", filters_echo="x", aggregates=aggregates)
    p2 = build_chat_system_prompt(label="leads", filters_echo="x", aggregates=aggregates)
    check("same inputs produce identical prompt", p1 == p2)


def main() -> int:
    for fn in (
        test_valid_messages_pass_through,
        test_invalid_role_rejected,
        test_empty_content_allowed_but_capped,
        test_oversized_content_rejected,
        test_content_at_cap_accepted,
        test_message_count_over_cap_rejected,
        test_message_count_at_cap_accepted,
        test_empty_messages_list_is_schema_valid,
        test_prompt_contains_aggregates_json,
        test_prompt_contains_filters_echo,
        test_prompt_contains_surface_label,
        test_prompt_instructs_grounding_only,
        test_prompt_is_deterministic_pure_function,
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
