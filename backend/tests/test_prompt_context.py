"""Unit tests for the instance-profile prompt templating (app.prompts.context).

Self-contained: runs with plain `python -m tests.test_prompt_context` (pytest
is not installed in this env), matching the other tests in this repo.

Covers the productization Phase 1 invariants:
1. No rendered prompt constant leaks an unsubstituted {{token}}.
2. Rendering with a different profile actually swaps vertical/app_name.
3. A partially-filled instance_profile row keeps defaults for NULL columns.
"""

from __future__ import annotations

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, _profile_from_row, render
from tests.parity.prompt_capture import collect_prompts

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    status = "ok" if cond else "FAIL"
    print(f"  [{status}] {name}")
    if not cond:
        _failures.append(name)


def test_no_unrendered_tokens() -> None:
    for mod, consts in collect_prompts().items():
        for name, text in consts.items():
            if isinstance(text, str):
                check(f"{mod}.{name} has no leftover {{{{token}}}}", "{{" not in text)


def test_render_swaps_profile_values() -> None:
    from app.prompts.central_intelligence_v1 import render_central_intelligence_system_prompt
    from app.prompts.icp_generator_v1 import render_icp_generator_system_prompt

    other = PromptProfile(
        app_name="Acme Copilot",
        vertical="logistics and freight",
        vertical_context={"icp_expertise": "**Freight economics** — margins move on lanes."},
    )
    ci = render_central_intelligence_system_prompt(other)
    check("orchestrator prompt uses custom app_name", "Acme Copilot" in ci)
    check("orchestrator prompt uses custom vertical", "logistics and freight business" in ci)
    check("orchestrator prompt drops default app name", "Central Intelligence" not in ci)

    icp = render_icp_generator_system_prompt(other)
    check("icp prompt uses custom expertise block", "Freight economics" in icp)
    check("icp prompt drops coaching expertise", "high-ticket coaching" not in icp)
    check("no tokens left in custom render", "{{" not in ci and "{{" not in icp)

    default_ci = render_central_intelligence_system_prompt(DEFAULT_PROFILE)
    check("default render keeps original platform name", "Central Intelligence" in default_ci)
    check("default render keeps original vertical", "coaching and consulting" in default_ci)


def test_partial_row_keeps_defaults() -> None:
    class FakeRow:
        business_name = None
        vertical = "dental clinics"
        business_description = None
        target_audience = None
        brand_voice = None
        currency_symbol = None
        vertical_context = None
        benchmarks = {"close_rate_good": "35%"}

    profile = _profile_from_row(FakeRow())
    check("row vertical overrides default", profile.vertical == "dental clinics")
    check("NULL app_name keeps default", profile.app_name == DEFAULT_PROFILE.app_name)
    check(
        "default vertical_context survives merge",
        "icp_expertise" in profile.vertical_context,
    )
    check("row benchmarks land as bm_ slots", profile.slots()["bm_close_rate_good"] == "35%")
    check(
        "render substitutes merged slots",
        render("{{vertical}} / {{bm_close_rate_good}}", profile) == "dental clinics / 35%",
    )


def main() -> int:
    for fn in (
        test_no_unrendered_tokens,
        test_render_swaps_profile_values,
        test_partial_row_keeps_defaults,
    ):
        print(f"\n{fn.__name__}:")
        fn()
    print(f"\n{'=' * 40}")
    if _failures:
        print(f"FAILED: {len(_failures)} check(s): {_failures}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
