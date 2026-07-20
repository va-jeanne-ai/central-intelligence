"""Prompt parity snapshot test.

Compares every module-level prompt constant against the frozen fixture. Any
prompt refactor (e.g. Phase 1's business-context templating) must keep the
rendered text identical for the current instance — this test is the gate.

Self-contained: runs with plain `python -m tests.parity.test_prompt_snapshots`
(pytest is not installed in this env), matching the other tests in this repo.

Regenerate the fixture (only when a prompt change is *intended*):
    UPDATE_PARITY_FIXTURES=1 PYTHONPATH=. .venv/bin/python -m tests.parity.test_prompt_snapshots
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from tests.parity.prompt_capture import collect_prompts

FIXTURE = Path(__file__).parent / "fixtures" / "prompt_snapshots.json"

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    status = "ok" if cond else "FAIL"
    print(f"  [{status}] {name}")
    if not cond:
        _failures.append(name)


def test_prompts_match_fixture() -> None:
    expected = json.loads(FIXTURE.read_text())
    actual = collect_prompts()

    missing = sorted(set(expected) - set(actual))
    added = sorted(set(actual) - set(expected))
    check(f"no prompt modules removed {missing or ''}", not missing)
    check(f"no prompt modules added unsnapshotted {added or ''}", not added)

    for mod in sorted(set(expected) & set(actual)):
        exp_consts, act_consts = expected[mod], actual[mod]
        gone = sorted(set(exp_consts) - set(act_consts))
        new = sorted(set(act_consts) - set(exp_consts))
        check(f"{mod}: constants unchanged {gone or new or ''}", not gone and not new)
        for name in sorted(set(exp_consts) & set(act_consts)):
            same = exp_consts[name] == act_consts[name]
            if not same:
                check(f"{mod}.{name}: text identical (drifted)", False)
    if not _failures:
        print(f"  all {sum(len(v) for v in expected.values())} constants across {len(expected)} modules match")


def main() -> int:
    if os.environ.get("UPDATE_PARITY_FIXTURES") == "1":
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        snapshot = collect_prompts()
        FIXTURE.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        n = sum(len(v) for v in snapshot.values())
        print(f"Wrote {FIXTURE.name}: {n} constants across {len(snapshot)} modules")
        return 0

    if not FIXTURE.exists():
        print(f"FAILED: fixture missing at {FIXTURE} — run with UPDATE_PARITY_FIXTURES=1 to create it")
        return 1

    print("test_prompts_match_fixture:")
    test_prompts_match_fixture()
    print("=" * 40)
    if _failures:
        print(f"FAILED: {len(_failures)} check(s)")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
