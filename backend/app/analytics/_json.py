"""Shared helper for pulling a JSON object out of an LLM response.

Claude is asked for "pure JSON" but in practice sometimes wraps it in ```json fences
or surrounds it with prose. This extractor tolerates both. Kept here (rather than in a
Celery task module) so any layer — analytics, tasks, routes — can import it without a
cross-module dependency on the task system.
"""

from __future__ import annotations

import re

_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def extract_json_object(raw_text: str) -> str:
    """Pull the JSON object out of an LLM response.

    Handles the two common deviations from "pure JSON":
      1. Wrapped in ```json fences
      2. Has leading/trailing prose around the JSON

    Returns the JSON-object substring. Raises if no ``{``-balanced object found.
    """
    stripped = raw_text.strip()

    # Case 1: fenced
    match = _JSON_FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()

    # Case 2: locate the outermost { ... } via brace-counting. Tolerates
    # leading "Here are the insights:" or similar prose.
    start = stripped.find("{")
    if start == -1:
        raise ValueError("No JSON object found in Claude response.")
    depth = 0
    for i in range(start, len(stripped)):
        c = stripped[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : i + 1]
    raise ValueError("Unbalanced JSON object in Claude response.")
