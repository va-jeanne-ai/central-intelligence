"""Collect every module-level prompt constant for parity snapshots.

Walks ``app.prompts`` and ``app.agents.directors`` and captures each module's
UPPERCASE string constants (and lists/tuples of strings, e.g. taxonomy
vocabularies). Constants re-exported into several modules are captured once per
module on purpose — the snapshot records the *effective* text each module sees.

Prompts composed dynamically at agent-init time (not module constants) are not
captured here; Phase 1's rendered-prompt tests cover those.
"""

from __future__ import annotations

import importlib
import pkgutil

PROMPT_PACKAGES = ["app.prompts", "app.agents.directors"]


def collect_prompts() -> dict[str, dict[str, str | list[str]]]:
    """Return {module_path: {CONSTANT_NAME: text_or_list}} for all prompt constants."""
    snapshot: dict[str, dict[str, str | list[str]]] = {}
    for pkg_name in PROMPT_PACKAGES:
        pkg = importlib.import_module(pkg_name)
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name.startswith("__"):
                continue
            mod = importlib.import_module(f"{pkg_name}.{info.name}")
            consts: dict[str, str | list[str]] = {}
            for attr in dir(mod):
                # Private (underscore-prefixed) names are templates/internals,
                # not rendered prompt text — the rendered constants are the parity
                # surface.
                if attr.startswith("_") or not attr.isupper():
                    continue
                val = getattr(mod, attr)
                if isinstance(val, str):
                    consts[attr] = val
                elif isinstance(val, (list, tuple)) and val and all(
                    isinstance(x, str) for x in val
                ):
                    consts[attr] = list(val)
            if consts:
                snapshot[f"{pkg_name}.{info.name}"] = consts
    return snapshot
