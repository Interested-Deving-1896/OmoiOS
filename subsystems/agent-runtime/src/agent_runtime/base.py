"""Neutral runtime interface and event types for agent backends.

This module is deliberately backend-agnostic: it does not import from
`claude_agent_sdk` or any other concrete provider. Backend-specific adapters
(see `claude_sdk.py`) translate provider messages into these neutral types so
upstream workers can iterate a single canonical event stream.

Design notes:

* Event types are frozen dataclasses instead of Pydantic models so they're
  cheap to construct in hot streaming loops. Upstream code that needs JSON
  serialization can use `dataclasses.asdict` or its own helper.
* The content part hierarchy mirrors the Claude SDK's block shape (`TextBlock`,
  `ThinkingBlock`, `ToolUseBlock`, `ToolResultBlock`) because every mainstream
  agent runtime exposes the same four concepts; mapping them to OpenCode's
  SSE event shape in Phase 2 is a pure rename.
* `RuntimeEvent` is a union rather than a base class so exhaustive handling
  can be checked with `match` statements.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, AsyncIterator, Awaitable, Callable, Literal, Optional, Union

# =============================================================================
# Content parts
# =============================================================================


@dataclass(frozen=True, slots=True)
class TextPart:
    """Plain assistant or user text."""

    text: str


@dataclass(frozen=True, slots=True)
class ThinkingPart:
    """Extended-thinking reasoning block.

    `signature` is an opaque provider token used to replay thinking across
    turns; callers should forward it verbatim and never inspect it.
    """

    thinking: str
    signature: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ToolCallPart:
    """Model-issued tool invocation."""

    id: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResultPart:
    """Result returned to the model for a prior tool call.

    `content` is kept loose (str, list, or None) because the SDK exposes all
    three shapes: a string for plain-text results, a list for structured
    blocks, and `None` when a tool errored before producing output.
    """

    tool_use_id: str
    content: Union[str, list[Any], None]
    is_error: bool = False


ContentPart = Union[TextPart, ThinkingPart, ToolCallPart, ToolResultPart]


# =============================================================================
# Runtime events
# =============================================================================


@dataclass(frozen=True, slots=True)
class AssistantMessageEvent:
    """One assistant turn, possibly containing multiple content parts."""

    parts: list[ContentPart]
    model: Optional[str] = None
    parent_tool_use_id: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True, slots=True)
class UserMessageEvent:
    """User-originated message relayed back by the runtime.

    The SDK sometimes echoes user messages (including tool results formatted as
    user turns) through the receive stream; normalizing them here means
    downstream code doesn't have to special-case the direction.
    """

    parts: list[ContentPart]
    uuid: Optional[str] = None
    parent_tool_use_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class SystemEvent:
    """Backend-emitted system notification (init, config, telemetry)."""

    subtype: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Usage:
    """Token accounting for a completed turn."""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None


@dataclass(frozen=True, slots=True)
class ResultEvent:
    """Terminal event for a prompt/response cycle.

    Fields mirror Claude Agent SDK's `ResultMessage` but with snake_case
    canonical names so other backends can populate them without translation.
    """

    subtype: Optional[str] = None
    session_id: Optional[str] = None
    num_turns: Optional[int] = None
    total_cost_usd: float = 0.0
    duration_ms: Optional[int] = None
    duration_api_ms: Optional[int] = None
    is_error: bool = False
    stop_reason: Optional[str] = None
    usage: Optional[Usage] = None
    result: Optional[str] = None
    structured_output: Optional[dict[str, Any]] = None


RuntimeEvent = Union[
    AssistantMessageEvent,
    UserMessageEvent,
    SystemEvent,
    ResultEvent,
]


# =============================================================================
# Permission callbacks
# =============================================================================


@dataclass(frozen=True, slots=True)
class PermissionRequestEvent:
    """A backend-issued request for the caller to approve a tool invocation.

    Field names are deliberately backend-neutral. Each adapter translates its
    native permission-request shape into this:

    * **Claude Agent SDK** — wired via `ClaudeAgentOptions.can_use_tool`; the
      callback receives `(tool_name, tool_input, ToolPermissionContext)` which
      map to `tool_name` + `tool_input` + `metadata={"signal", "suggestions"}`.
      There is no native request id so adapters synthesize one.
    * **OpenCode** — the `permission.asked` SSE event carries
      `{id, sessionID, permission, patterns, metadata, always, tool?}`. The
      OpenCode adapter maps `permission` → `tool_name`, `metadata` →
      `tool_input`, and surfaces `patterns` directly; `always` and the
      optional `tool` cross-reference live under `metadata`.
    """

    id: str
    """Provider-issued id used to answer this specific request."""

    tool_name: str
    """Tool/permission key the agent is asking about (e.g. `"Bash"`, `"Edit"`)."""

    tool_input: dict[str, Any]
    """Tool-specific arguments — shape depends on the tool."""

    patterns: list[str] = field(default_factory=list)
    """Patterns this request would cover if approved (OpenCode native)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Backend-specific extras (signals, suggestions, cross-references)."""


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    """Caller's answer to a `PermissionRequestEvent`.

    `scope` controls whether the approval applies to a single invocation or
    is remembered for the rest of the session. OpenCode supports both
    natively (`reply: "once"|"always"`); the Claude SDK adapter maps
    `scope="always"` by setting `updated_permissions` on its
    `PermissionResultAllow`.
    """

    allow: bool
    scope: Literal["once", "always"] = "once"
    reason: Optional[str] = None
    """Human-readable note; surfaced as a denial message or audit trail."""


PermissionHandler = Callable[[PermissionRequestEvent], Awaitable[PermissionDecision]]
"""Async callback invoked by `AgentRuntime.on_permission_request()`."""


# =============================================================================
# Runtime interface
# =============================================================================


class AgentRuntime(ABC):
    """Provider-agnostic agent runtime.

    Lifecycle:

        async with runtime:                         # connect/disconnect
            runtime.on_permission_request(my_policy)  # optional, before connect
            await runtime.send_prompt("do X")
            async for event in runtime.events():
                handle(event)
                if isinstance(event, ResultEvent):
                    break

    Implementations must be safe to `connect()` exactly once per instance.
    Reconnecting after `disconnect()` is not required.
    """

    _permission_handler: Optional[PermissionHandler] = None
    """Registered permission callback (see `on_permission_request`)."""

    @abstractmethod
    async def connect(self) -> None:
        """Start the underlying session.

        Idempotent: calling `connect()` on an already-connected runtime is a
        no-op rather than an error.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Tear down the underlying session.

        Idempotent: safe to call after `connect()` failed or was never
        attempted.
        """

    @abstractmethod
    async def send_prompt(self, prompt: str) -> None:
        """Submit a user prompt to the current session.

        Returning from this method does not imply the response is complete —
        callers must iterate `events()` to consume the resulting stream.
        """

    @abstractmethod
    def events(self) -> AsyncIterator[RuntimeEvent]:
        """Async iterator yielding normalized events until the stream ends."""

    @abstractmethod
    async def interrupt(self) -> None:
        """Signal the current turn to stop as soon as the backend allows."""

    @abstractmethod
    async def set_permission_mode(self, mode: str) -> None:
        """Change permission mode mid-session.

        Mode strings follow the Claude SDK vocabulary today
        (`default`, `acceptEdits`, `plan`, `bypassPermissions`). OpenCode
        adapters should map these to their equivalent permission policies.
        """

    @abstractmethod
    async def set_model(self, model: str) -> None:
        """Change the model used for subsequent turns."""

    def on_permission_request(self, handler: PermissionHandler) -> None:
        """Register a handler for tool permission requests from the backend.

        The handler is called whenever the agent wants to execute a tool that
        requires approval. It receives a `PermissionRequestEvent` and returns
        a `PermissionDecision` (allow/deny + optional scope).

        Must be called BEFORE `connect()`. Calling it on a connected runtime
        raises `RuntimeError` — the handler has to be in place when the
        underlying client is built so the backend can wire it into options
        (Claude SDK's `can_use_tool`) or its SSE permission loop
        (OpenCode's `permission.asked` → `POST /permission/:id/reply`).

        Subclasses store the handler via `_permission_handler`; the default
        implementation is pure bookkeeping. Subclasses that need to inject
        something at connect time (e.g. `ClaudeSDKRuntime` needs to clone
        `ClaudeAgentOptions` with a `can_use_tool` wrapper) do that inside
        their own `connect()`.
        """
        self._require_disconnected_for("on_permission_request")
        self._permission_handler = handler

    def _require_disconnected_for(self, op: str) -> None:
        """Guard used by `on_permission_request` (and future pre-connect setters).

        Subclasses override `_is_connected()` to signal whether the backend
        has already been built and can no longer accept option changes.
        """
        if self._is_connected():
            raise RuntimeError(
                f"{op}() must be called before connect(); the permission "
                "handler has to be present when the backend client is built"
            )

    def _is_connected(self) -> bool:
        """Return True if the backend client is live.

        Subclasses override this. Default assumes disconnected so base-class
        instances (tests, mocks) don't trip the guard unexpectedly.
        """
        return False

    async def __aenter__(self) -> "AgentRuntime":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.disconnect()
