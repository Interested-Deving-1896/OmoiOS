"""Unit tests for the OpenCode implementation of `AgentRuntime`.

Uses `httpx.MockTransport` to intercept every HTTP call the runtime makes —
no real `opencode serve` process is required. The mock responds to:

* `POST /session` → returns `{id: "sess-test"}`
* `POST /session/sess-test/prompt_async` → 204
* `GET  /event` → returns a canned SSE byte stream terminating in a
  `session.status` idle event
* `POST /permission/:id/reply` → 200

These cover the full happy-path lifecycle plus the permission-callback loop.
Phase 2b will add integration tests against a real `opencode serve` instance
spun up as a fixture; phase 2a's budget is purely unit coverage so the
translation + wire shape + queue plumbing are exercised in isolation.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx
import pytest

from agent_runtime import (
    AgentRuntime,
    AssistantMessageEvent,
    OpenCodeOptions,
    OpenCodeRuntime,
    PermissionDecision,
    PermissionRequestEvent,
    ResultEvent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolResultPart,
    UserMessageEvent,
)


# =============================================================================
# MockTransport helpers
# =============================================================================


def _sse_body(events: list[dict[str, Any]]) -> bytes:
    """Encode a list of SSE payloads the way `opencode serve` does.

    OpenCode writes one `data: <json>\\n\\n` line per bus event. The trailing
    blank line is mandatory per SSE; `aiter_lines()` splits on it.
    """
    lines = [f"data: {json.dumps(ev)}\n\n" for ev in events]
    return "".join(lines).encode("utf-8")


def _make_mock_handler(
    *,
    sse_events: list[dict[str, Any]],
    session_id: str = "sess-test",
    permission_replies: Optional[list[dict[str, Any]]] = None,
    session_responses: Optional[list[dict[str, Any]]] = None,
) -> tuple[httpx.MockTransport, list[dict[str, Any]]]:
    """Build a MockTransport that fakes the subset of `opencode serve` we use.

    Returns `(transport, captured_requests)` where `captured_requests` is a
    mutable list the handler appends each intercepted request to. Tests can
    introspect it to assert on request bodies, paths, and auth headers.
    """
    captured: list[dict[str, Any]] = []
    replies = permission_replies if permission_replies is not None else []
    sess_created = session_responses if session_responses is not None else []

    def handler(request: httpx.Request) -> httpx.Response:
        body_bytes = request.read()
        try:
            body_json = json.loads(body_bytes) if body_bytes else None
        except json.JSONDecodeError:
            body_json = None
        captured.append(
            {
                "method": request.method,
                "path": request.url.path,
                "json": body_json,
                "headers": dict(request.headers),
            }
        )

        path = request.url.path
        method = request.method

        if method == "POST" and path == "/session":
            payload = sess_created.pop(0) if sess_created else {"id": session_id}
            return httpx.Response(200, json=payload)

        if (
            method == "POST"
            and path.startswith("/session/")
            and path.endswith("/prompt_async")
        ):
            return httpx.Response(204)

        if method == "GET" and path == "/event":
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=_sse_body(sse_events),
            )

        if (
            method == "POST"
            and path.startswith("/permission/")
            and path.endswith("/reply")
        ):
            replies.append(body_json or {})
            return httpx.Response(200, json={"ok": True})

        return httpx.Response(404, json={"error": f"mock: unhandled {method} {path}"})

    transport = httpx.MockTransport(handler)
    return transport, captured


async def _drain_events(runtime: OpenCodeRuntime) -> list[Any]:
    """Iterate `runtime.events()` to completion (it stops at ResultEvent)."""
    collected = []
    async for event in runtime.events():
        collected.append(event)
    return collected


# =============================================================================
# OpenCodeOptions
# =============================================================================


class TestOpenCodeOptions:
    def test_defaults(self) -> None:
        opts = OpenCodeOptions()
        assert opts.base_url == "http://localhost:4096"
        assert opts.username == "opencode"
        assert opts.password is None
        assert opts.provider_id is None
        assert opts.model_id is None
        assert opts.agent is None
        assert opts.system is None

    @pytest.mark.asyncio
    async def test_set_model_replaces_model_id_only(self) -> None:
        transport, _ = _make_mock_handler(sse_events=[])
        opts = OpenCodeOptions(provider_id="anthropic", model_id="old")
        runtime = OpenCodeRuntime(opts, _transport=transport)
        await runtime.set_model("new")
        assert runtime._options.provider_id == "anthropic"
        assert runtime._options.model_id == "new"


# =============================================================================
# Lifecycle
# =============================================================================


class TestOpenCodeRuntimeLifecycle:
    @pytest.mark.asyncio
    async def test_connect_creates_session(self) -> None:
        transport, captured = _make_mock_handler(
            sse_events=[
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(
            OpenCodeOptions(session_title="test"), _transport=transport
        )
        async with runtime:
            assert runtime._session_id == "sess-test"

        session_creates = [c for c in captured if c["path"] == "/session"]
        assert len(session_creates) == 1
        assert session_creates[0]["json"] == {"title": "test"}

    @pytest.mark.asyncio
    async def test_connect_is_idempotent(self) -> None:
        transport, captured = _make_mock_handler(
            sse_events=[
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        await runtime.connect()
        await runtime.connect()
        await runtime.disconnect()

        # Only one session created regardless of double-connect.
        assert len([c for c in captured if c["path"] == "/session"]) == 1

    @pytest.mark.asyncio
    async def test_disconnect_without_connect_is_noop(self) -> None:
        runtime = OpenCodeRuntime(OpenCodeOptions())
        # Must not raise — we never connected, nothing to tear down.
        await runtime.disconnect()

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        async with OpenCodeRuntime(OpenCodeOptions(), _transport=transport) as runtime:
            assert isinstance(runtime, AgentRuntime)
            assert runtime._session_id == "sess-test"

    @pytest.mark.asyncio
    async def test_connect_raises_if_session_id_missing(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[],
            session_responses=[{"not_id": "oops"}],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        with pytest.raises(RuntimeError, match="no string `id`"):
            await runtime.connect()


# =============================================================================
# send_prompt
# =============================================================================


class TestSendPrompt:
    @pytest.mark.asyncio
    async def test_before_connect_raises(self) -> None:
        runtime = OpenCodeRuntime(OpenCodeOptions())
        with pytest.raises(RuntimeError, match="send_prompt called before connect"):
            await runtime.send_prompt("hi")

    @pytest.mark.asyncio
    async def test_posts_to_prompt_async(self) -> None:
        transport, captured = _make_mock_handler(
            sse_events=[
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            await runtime.send_prompt("hello world")

        prompts = [c for c in captured if "/prompt_async" in c["path"]]
        assert len(prompts) == 1
        assert prompts[0]["method"] == "POST"
        assert prompts[0]["path"] == "/session/sess-test/prompt_async"
        assert prompts[0]["json"] == {
            "parts": [{"type": "text", "text": "hello world"}]
        }

    @pytest.mark.asyncio
    async def test_includes_model_and_agent_when_set(self) -> None:
        transport, captured = _make_mock_handler(
            sse_events=[
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        opts = OpenCodeOptions(
            provider_id="anthropic",
            model_id="claude-sonnet-4-5",
            agent="build",
            system="you are helpful",
        )
        runtime = OpenCodeRuntime(opts, _transport=transport)
        async with runtime:
            await runtime.send_prompt("do stuff")

        prompt_req = next(c for c in captured if "/prompt_async" in c["path"])
        body = prompt_req["json"]
        assert body["model"] == {
            "providerID": "anthropic",
            "modelID": "claude-sonnet-4-5",
        }
        assert body["agent"] == "build"
        assert body["system"] == "you are helpful"


# =============================================================================
# Event translation
# =============================================================================


class TestEventTranslation:
    @pytest.mark.asyncio
    async def test_text_part_becomes_assistant_message(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "sess-test",
                        "part": {"type": "text", "text": "hello"},
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            events = await _drain_events(runtime)

        assert len(events) == 2
        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].parts == [TextPart(text="hello")]
        assert isinstance(events[1], ResultEvent)
        assert events[1].session_id == "sess-test"

    @pytest.mark.asyncio
    async def test_reasoning_part_becomes_thinking(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "sess-test",
                        "part": {"type": "reasoning", "text": "considering"},
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            events = await _drain_events(runtime)

        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].parts == [ThinkingPart(thinking="considering")]

    @pytest.mark.asyncio
    async def test_tool_part_pending_becomes_tool_call(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "sess-test",
                        "part": {
                            "type": "tool",
                            "callID": "call-1",
                            "tool": "Bash",
                            "state": {
                                "status": "pending",
                                "input": {"cmd": "ls"},
                                "raw": "ls",
                            },
                        },
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            events = await _drain_events(runtime)

        assert isinstance(events[0], AssistantMessageEvent)
        assert events[0].parts == [
            ToolCallPart(id="call-1", name="Bash", input={"cmd": "ls"})
        ]

    @pytest.mark.asyncio
    async def test_tool_part_completed_becomes_user_tool_result(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "sess-test",
                        "part": {
                            "type": "tool",
                            "callID": "call-1",
                            "tool": "Bash",
                            "state": {
                                "status": "completed",
                                "input": {"cmd": "ls"},
                                "output": "file1\nfile2",
                                "title": "ls",
                                "metadata": {},
                                "time": {"start": 1, "end": 2},
                            },
                        },
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            events = await _drain_events(runtime)

        assert isinstance(events[0], UserMessageEvent)
        assert events[0].parts == [
            ToolResultPart(tool_use_id="call-1", content="file1\nfile2", is_error=False)
        ]

    @pytest.mark.asyncio
    async def test_tool_part_error_marks_is_error(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "sess-test",
                        "part": {
                            "type": "tool",
                            "callID": "call-2",
                            "tool": "Bash",
                            "state": {
                                "status": "error",
                                "input": {"cmd": "badcmd"},
                                "error": "command not found",
                                "time": {"start": 1, "end": 2},
                            },
                        },
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            events = await _drain_events(runtime)

        assert isinstance(events[0], UserMessageEvent)
        assert isinstance(events[0].parts[0], ToolResultPart)
        assert events[0].parts[0].is_error is True
        assert events[0].parts[0].content == "command not found"

    @pytest.mark.asyncio
    async def test_tool_call_deduped_on_state_transitions(self) -> None:
        """A ToolPart that goes pending → running shouldn't emit two ToolCallParts."""
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "sess-test",
                        "part": {
                            "type": "tool",
                            "callID": "call-3",
                            "tool": "Edit",
                            "state": {
                                "status": "pending",
                                "input": {"file": "a.py"},
                                "raw": "",
                            },
                        },
                    },
                },
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "sess-test",
                        "part": {
                            "type": "tool",
                            "callID": "call-3",
                            "tool": "Edit",
                            "state": {
                                "status": "running",
                                "input": {"file": "a.py"},
                                "time": {"start": 1},
                            },
                        },
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            events = await _drain_events(runtime)

        tool_calls = [
            e
            for e in events
            if isinstance(e, AssistantMessageEvent)
            and any(isinstance(p, ToolCallPart) for p in e.parts)
        ]
        assert len(tool_calls) == 1  # not 2

    @pytest.mark.asyncio
    async def test_events_from_other_sessions_are_ignored(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "some-other-session",
                        "part": {"type": "text", "text": "wrong session"},
                    },
                },
                {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": "sess-test",
                        "part": {"type": "text", "text": "right session"},
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            events = await _drain_events(runtime)

        text_events = [e for e in events if isinstance(e, AssistantMessageEvent)]
        assert len(text_events) == 1
        assert text_events[0].parts == [TextPart(text="right session")]

    @pytest.mark.asyncio
    async def test_session_error_becomes_error_result(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "session.error",
                    "properties": {
                        "sessionID": "sess-test",
                        "error": {"name": "rate_limit", "message": "slow down"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            events = await _drain_events(runtime)

        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)
        assert events[0].is_error is True
        assert events[0].result is not None
        assert "rate_limit" in events[0].result


# =============================================================================
# Permission callback
# =============================================================================


class TestPermissionCallback:
    @pytest.mark.asyncio
    async def test_handler_allow_once_replies_once(self) -> None:
        reply_log: list[dict[str, Any]] = []
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "permission.asked",
                    "properties": {
                        "id": "perm-1",
                        "sessionID": "sess-test",
                        "permission": "Bash",
                        "patterns": ["cmd:*"],
                        "metadata": {"cmd": "ls"},
                        "always": [],
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
            permission_replies=reply_log,
        )

        received: list[PermissionRequestEvent] = []

        async def handler(req: PermissionRequestEvent) -> PermissionDecision:
            received.append(req)
            return PermissionDecision(allow=True)

        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        runtime.on_permission_request(handler)
        async with runtime:
            await _drain_events(runtime)

        assert len(received) == 1
        assert received[0].id == "perm-1"
        assert received[0].tool_name == "Bash"
        assert received[0].tool_input == {"cmd": "ls"}
        assert received[0].patterns == ["cmd:*"]

        assert reply_log == [{"reply": "once"}]

    @pytest.mark.asyncio
    async def test_handler_allow_always(self) -> None:
        reply_log: list[dict[str, Any]] = []
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "permission.asked",
                    "properties": {
                        "id": "perm-2",
                        "sessionID": "sess-test",
                        "permission": "Edit",
                        "patterns": [],
                        "metadata": {},
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
            permission_replies=reply_log,
        )

        async def handler(req: PermissionRequestEvent) -> PermissionDecision:
            return PermissionDecision(allow=True, scope="always")

        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        runtime.on_permission_request(handler)
        async with runtime:
            await _drain_events(runtime)

        assert reply_log == [{"reply": "always"}]

    @pytest.mark.asyncio
    async def test_handler_reject_with_reason(self) -> None:
        reply_log: list[dict[str, Any]] = []
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "permission.asked",
                    "properties": {
                        "id": "perm-3",
                        "sessionID": "sess-test",
                        "permission": "Bash",
                        "patterns": [],
                        "metadata": {"cmd": "rm -rf /"},
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
            permission_replies=reply_log,
        )

        async def handler(req: PermissionRequestEvent) -> PermissionDecision:
            return PermissionDecision(allow=False, reason="destructive")

        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        runtime.on_permission_request(handler)
        async with runtime:
            await _drain_events(runtime)

        assert reply_log == [{"reply": "reject", "message": "destructive"}]

    @pytest.mark.asyncio
    async def test_no_handler_rejects_by_default(self) -> None:
        reply_log: list[dict[str, Any]] = []
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "permission.asked",
                    "properties": {
                        "id": "perm-4",
                        "sessionID": "sess-test",
                        "permission": "Bash",
                        "patterns": [],
                        "metadata": {},
                    },
                },
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
            permission_replies=reply_log,
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)
        async with runtime:
            await _drain_events(runtime)

        assert len(reply_log) == 1
        assert reply_log[0]["reply"] == "reject"
        assert "no permission handler" in reply_log[0]["message"]

    @pytest.mark.asyncio
    async def test_on_permission_request_after_connect_raises(self) -> None:
        transport, _ = _make_mock_handler(
            sse_events=[
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(OpenCodeOptions(), _transport=transport)

        async def handler(req: PermissionRequestEvent) -> PermissionDecision:
            return PermissionDecision(allow=True)

        async with runtime:
            with pytest.raises(
                RuntimeError,
                match="on_permission_request.*must be called before connect",
            ):
                runtime.on_permission_request(handler)


# =============================================================================
# Auth
# =============================================================================


class TestAuth:
    @pytest.mark.asyncio
    async def test_basic_auth_header_sent_when_password_set(self) -> None:
        transport, captured = _make_mock_handler(
            sse_events=[
                {
                    "type": "session.status",
                    "properties": {
                        "sessionID": "sess-test",
                        "status": {"type": "idle"},
                    },
                },
            ],
        )
        runtime = OpenCodeRuntime(
            OpenCodeOptions(password="hunter2"), _transport=transport
        )
        async with runtime:
            pass

        session_req = next(c for c in captured if c["path"] == "/session")
        auth_header = session_req["headers"].get("authorization", "")
        assert auth_header.startswith("Basic ")
