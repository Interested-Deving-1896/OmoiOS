"""OpenCode server implementation of `AgentRuntime`.

Talks to `opencode serve` (github.com/sst/opencode) over HTTP + Server-Sent
Events. Rationale for the specific wire choices is documented inline because
OpenCode's public docs don't enumerate them — everything below is pulled from
`packages/opencode/src/` in sst/opencode @ branch `dev`.

What this adapter does:

* Owns the session lifecycle:
  - `connect()` creates an `httpx.AsyncClient`, opens a session via
    `POST /session`, and spawns a background task that subscribes to the
    `/event` SSE stream.
  - `disconnect()` cancels the background task and closes the client.
* `send_prompt()` posts to `POST /session/:id/prompt_async` (the async variant
  that returns 204 and streams the real response via SSE, NOT the sync
  `/session/:id/message` endpoint which would block until the turn completes
  and return a single JSON blob — the sync endpoint is a bad fit for a
  streaming `AgentRuntime.events()` iterator).
* Translates SSE events into neutral `RuntimeEvent`s, filtered to the
  adapter's own `sessionID`:
  - `message.part.updated` with a TextPart → `AssistantMessageEvent(TextPart)`
  - `message.part.updated` with a ReasoningPart → `AssistantMessageEvent(ThinkingPart)`
  - `message.part.updated` with a ToolPart in pending/running state →
    `AssistantMessageEvent(ToolCallPart)` (synthesized to match the Claude
    SDK shape where tool calls come from the assistant)
  - `message.part.updated` with a ToolPart in completed/error state →
    `UserMessageEvent(ToolResultPart)` (synthesized to match the Claude SDK
    shape where tool results come from the user side)
  - `session.status` with `status.type === "idle"` → `ResultEvent` (terminal)
  - `session.error` → `ResultEvent(is_error=True, result=...)` (terminal)
  - `permission.asked` → invoke the registered handler and reply via
    `POST /permission/:id/reply` (the current endpoint, not the deprecated
    `/session/:id/permissions/:id`)
* `on_permission_request()` registers the neutral handler; no options
  rebuild is needed because OpenCode handles permissions out-of-band via SSE.

What this adapter deliberately does NOT do yet:

* Interrupts — OpenCode's interrupt endpoint wasn't in the research; Phase 2b
  adds it once we've verified against a real server.
* Cost/usage accounting — populated from `step-finish` parts / final
  `message.updated` in the real server; the skeleton emits a minimal
  `ResultEvent(session_id=...)` and leaves cost fields at their defaults.
* Partial text deltas via `message.part.delta` — the skeleton only consumes
  `message.part.updated` (full snapshots), not delta increments. Good enough
  for non-streaming UIs; streaming UIs will want delta handling in 2b.
* MCP server registration — `POST /mcp` exists but the adapter doesn't call
  it. Callers register MCP servers out-of-band.

Known divergences from `ClaudeSDKRuntime` that Phase 2b callers need to
reconcile:

* **One event per part, not one event per message**. OpenCode emits a
  `message.part.updated` for each part as it materializes; this adapter
  emits an `AssistantMessageEvent` for each. Callers that count turns or
  report "agent.assistant_message" per event will see inflated counts
  compared to the Claude adapter. Fix options: either buffer in the
  adapter (track messageIDs, flush on next message or on idle) or count
  `ResultEvent`s in the worker instead. We'll pick in Phase 2b.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

import httpx

from agent_runtime.base import (
    AgentRuntime,
    AssistantMessageEvent,
    PermissionRequestEvent,
    ResultEvent,
    RuntimeEvent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolResultPart,
    UserMessageEvent,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Options
# =============================================================================


@dataclass
class OpenCodeOptions:
    """Configuration for a single `OpenCodeRuntime` session.

    Per the phase 2a design decision, options are intentionally
    runtime-specific rather than funneling through a neutral `RuntimeOptions`
    struct — the Claude SDK and OpenCode have fundamentally different option
    surfaces (hooks vs permission callbacks, per-process env vs per-prompt
    model, plan mode vs agent name) and building a neutral shape now would
    risk premature abstraction before we've proven Phase 2b against a real
    `opencode serve`.
    """

    base_url: str = "http://localhost:4096"
    """Where `opencode serve` is listening."""

    password: Optional[str] = None
    """Value of `OPENCODE_SERVER_PASSWORD` if the server was launched with it.

    When set, every HTTP request (including the SSE stream) uses HTTP Basic
    auth. Unset → the server must also be running without auth.
    """

    username: str = "opencode"
    """HTTP Basic username. OpenCode's middleware defaults to `"opencode"`."""

    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    """Model selection passed per-prompt via `{model: {providerID, modelID}}`.

    Unlike the Claude SDK where model is a process-wide env var, OpenCode
    picks the model for each POST, so per-runtime-instance storage is
    sufficient. Leave unset to let the server pick its default.
    """

    agent: Optional[str] = None
    """Optional agent name (e.g. `"build"`, `"plan"`) sent with each prompt."""

    system: Optional[str] = None
    """Optional system-prompt override sent with each prompt."""

    session_title: Optional[str] = None
    """Human-readable title for the created session."""

    request_timeout_seconds: float = 60.0
    """Per-request HTTP timeout. SSE stream uses a separate longer read budget."""

    sse_read_timeout_seconds: Optional[float] = None
    """Read timeout on the `/event` SSE stream.

    `None` disables the read timeout entirely (default — the stream is
    long-lived and httpx's default 5s read timeout would kill it between
    events). Set to a finite value only if you want a hard idle deadline.
    """


