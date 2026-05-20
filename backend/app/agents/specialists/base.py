"""
SpecialistAgent — Domain expert with deep knowledge of a single area.

Specialists are the leaf nodes of the agent hierarchy.  They run on smaller,
faster models (Haiku by default) and are equipped with narrowly scoped tools
that let them read from databases, call external APIs, or trigger operator
actions within their domain.
"""

from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class SpecialistAgent(BaseAgent):
    """Domain expert agent.

    Each specialist owns a ``domain`` label (e.g. "email_marketing",
    "pipeline_management", "client_onboarding") that Directors use when
    deciding which specialist to delegate to.

    Specialists are designed to be lightweight and focused:
    - They use a smaller model (Haiku) for speed and cost efficiency.
    - Their tools are restricted to read/write operations within their domain.
    - They report results back to their parent Director, never directly to
      the end user.
    """

    def __init__(
        self,
        spec_id: str,
        name: str,
        domain: str,
        model: str = "claude-haiku-4-5-20251001",
        max_tokens: int = 2048,
        session: AsyncSession | None = None,
    ):
        super().__init__(agent_id=spec_id, name=name, model=model, max_tokens=max_tokens)
        self.domain = domain
        self._session = session

        # Subclasses wire up domain-specific tools in these hooks.
        self._register_db_tools()
        self._register_operator_tools()

        logger.info(
            "Initialized specialist %s (%s) — domain: %s",
            spec_id,
            name,
            domain,
        )

    # -------------------------------------------------------------------
    # Tool registration hooks (override in concrete subclasses)
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only database query tools for this specialist's domain.

        Override in concrete subclasses to add tools like:
        - ``search_contacts`` (CRM specialist)
        - ``get_campaign_stats`` (email marketing specialist)
        - ``lookup_invoice`` (billing specialist)

        These tools should be **read-only** to minimise blast radius.  Write
        operations go through operator tools with explicit confirmation.

        The base implementation is a no-op.  Subclasses should call
        ``self.register_tool(...)`` for each database-backed capability.
        """
        pass

    def _register_operator_tools(self) -> None:
        """Register write/action tools that mutate external state.

        Override in concrete subclasses to add tools like:
        - ``send_email`` (email specialist)
        - ``create_task`` (project management specialist)
        - ``update_deal_stage`` (sales specialist)

        Operator tools should include safety guards:
        - Require confirmation for destructive actions.
        - Log every mutation for audit trails.
        - Validate inputs before executing.

        The base implementation is a no-op.
        """
        pass

    # -------------------------------------------------------------------
    # Domain context
    # -------------------------------------------------------------------

    def set_domain_context(self, context: str) -> None:
        """Append domain-specific context to the system prompt.

        Useful for injecting business rules, style guides, or data summaries
        that the specialist should be aware of for the current session.
        """
        if context:
            self.system_prompt = f"{self.system_prompt}\n\n---\n\n{context}"
            logger.debug(
                "Appended domain context to specialist %s (%.60s...)",
                self.agent_id,
                context,
            )

    def get_domain_info(self) -> dict[str, str]:
        """Return a summary of this specialist's identity and domain."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "domain": self.domain,
            "model": self.model,
            "tool_count": len(self.tools),
        }
