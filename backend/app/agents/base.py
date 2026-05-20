"""
BaseAgent — Core agent class wrapping the Anthropic Python SDK.

Provides tool registration, async streaming with automatic tool-use loops,
conversation history management, and structured error handling.
"""

import json
import asyncio
import logging
from typing import AsyncIterator, Callable, Any

from anthropic import (
    AsyncAnthropic,
    APIError,
    RateLimitError,
    APIConnectionError,
    NOT_GIVEN,
)

logger = logging.getLogger(__name__)

_OVERLOAD_MAX_RETRIES = 3


class BaseAgent:
    """Abstract agent with Anthropic SDK integration, tool registry, and streaming.

    Subclasses set ``self.system_prompt`` and call ``register_tool`` to wire up
    capabilities.  The agent handles the full tool-use loop automatically —
    streaming text deltas back to the caller while executing any tool calls
    Claude requests until the model produces a final text response.
    """

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    def __init__(
        self,
        agent_id: str,
        name: str,
        model: str = "claude-sonnet-4-5-20250514",
        max_tokens: int = 4096,
        max_tool_rounds: int = 10,
    ):
        self.agent_id = agent_id
        self.name = name
        self.model = model
        self.max_tokens = max_tokens
        self.max_tool_rounds = max_tool_rounds

        from app.config import settings
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Tool schemas are sent to Claude; handlers stay server-side.
        self.tools: list[dict] = []
        self._tool_handlers: dict[str, Callable] = {}

        self.system_prompt: str = ""
        self.conversation_history: list[dict] = []

        logger.info("Initialized agent %s (%s) on model %s", agent_id, name, model)

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: Callable,
    ) -> None:
        """Register a callable tool.

        *schema* is forwarded to Claude in the ``tools`` parameter.
        *handler* is kept locally and invoked when Claude emits a ``tool_use`` block.
        Handlers may be sync or async — both are supported.
        """
        if name in self._tool_handlers:
            logger.warning("Overwriting existing tool handler for '%s'", name)

        self.tools.append(
            {
                "name": name,
                "description": description,
                "input_schema": input_schema,
            }
        )
        self._tool_handlers[name] = handler
        logger.debug("Registered tool '%s' on agent %s", name, self.agent_id)

    # -------------------------------------------------------------------
    # Streaming execution (primary interface)
    # -------------------------------------------------------------------

    async def stream_response(self, message: str) -> AsyncIterator[str]:
        """Stream response tokens, handling tool-use loops automatically.

        Yields text deltas as they arrive from the model.  When Claude calls
        a tool the loop executes the handler, appends the result, and asks
        Claude to continue — repeating until Claude produces a text-only
        response or ``max_tool_rounds`` is exhausted.
        """
        self.conversation_history.append({"role": "user", "content": message})

        rounds = 0
        has_yielded_text = False
        while rounds < self.max_tool_rounds:
            rounds += 1

            try:
                # Inner retry loop — handles transient overloaded_error only.
                for attempt in range(_OVERLOAD_MAX_RETRIES + 1):
                    if attempt > 0:
                        backoff = 2 ** (attempt - 1)
                        logger.warning(
                            "Agent %s: overloaded_error — retry %d/%d after %ds",
                            self.agent_id,
                            attempt,
                            _OVERLOAD_MAX_RETRIES,
                            backoff,
                        )
                        await asyncio.sleep(backoff)

                    yielded_in_attempt = False
                    try:
                        async with self.client.messages.stream(
                            model=self.model,
                            max_tokens=self.max_tokens,
                            system=self.system_prompt if self.system_prompt else NOT_GIVEN,
                            tools=self.tools if self.tools else NOT_GIVEN,
                            messages=self.conversation_history,
                        ) as stream:
                            async for event in stream:
                                if not hasattr(event, "type"):
                                    continue
                                if (
                                    event.type == "content_block_delta"
                                    and hasattr(event, "delta")
                                    and event.delta.type == "text_delta"
                                ):
                                    yield event.delta.text
                                    yielded_in_attempt = True
                                    has_yielded_text = True

                            # Collect the complete message once streaming finishes.
                            response = await stream.get_final_message()

                        # Successful stream — exit the retry loop.
                        break

                    except APIError as exc:
                        if getattr(exc, "status_code", None) != 529:
                            # Not an overloaded error — let the outer handlers deal with it.
                            raise
                        # HTTP 529 overloaded_error.
                        if not yielded_in_attempt and attempt < _OVERLOAD_MAX_RETRIES:
                            # Retriable overload with no partial output yet.
                            continue
                        # Retries exhausted or content already yielded.
                        logger.error(
                            "Agent %s: overloaded_error after %d attempt(s), giving up: %s",
                            self.agent_id,
                            attempt + 1,
                            exc,
                        )
                        yield "\n\n[Service is temporarily overloaded. Please try again in a moment.]"
                        return

            except RateLimitError as exc:
                logger.error(
                    "Rate-limited on agent %s: %s — backing off", self.agent_id, exc
                )
                # Surface a user-friendly message and stop the turn.
                yield "\n\n[Rate limit reached. Please try again in a moment.]"
                return

            except APIConnectionError as exc:
                logger.error(
                    "Connection error on agent %s: %s", self.agent_id, exc
                )
                yield "\n\n[Connection error. Please check network and retry.]"
                return

            except APIError as exc:
                logger.error(
                    "Anthropic API error on agent %s (status %s): %s",
                    self.agent_id,
                    getattr(exc, "status_code", "unknown"),
                    exc,
                )
                yield f"\n\n[API error: {exc.message}]"
                return

            # Persist the assistant turn in history.
            # ``response.content`` is a list of ContentBlock objects; we
            # must serialise them for the messages API.
            self.conversation_history.append(
                {"role": "assistant", "content": self._serialize_content(response.content)}
            )

            # ----- Tool-use handling -----
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # No tools requested — conversation turn is complete.
                return

            # Execute every tool call and collect results.
            tool_results = await self._execute_tool_calls(tool_use_blocks)

            # Append tool results as a user message so Claude can continue.
            self.conversation_history.append({"role": "user", "content": tool_results})

            logger.debug(
                "Agent %s completed tool round %d/%d (%d tool calls)",
                self.agent_id,
                rounds,
                self.max_tool_rounds,
                len(tool_use_blocks),
            )

            # Insert visual separator between tool rounds only if text was
            # already streamed, so there's no leading blank gap.
            if has_yielded_text:
                yield "\n\n"

        # Safety valve — should rarely be hit.
        logger.warning(
            "Agent %s hit max tool rounds (%d)", self.agent_id, self.max_tool_rounds
        )
        yield "\n\n[Reached maximum tool execution rounds. Stopping.]"

    # -------------------------------------------------------------------
    # Non-streaming execution
    # -------------------------------------------------------------------

    async def execute(self, message: str) -> dict[str, Any]:
        """Non-streaming execution.  Collects the full response and returns it.

        Returns a dict with ``agent_id``, ``response`` (text), and ``usage``
        metadata when available.
        """
        chunks: list[str] = []
        async for chunk in self.stream_response(message):
            chunks.append(chunk)

        return {
            "agent_id": self.agent_id,
            "response": "".join(chunks),
        }

    # -------------------------------------------------------------------
    # Conversation management
    # -------------------------------------------------------------------

    def reset_conversation(self) -> None:
        """Clear conversation history for a fresh session."""
        self.conversation_history = []
        logger.debug("Conversation reset for agent %s", self.agent_id)

    def get_conversation_length(self) -> int:
        """Return the number of messages in the current conversation."""
        return len(self.conversation_history)

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    async def _execute_tool_calls(
        self, tool_use_blocks: list
    ) -> list[dict[str, Any]]:
        """Execute tool handlers for a batch of tool_use blocks.

        Returns a list of ``tool_result`` dicts ready to be appended to the
        conversation as a user message.
        """
        tool_results: list[dict[str, Any]] = []

        for block in tool_use_blocks:
            handler = self._tool_handlers.get(block.name)

            if handler is None:
                logger.error(
                    "No handler registered for tool '%s' on agent %s",
                    block.name,
                    self.agent_id,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(
                            {"error": f"Unknown tool: {block.name}"}
                        ),
                        "is_error": True,
                    }
                )
                continue

            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**block.input)
                else:
                    # Run sync handlers in the default executor so we don't
                    # block the event loop.
                    result = await asyncio.get_running_loop().run_in_executor(
                        None, lambda: handler(**block.input)
                    )

                content = (
                    result if isinstance(result, str) else json.dumps(result)
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                    }
                )
                logger.debug(
                    "Tool '%s' executed successfully on agent %s",
                    block.name,
                    self.agent_id,
                )

            except Exception as exc:
                logger.exception(
                    "Tool '%s' raised on agent %s: %s", block.name, self.agent_id, exc
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": str(exc)}),
                        "is_error": True,
                    }
                )

        return tool_results

    @staticmethod
    def _serialize_content(content_blocks: list) -> list[dict[str, Any]]:
        """Convert SDK ContentBlock objects into plain dicts for the messages API.

        The Anthropic SDK returns typed objects (TextBlock, ToolUseBlock, etc.)
        but the messages parameter expects plain dicts when replaying history.
        """
        serialized: list[dict[str, Any]] = []
        for block in content_blocks:
            if block.type == "text":
                serialized.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                serialized.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
            else:
                # Future-proof: pass through any other block types as dicts.
                serialized.append(
                    block.model_dump() if hasattr(block, "model_dump") else {"type": block.type}
                )
        return serialized