# =============================================================================
# Runtime
# =============================================================================


class OpenCodeRuntime(AgentRuntime):
    """Wrap an `opencode serve` HTTP+SSE endpoint behind `AgentRuntime`.

    options = OpenCodeOptions(base_url="http://localhost:4096", password="...")
    async with OpenCodeRuntime(options) as runtime:
        runtime.on_permission_request(policy)  # optional (pre-connect)
        await runtime.send_prompt("hello")
        async for event in runtime.events():
            ...
    """

    def __init__(
        self,
        options: OpenCodeOptions,
        *,
        _transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        """Construct an OpenCode runtime.

        `_transport` is a test-only hook: passing an `httpx.MockTransport`
        lets unit tests intercept HTTP calls without standing up a real
        `opencode serve`. Production callers never touch it — the
        underscore prefix signals that.
        """
        self._options = options
        self._transport = _transport
        self._client: Optional[httpx.AsyncClient] = None
        self._session_id: Optional[str] = None
        self._event_task: Optional[asyncio.Task[None]] = None
        self._event_queue: asyncio.Queue[RuntimeEvent] = asyncio.Queue()
        # Tracks ToolParts we've already emitted as ToolCallPart so repeated
        # `message.part.updated` events for the same callID don't re-emit the
        # call. The set of callIDs resets on each new connect.
        self._emitted_tool_calls: set[str] = set()

    # ------------------------------------------------------------------ lifecycle

    def _is_connected(self) -> bool:
        return self._client is not None

    async def connect(self) -> None:
        if self._client is not None:
            return
        auth = (
            httpx.BasicAuth(self._options.username, self._options.password)
            if self._options.password is not None
            else None
        )
        self._client = httpx.AsyncClient(
            base_url=self._options.base_url,
            auth=auth,
            timeout=self._options.request_timeout_seconds,
            transport=self._transport,
        )
        self._session_id = await self._create_session()
        self._emitted_tool_calls = set()
        self._event_task = asyncio.create_task(self._event_loop())

    async def disconnect(self) -> None:
        if self._event_task is not None:
            self._event_task.cancel()
            try:
                await self._event_task
            except (asyncio.CancelledError, Exception):
                # Best effort — we're tearing down
                pass
            self._event_task = None
        client = self._client
        self._client = None
        self._session_id = None
        if client is not None:
            await client.aclose()

    # ------------------------------------------------------------------ actions

    async def send_prompt(self, prompt: str) -> None:
        client = self._require_client("send_prompt")
        session_id = self._require_session_id("send_prompt")
        body: dict[str, Any] = {
            "parts": [{"type": "text", "text": prompt}],
        }
        if self._options.provider_id and self._options.model_id:
            body["model"] = {
                "providerID": self._options.provider_id,
                "modelID": self._options.model_id,
            }
        if self._options.agent is not None:
            body["agent"] = self._options.agent
        if self._options.system is not None:
            body["system"] = self._options.system
        resp = await client.post(f"/session/{session_id}/prompt_async", json=body)
        resp.raise_for_status()

    async def interrupt(self) -> None:
        # OpenCode's interrupt endpoint shape wasn't confirmed in phase 2a
        # research. Leaving this as a no-op rather than a raise so callers
        # can still invoke it during teardown without crashing; phase 2b
        # wires the real endpoint once we've verified it against a running
        # server.
        logger.warning(
            "OpenCodeRuntime.interrupt() is a no-op in phase 2a; "
            "real interrupt wiring lands in phase 2b"
        )

    async def set_permission_mode(self, mode: str) -> None:
        # OpenCode has no "permission mode" enum — permissions are always
        # callback-driven through `on_permission_request()`. Phase 2b will
        # map Claude-vocab modes ("acceptEdits", "plan", "bypassPermissions")
        # to default permission policies at the daytona-spawner boundary;
        # the adapter itself stays pure.
        logger.debug(
            "OpenCodeRuntime.set_permission_mode(%r) is a no-op; "
            "use on_permission_request() instead",
            mode,
        )

    async def set_model(self, model: str) -> None:
        # Model in OpenCode is per-prompt, so changing it just updates the
        # options used by the next `send_prompt` call. `model` here is a
        # bare modelID; providerID stays whatever was configured at init.
        self._options = _replace_model_id(self._options, model)

    # ------------------------------------------------------------------ streaming

    async def events(self) -> AsyncIterator[RuntimeEvent]:
        self._require_client("events")
        while True:
            event = await self._event_queue.get()
            yield event
            if isinstance(event, ResultEvent):
                return

    # ------------------------------------------------------------------ internal: HTTP

    async def _create_session(self) -> str:
        assert self._client is not None
        body: dict[str, Any] = {}
        if self._options.session_title is not None:
            body["title"] = self._options.session_title
        resp = await self._client.post("/session", json=body)
        resp.raise_for_status()
        data = resp.json()
        session_id = data.get("id")
        if not isinstance(session_id, str):
            raise RuntimeError(
                f"OpenCode `POST /session` returned unexpected payload "
                f"(no string `id`): {data!r}"
            )
        return session_id

    async def _reply_permission(
        self,
        request_id: str,
        reply: str,
        message: Optional[str],
    ) -> None:
        client = self._client
        if client is None:
            return  # shutting down
        body: dict[str, Any] = {"reply": reply}
        if message is not None:
            body["message"] = message
        try:
            resp = await client.post(f"/permission/{request_id}/reply", json=body)
            resp.raise_for_status()
        except Exception as e:
            logger.error(
                "Failed to POST permission reply for request %s: %s",
                request_id,
                e,
            )

    # ------------------------------------------------------------------ internal: SSE loop

    async def _event_loop(self) -> None:
        """Background task: subscribe to `/event` and push `RuntimeEvent`s."""
        assert self._client is not None
        try:
            async with self._client.stream(
                "GET",
                "/event",
                timeout=httpx.Timeout(
                    self._options.request_timeout_seconds,
                    read=self._options.sse_read_timeout_seconds,
                ),
            ) as resp:
                resp.raise_for_status()
                async for raw_event in _iter_sse_events(resp):
                    await self._dispatch_sse_event(raw_event)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("OpenCode SSE event loop crashed: %s", e, exc_info=True)
            # Surface a terminal ResultEvent so the caller's `events()`
            # iterator doesn't hang forever. Callers that care can inspect
            # `is_error`.
            await self._event_queue.put(
                ResultEvent(is_error=True, result=f"SSE loop failed: {e}")
            )

    async def _dispatch_sse_event(self, raw: dict[str, Any]) -> None:
        """Translate one SSE payload into 0+ RuntimeEvents and enqueue them."""
        event_type = raw.get("type")
        props = raw.get("properties") or {}

        # Filter: ignore events for other sessions. Not every event carries
        # sessionID (e.g. server.heartbeat, server.connected) so we only
        # filter when the field is actually present.
        session_id = props.get("sessionID")
        if (
            session_id is not None
            and self._session_id is not None
            and session_id != self._session_id
        ):
            return

        if event_type == "message.part.updated":
            translated = self._translate_part_updated(props)
            if translated is not None:
                await self._event_queue.put(translated)
            return

        if event_type == "session.status":
            status = props.get("status") or {}
            if status.get("type") == "idle":
                await self._event_queue.put(ResultEvent(session_id=self._session_id))
            return

        if event_type == "session.error":
            error_info = props.get("error")
            await self._event_queue.put(
                ResultEvent(
                    session_id=self._session_id,
                    is_error=True,
                    result=str(error_info)
                    if error_info is not None
                    else "session.error",
                )
            )
            return

        if event_type == "permission.asked":
            await self._handle_permission_request(props)
            return

        # server.connected, server.heartbeat, message.updated, step-* parts,
        # file-watcher events, etc. — intentionally ignored in the skeleton.

    def _translate_part_updated(self, props: dict[str, Any]) -> Optional[RuntimeEvent]:
        part = props.get("part") or {}
        part_type = part.get("type")

        if part_type == "text":
            return AssistantMessageEvent(parts=[TextPart(text=part.get("text") or "")])

        if part_type == "reasoning":
            return AssistantMessageEvent(
                parts=[ThinkingPart(thinking=part.get("text") or "")]
            )

        if part_type == "tool":
            return self._translate_tool_part(part)

        # file / step-start / step-finish / snapshot / patch / agent / subtask /
        # retry / compaction are ignored in phase 2a. Phase 2b should decide
        # which of these to surface (step-finish carries cost/tokens, for
        # example, and should map onto ResultEvent.usage).
        return None

    def _translate_tool_part(self, part: dict[str, Any]) -> Optional[RuntimeEvent]:
        call_id = part.get("callID") or ""
        tool_name = part.get("tool") or ""
        state = part.get("state") or {}
        status = state.get("status")

        if status in ("pending", "running"):
            if call_id in self._emitted_tool_calls:
                # Already emitted the call for this callID — the subsequent
                # update is just a state transition we don't need to forward.
                return None
            self._emitted_tool_calls.add(call_id)
            return AssistantMessageEvent(
                parts=[
                    ToolCallPart(
                        id=call_id,
                        name=tool_name,
                        input=dict(state.get("input") or {}),
                    )
                ]
            )

        if status == "completed":
            return UserMessageEvent(
                parts=[
                    ToolResultPart(
                        tool_use_id=call_id,
                        content=state.get("output") or "",
                        is_error=False,
                    )
                ]
            )

        if status == "error":
            return UserMessageEvent(
                parts=[
                    ToolResultPart(
                        tool_use_id=call_id,
                        content=state.get("error") or "",
                        is_error=True,
                    )
                ]
            )

        return None

    async def _handle_permission_request(self, props: dict[str, Any]) -> None:
        request_id = props.get("id") or ""
        handler = self._permission_handler
        if handler is None:
            # No handler → safe default is reject. Logging at warning because
            # this is almost always a misconfiguration in production.
            logger.warning(
                "OpenCode permission.asked received but no handler is "
                "registered; rejecting request %s",
                request_id,
            )
            await self._reply_permission(
                request_id, "reject", "no permission handler registered"
            )
            return

        event = PermissionRequestEvent(
            id=request_id,
            tool_name=props.get("permission") or "",
            tool_input=dict(props.get("metadata") or {}),
            patterns=list(props.get("patterns") or []),
            metadata={
                "always": list(props.get("always") or []),
                "tool": props.get("tool"),
            },
        )
        try:
            decision = await handler(event)
        except Exception as e:
            logger.error(
                "Permission handler raised for request %s: %s",
                request_id,
                e,
                exc_info=True,
            )
            await self._reply_permission(request_id, "reject", f"handler error: {e}")
            return

        if decision.allow:
            reply = "always" if decision.scope == "always" else "once"
            await self._reply_permission(request_id, reply, None)
        else:
            await self._reply_permission(request_id, "reject", decision.reason)

    # ------------------------------------------------------------------ internal: guards

    def _require_client(self, op: str) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                f"OpenCodeRuntime.{op} called before connect(); "
                "use `async with runtime:` or call `await runtime.connect()` first"
            )
        return self._client

    def _require_session_id(self, op: str) -> str:
        if self._session_id is None:
            raise RuntimeError(f"OpenCodeRuntime.{op} called without an active session")
        return self._session_id


