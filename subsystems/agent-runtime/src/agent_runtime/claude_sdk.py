"""Claude Agent SDK implementation of `AgentRuntime`.

This adapter wraps `claude_agent_sdk.ClaudeSDKClient` behind the neutral
`AgentRuntime` interface defined in `base.py`. Both `omoi-os` backend workers
and the `spec-sandbox` phase executor consume it so they never import from
`claude_agent_sdk` directly — the OpenCode cutover is a single-file swap
inside this package.

What this adapter does:

* Owns the `ClaudeSDKClient` lifecycle (`connect` / `disconnect`).
* Forwards `send_prompt` to `client.query()`.
* Translates every SDK message (`AssistantMessage`, `UserMessage`,
  `SystemMessage`, `ResultMessage`) and every content block into the neutral
  event types from `base.py`.
* Forwards `interrupt`, `set_permission_mode`, and `set_model` 1:1.

What this adapter explicitly does NOT do:

* Build `ClaudeAgentOptions` — callers pass a fully-constructed options object.
  Options construction is a large surface area with environment variable
  handling, hooks, tool allowlisting, etc.; keeping it in the caller means
  zero behavior change during the SDK → OpenCode cutover.
* Handle reporting/eventing — callers own downstream reporting; the adapter
  only normalizes the stream.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional, cast

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agent_runtime.base import (
    AgentRuntime,
    AssistantMessageEvent,
    ContentPart,
    PermissionDecision,
    PermissionRequestEvent,
    ResultEvent,
    RuntimeEvent,
    SystemEvent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolResultPart,
    Usage,
    UserMessageEvent,
)

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions, ToolPermissionContext


class ClaudeSDKRuntime(AgentRuntime):
    """Wrap `ClaudeSDKClient` behind the neutral `AgentRuntime` interface.

    The caller owns option construction:

        options = ClaudeAgentOptions(...)
        async with ClaudeSDKRuntime(options) as runtime:
            await runtime.send_prompt("hello")
            async for event in runtime.events():
                ...
    """

    def __init__(self, options: "ClaudeAgentOptions") -> None:
        self._options = options
        self._client: Optional[ClaudeSDKClient] = None

    # ------------------------------------------------------------------ lifecycle

    def _is_connected(self) -> bool:
        return self._client is not None

    async def connect(self) -> None:
        if self._client is not None:
            return
        options = self._options
        if self._permission_handler is not None:
            # Wire the neutral handler into the SDK's native can_use_tool slot.
            # If the caller already set can_use_tool on their options we'd
            # silently stomp it, which is a footgun — refuse instead.
            if getattr(options, "can_use_tool", None) is not None:
                raise RuntimeError(
                    "ClaudeSDKRuntime: both on_permission_request() handler "
                    "and options.can_use_tool are set. Pick one — either "
                    "register the neutral handler OR build the SDK callback "
                    "directly on your options, not both."
                )
            options = replace(options, can_use_tool=self._build_can_use_tool_wrapper())
        client = ClaudeSDKClient(options=options)
        await client.connect()
        self._client = client

    async def disconnect(self) -> None:
        client = self._client
        if client is None:
            return
        self._client = None
        await client.disconnect()

    # ------------------------------------------------------------------ actions

    async def send_prompt(self, prompt: str) -> None:
        client = self._require_client("send_prompt")
        await client.query(prompt)

    async def interrupt(self) -> None:
        # Interrupt is best-effort: if we aren't connected there's nothing to
        # cancel, and the SDK itself raises on a disconnected client.
        if self._client is None:
            return
        await self._client.interrupt()

    async def set_permission_mode(self, mode: str) -> None:
        client = self._require_client("set_permission_mode")
        # The SDK narrows `mode` to a Literal; we accept str at the interface
        # layer so OpenCode can pass its own vocabulary without a cast here.
        await client.set_permission_mode(cast("str", mode))  # type: ignore[arg-type]

    async def set_model(self, model: str) -> None:
        client = self._require_client("set_model")
        await client.set_model(model)

    # ------------------------------------------------------------------ streaming

    async def events(self) -> AsyncIterator[RuntimeEvent]:
        client = self._require_client("events")
        async for message in client.receive_messages():
            event = _translate_message(message)
            if event is not None:
                yield event
            if isinstance(event, ResultEvent):
                # ResultMessage is the terminal event for a turn; matching the
                # existing `claude_executor.py` semantics, we stop iterating
                # here so callers don't block on a stream that won't advance.
                return

    # ------------------------------------------------------------------ internal

    def _require_client(self, op: str) -> ClaudeSDKClient:
        if self._client is None:
            raise RuntimeError(
                f"ClaudeSDKRuntime.{op} called before connect(); "
                "use `async with runtime:` or call `await runtime.connect()` first"
            )
        return self._client

    def _build_can_use_tool_wrapper(self):
        """Create a `CanUseTool` callable that delegates to the neutral handler.

        The SDK signature is
        `async (tool_name, tool_input, ToolPermissionContext) -> Allow|Deny`;
        we translate that into our neutral `PermissionRequestEvent` + await
        the registered handler + translate the `PermissionDecision` back
        into the SDK's `PermissionResultAllow` / `PermissionResultDeny`.

        Note the SDK has no native request id, so we synthesize one from
        the tool name and input identity — good enough for the handler to
        key on if it cares, though most policies won't.
        """
        handler = self._permission_handler
        assert handler is not None  # guarded by caller

        async def can_use_tool(
            tool_name: str,
            tool_input: dict[str, Any],
            context: "ToolPermissionContext",
        ):
            event = PermissionRequestEvent(
                id=f"claude-sdk:{tool_name}:{id(tool_input)}",
                tool_name=tool_name,
                tool_input=dict(tool_input),
                patterns=[],
                metadata={
                    "signal": getattr(context, "signal", None),
                    "suggestions": getattr(context, "suggestions", None),
                },
            )
            decision: PermissionDecision = await handler(event)
            if decision.allow:
                # `updated_input=None` tells the SDK to use the original input
                # unchanged. `updated_permissions=None` means "no broadening".
                # Phase 2a deliberately does not surface scope="always" into
                # `updated_permissions` — that requires building a
                # PermissionUpdate list, which is SDK-specific glue we'd
                # rather land in its own PR once we have a caller that needs
                # session-wide approvals.
                return PermissionResultAllow(
                    behavior="allow",
                    updated_input=None,
                    updated_permissions=None,
                )
            return PermissionResultDeny(
                behavior="deny",
                message=decision.reason or "denied by permission handler",
                interrupt=False,
            )

        return can_use_tool


# =============================================================================
# Message translation
# =============================================================================


def _translate_message(message: object) -> Optional[RuntimeEvent]:
    """Map a raw SDK message to a neutral `RuntimeEvent`.

    Returns `None` for message types we don't surface upstream yet (currently
    there are none, but leaving the escape hatch avoids a future breaking
    change if the SDK adds new message kinds).
    """
    if isinstance(message, AssistantMessage):
        return AssistantMessageEvent(
            parts=[_translate_block(b) for b in message.content],
            model=getattr(message, "model", None),
            parent_tool_use_id=getattr(message, "parent_tool_use_id", None),
            error=getattr(message, "error", None),
        )
    if isinstance(message, UserMessage):
        # UserMessage.content can be either a string (plain user text) or a
        # list of blocks (echoed tool results). Normalize both into parts.
        content = message.content
        if isinstance(content, str):
            parts: list[ContentPart] = [TextPart(text=content)]
        else:
            parts = [_translate_block(b) for b in content]
        return UserMessageEvent(
            parts=parts,
            uuid=getattr(message, "uuid", None),
            parent_tool_use_id=getattr(message, "parent_tool_use_id", None),
        )
    if isinstance(message, SystemMessage):
        return SystemEvent(
            subtype=getattr(message, "subtype", "unknown"),
            data=dict(getattr(message, "data", {}) or {}),
        )
    if isinstance(message, ResultMessage):
        return _translate_result(message)
    return None


def _translate_block(block: object) -> ContentPart:
    """Map a raw SDK content block to a neutral `ContentPart`."""
    if isinstance(block, TextBlock):
        return TextPart(text=block.text)
    if isinstance(block, ThinkingBlock):
        return ThinkingPart(
            thinking=block.thinking,
            signature=getattr(block, "signature", None),
        )
    if isinstance(block, ToolUseBlock):
        return ToolCallPart(
            id=block.id,
            name=block.name,
            input=dict(block.input or {}),
        )
    if isinstance(block, ToolResultBlock):
        return ToolResultPart(
            tool_use_id=block.tool_use_id,
            content=block.content,
            is_error=bool(getattr(block, "is_error", False)),
        )
    # Unknown block kind: preserve as text so we don't silently drop data.
    return TextPart(text=repr(block))


def _translate_result(message: ResultMessage) -> ResultEvent:
    usage_obj = getattr(message, "usage", None)
    usage = _translate_usage(usage_obj) if usage_obj is not None else None

    return ResultEvent(
        subtype=getattr(message, "subtype", None),
        session_id=getattr(message, "session_id", None),
        num_turns=getattr(message, "num_turns", None),
        total_cost_usd=float(getattr(message, "total_cost_usd", 0.0) or 0.0),
        duration_ms=getattr(message, "duration_ms", None),
        duration_api_ms=getattr(message, "duration_api_ms", None),
        is_error=bool(getattr(message, "is_error", False)),
        stop_reason=getattr(message, "stop_reason", None),
        usage=usage,
        result=getattr(message, "result", None),
        structured_output=getattr(message, "structured_output", None),
    )


def _translate_usage(usage: object) -> Usage:
    """Extract token accounting from either a dict or a pydantic-like object."""
    if isinstance(usage, dict):
        return Usage(
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cache_read_tokens=usage.get("cache_read_input_tokens"),
            cache_write_tokens=usage.get("cache_creation_input_tokens"),
        )
    return Usage(
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
    )
