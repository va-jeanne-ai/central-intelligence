"""
DirectorAgent — Department-level coordinator that delegates to specialists.

Directors sit between Central Intelligence and Specialist agents.  Each Director owns a
domain (Marketing, Sales, Fulfillment) and exposes its registered specialists
as callable tools so Claude can delegate sub-tasks without the caller needing
to know which specialist to invoke.
"""

import json
import logging
from datetime import date
from typing import Any, Callable

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared time-window contract for director data tools
# ---------------------------------------------------------------------------
#
# Every director summary tool that reports time-scoped numbers exposes the SAME
# three params so the LLM has one consistent way to ask for any window. The
# numbers themselves are still computed in SQL — these params only steer WHICH
# rows the deterministic query sees. See feedback-ci-director-hypothesize-not-
# fabricate: directors reason over real data, they never originate numbers.

# Reusable JSON-schema fragment. Spread into a tool's input_schema properties.
WINDOW_PARAMS: dict[str, Any] = {
    "date_from": {
        "type": "string",
        "description": (
            "Start of the report window, ISO YYYY-MM-DD (inclusive). Scopes the "
            "ranged report numbers. Omit for all-time."
        ),
    },
    "date_to": {
        "type": "string",
        "description": (
            "End of the report window, ISO YYYY-MM-DD (inclusive). Also anchors "
            "the trailing volume series. Omit to anchor at today."
        ),
    },
    "window_weeks": {
        "type": "integer",
        "description": (
            "Length of the trailing volume/enrollment sparkline, in weeks "
            "(default 8). Independent of date_from/date_to."
        ),
        "default": 8,
    },
}


def _valid_iso_date(v: str | None) -> str | None:
    """Return the ISO string only if it parses to a real date, else None.

    Parsing happens again in the repo layer (where asyncpg needs a real date
    object); here we just refuse to forward obvious garbage so a bad param
    degrades to "all-time" rather than erroring the whole tool call.
    """
    if not v:
        return None
    try:
        date.fromisoformat(v)
        return v
    except (ValueError, TypeError):
        return None


def build_window(
    date_from: str | None = None,
    date_to: str | None = None,
    window_weeks: int = 8,
) -> dict[str, Any]:
    """Normalize the shared window params into kwargs for the stats repos.

    Clamps ``window_weeks`` to a sane range so an LLM-supplied value can't ask
    for a 0- or 10000-week series. Returns a plain dict the caller passes
    straight through to ``compute_*_stats``.
    """
    try:
        weeks = int(window_weeks)
    except (ValueError, TypeError):
        weeks = 8
    weeks = max(1, min(weeks, 52))
    return {
        "date_from": _valid_iso_date(date_from),
        "date_to": _valid_iso_date(date_to),
        "window_weeks": weeks,
    }


def window_meta(window: dict[str, Any], *, anchor: str | None = None) -> dict[str, Any]:
    """Build the ``_meta`` trace block attached to every windowed tool result.

    Lets the LLM (and a human auditor) see exactly which window produced the
    numbers it's about to reason over — the tracing half of the
    hypothesize-not-fabricate contract.
    """
    return {
        "window_weeks": window.get("window_weeks"),
        "date_from": window.get("date_from"),
        "date_to": window.get("date_to"),
        "anchor": anchor or window.get("date_to") or "today",
    }


class DirectorAgent(BaseAgent):
    """Department head that coordinates specialist agents.

    When a specialist is registered the Director automatically creates an
    Anthropic-compatible tool definition for it.  During a conversation Claude
    can call that tool, which triggers ``specialist.execute()`` under the hood
    and returns the result.
    """

    def __init__(
        self,
        director_id: str,
        name: str,
        department: str,
        model: str = "claude-sonnet-4-5-20250514",
    ):
        super().__init__(agent_id=director_id, name=name, model=model)
        self.department = department
        self.specialists: dict[str, "SpecialistAgent"] = {}

        # Hook for subclasses to wire up domain-specific data-access tools.
        self._register_data_tools()

    # -------------------------------------------------------------------
    # Specialist management
    # -------------------------------------------------------------------

    def register_specialist(
        self,
        specialist_id: str,
        specialist: Any,  # SpecialistAgent — forward ref to avoid circular import
    ) -> None:
        """Register a specialist and expose it as a callable tool.

        The tool schema uses the specialist's ``domain`` and ``name`` to build
        a description Claude can reason about.  The handler delegates to
        ``specialist.execute()``.
        """
        self.specialists[specialist_id] = specialist

        # Build an Anthropic tool schema for this specialist.
        tool_name = f"delegate_to_{specialist_id}"
        tool_description = (
            f"Delegate a task to {specialist.name}, a specialist in "
            f"{specialist.domain}. Send a clear, detailed instruction as the "
            f"'task' parameter. The specialist will execute independently and "
            f"return a result."
        )
        input_schema = {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "A detailed natural-language instruction for the "
                        "specialist to carry out."
                    ),
                },
            },
            "required": ["task"],
        }

        # Create a closure that captures the specialist reference.
        async def _handle_specialist_call(task: str, _spec=specialist) -> str:
            logger.info(
                "Director %s delegating to specialist %s: %.120s...",
                self.agent_id,
                _spec.agent_id,
                task,
            )
            result = await _spec.execute(task)
            return json.dumps(result)

        self.register_tool(
            name=tool_name,
            description=tool_description,
            input_schema=input_schema,
            handler=_handle_specialist_call,
        )

        logger.info(
            "Director %s registered specialist %s (%s)",
            self.agent_id,
            specialist_id,
            specialist.domain,
        )

    def get_specialist(self, specialist_id: str) -> Any | None:
        """Retrieve a registered specialist by ID."""
        return self.specialists.get(specialist_id)

    def list_specialists(self) -> list[dict[str, str]]:
        """Return a summary list of registered specialists."""
        return [
            {
                "id": sid,
                "name": spec.name,
                "domain": spec.domain,
            }
            for sid, spec in self.specialists.items()
        ]

    # -------------------------------------------------------------------
    # Data tools (override in concrete subclasses)
    # -------------------------------------------------------------------

    def _register_data_tools(self) -> None:
        """Register read-only data-access tools for this department.

        Override in concrete director subclasses (e.g. MarketingDirector) to
        add tools like ``get_campaign_metrics``, ``search_contacts``, etc.
        The base implementation is intentionally a no-op.
        """
        pass

    # -------------------------------------------------------------------
    # Reporting helpers
    # -------------------------------------------------------------------

    async def get_department_status(self) -> dict[str, Any]:
        """Return a lightweight status summary for the department.

        Useful for Central Intelligence when she needs a roll-up across departments.
        Subclasses can extend this with live data.
        """
        return {
            "director_id": self.agent_id,
            "department": self.department,
            "specialist_count": len(self.specialists),
            "specialists": self.list_specialists(),
            "conversation_length": self.get_conversation_length(),
        }