# =============================================================================
# SSE parsing
# =============================================================================


async def _iter_sse_events(resp: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """Yield decoded `data:` payloads from an httpx streaming response.

    This is an intentionally minimal SSE parser — the full spec supports
    multi-line `data:` fields, event ids, custom event names, and retry
    hints, but OpenCode's emitter only writes `data: <single line JSON>\\n\\n`,
    so a line-oriented parser is sufficient. If that ever changes the
    parser will need to rebuild here.
    """
    async for line in resp.aiter_lines():
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        payload = line[5:].lstrip()
        if not payload:
            continue
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Dropping malformed SSE payload: %r", payload)
            continue
        if isinstance(decoded, dict):
            yield decoded


# =============================================================================
# Helpers
# =============================================================================


def _replace_model_id(options: OpenCodeOptions, model_id: str) -> OpenCodeOptions:
    """Return a copy of `options` with `model_id` updated.

    Split out so `set_model` stays a one-liner and the replacement semantics
    (provider_id untouched) are easy to audit.
    """
    return OpenCodeOptions(
        base_url=options.base_url,
        password=options.password,
        username=options.username,
        provider_id=options.provider_id,
        model_id=model_id,
        agent=options.agent,
        system=options.system,
        session_title=options.session_title,
        request_timeout_seconds=options.request_timeout_seconds,
        sse_read_timeout_seconds=options.sse_read_timeout_seconds,
    )
