"""Unit tests for the provider-agnostic agent runtime adapter.

These tests cover two layers:

1. **Pure translation** — `_translate_message` / `_translate_block` called
   with real `claude_agent_sdk` dataclasses. Verifies that every SDK message
   and block kind round-trips into a neutral `RuntimeEvent` with the expected
   fields. No mocking required — the SDK types are plain dataclasses so we
   can construct them directly.

2. **`ClaudeSDKRuntime` lifecycle** — monkeypatches `ClaudeSDKClient` at the
   adapter module boundary with a fake that records method calls and can be
   primed with a canned message stream. Verifies connect/disconnect
   idempotence, send_prompt forwarding, event iteration, early termination
   on `ResultEvent`, and the pre-connect error for `send_prompt`/`events`.

Phase 1a ships the adapter with no callers; these tests are the only place
exercising it until Phase 1b.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from omoi_os.agents.runtime import (
    AgentRuntime,
    AssistantMessageEvent,
    ClaudeSDKRuntime,
    ResultEvent,
    SystemEvent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolResultPart,
    UserMessageEvent,
)
from omoi_os.agents.runtime.claude_sdk import (
    _translate_block,
    _translate_message,
    _translate_usage,
)


# =============================================================================
# Message translation (pure functions against real SDK dataclasses)
# =============================================================================


class TestTranslateBlock:
    """`_translate_block` maps each SDK block kind to a neutral ContentPart."""

    def test_text_block_becomes_text_part(self) -> None:
        part = _translate_block(TextBlock(text="hello world"))
        assert part == TextPart(text="hello world")

    def test_thinking_block_preserves_signature(self) -> None:
        part = _translate_block(
            ThinkingBlock(thinking="considering options", signature="sig-123")
        )
        assert part == ThinkingPart(thinking="considering options", signature="sig-123")

    def test_tool_use_block_copies_input_dict(self) -> None:
        source_input = {"file_path": "/tmp/x", "content": "data"}
        part = _translate_block(
            ToolUseBlock(id="tool-1", name="Write", input=source_input)
        )
        assert isinstance(part, ToolCallPart)
        assert part.id == "tool-1"
        assert part.name == "Write"
        assert part.input == source_input
        # Defensive copy: mutating the source must not affect the part.
        source_input["file_path"] = "/tmp/mutated"
        assert part.input["file_path"] == "/tmp/x"

    def test_tool_result_block_with_string_content(self) -> None:
        part = _translate_block(
            ToolResultBlock(tool_use_id="tool-1", content="ok", is_error=False)
        )
        assert part == ToolResultPart(
            tool_use_id="tool-1", content="ok", is_error=False
        )

    def test_tool_result_block_marks_error(self) -> None:
        part = _translate_block(
            ToolResultBlock(tool_use_id="tool-2", content="boom", is_error=True)
        )
        assert isinstance(part, ToolResultPart)
        assert part.is_error is True

    def test_unknown_block_is_preserved_as_text(self) -> None:
        class MysteryBlock:
            def __repr__(self) -> str:
                return "MysteryBlock()"

        part = _translate_block(MysteryBlock())
        assert part == TextPart(text="MysteryBlock()")


class TestTranslateMessage:
    """`_translate_message` maps each SDK message kind to a RuntimeEvent."""

    def test_assistant_message_with_mixed_blocks(self) -> None:
        msg = AssistantMessage(
            content=[
                TextBlock(text="let me think"),
                ThinkingBlock(thinking="reasoning", signature="sig"),
                ToolUseBlock(id="t1", name="Read", input={"path": "a.py"}),
            ],
            model="claude-sonnet-4-5-20250929",
            parent_tool_use_id=None,
            error=None,
        )
        event = _translate_message(msg)
        assert isinstance(event, AssistantMessageEvent)
        assert event.model == "claude-sonnet-4-5-20250929"
        assert len(event.parts) == 3
        assert event.parts[0] == TextPart(text="let me think")
        assert event.parts[1] == ThinkingPart(thinking="reasoning", signature="sig")
        assert event.parts[2] == ToolCallPart(
            id="t1", name="Read", input={"path": "a.py"}
        )

    def test_assistant_message_propagates_error_and_parent(self) -> None:
        msg = AssistantMessage(
            content=[TextBlock(text="partial")],
            model="x",
            parent_tool_use_id="parent-t",
            error="rate_limited",
        )
        event = _translate_message(msg)
        assert isinstance(event, AssistantMessageEvent)
        assert event.error == "rate_limited"
        assert event.parent_tool_use_id == "parent-t"

    def test_user_message_string_content_becomes_single_text_part(self) -> None:
        msg = UserMessage(content="hi there", uuid="u-1", parent_tool_use_id=None)
        event = _translate_message(msg)
        assert isinstance(event, UserMessageEvent)
        assert event.uuid == "u-1"
        assert event.parts == [TextPart(text="hi there")]

    def test_user_message_block_list_content_translates_each(self) -> None:
        msg = UserMessage(
            content=[
                ToolResultBlock(tool_use_id="t1", content="result", is_error=False),
                TextBlock(text="follow-up"),
            ],
            uuid="u-2",
            parent_tool_use_id="p1",
        )
        event = _translate_message(msg)
        assert isinstance(event, UserMessageEvent)
        assert len(event.parts) == 2
        assert isinstance(event.parts[0], ToolResultPart)
        assert event.parts[0].tool_use_id == "t1"
        assert event.parts[1] == TextPart(text="follow-up")
        assert event.parent_tool_use_id == "p1"

    def test_system_message_preserves_subtype_and_data(self) -> None:
        msg = SystemMessage(subtype="init", data={"session_id": "s1", "tools": 5})
        event = _translate_message(msg)
        assert isinstance(event, SystemEvent)
        assert event.subtype == "init"
        assert event.data == {"session_id": "s1", "tools": 5}

    def test_system_message_with_none_data_coerces_to_empty_dict(self) -> None:
        msg = SystemMessage(subtype="ping", data=None)  # type: ignore[arg-type]
        event = _translate_message(msg)
        assert isinstance(event, SystemEvent)
        assert event.data == {}

    def test_result_message_full_shape(self) -> None:
        msg = ResultMessage(
            subtype="final",
            duration_ms=1234,
            duration_api_ms=567,
            is_error=False,
            num_turns=3,
            session_id="session-xyz",
            total_cost_usd=0.0125,
            usage={
                "input_tokens": 100,
                "output_tokens": 200,
                "cache_read_input_tokens": 50,
                "cache_creation_input_tokens": 25,
            },
            result="task complete",
            structured_output={"score": 0.9},
        )
        event = _translate_message(msg)
        assert isinstance(event, ResultEvent)
        assert event.subtype == "final"
        assert event.session_id == "session-xyz"
        assert event.num_turns == 3
        assert event.total_cost_usd == pytest.approx(0.0125)
        assert event.duration_ms == 1234
        assert event.duration_api_ms == 567
        assert event.is_error is False
        assert event.result == "task complete"
        assert event.structured_output == {"score": 0.9}
        assert event.usage is not None
        assert event.usage.input_tokens == 100
        assert event.usage.output_tokens == 200
        assert event.usage.cache_read_tokens == 50
        assert event.usage.cache_write_tokens == 25

    def test_result_message_usage_object_shape(self) -> None:
        """Usage may arrive as an object with attributes instead of a dict."""

        class UsageObj:
            input_tokens = 7
            output_tokens = 11
            cache_read_input_tokens = None
            cache_creation_input_tokens = None

        msg = ResultMessage(
            subtype="final",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="s",
            total_cost_usd=0.0,
            usage=UsageObj(),  # type: ignore[arg-type]
            result=None,
            structured_output=None,
        )
        event = _translate_message(msg)
        assert isinstance(event, ResultEvent)
        assert event.usage is not None
        assert event.usage.input_tokens == 7
        assert event.usage.output_tokens == 11
        assert event.usage.cache_read_tokens is None

    def test_result_message_none_cost_coerces_to_zero(self) -> None:
        msg = ResultMessage(
            subtype="final",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="s",
            total_cost_usd=None,  # type: ignore[arg-type]
            usage=None,
            result=None,
            structured_output=None,
        )
        event = _translate_message(msg)
        assert isinstance(event, ResultEvent)
        assert event.total_cost_usd == 0.0

    def test_unknown_message_returns_none(self) -> None:
        assert _translate_message(object()) is None


class TestTranslateUsage:
    def test_dict_usage_maps_cache_fields(self) -> None:
        usage = _translate_usage(
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "cache_read_input_tokens": 3,
                "cache_creation_input_tokens": 4,
            }
        )
        assert usage.input_tokens == 1
        assert usage.output_tokens == 2
        assert usage.cache_read_tokens == 3
        assert usage.cache_write_tokens == 4

    def test_dict_usage_missing_fields_default_to_none(self) -> None:
        usage = _translate_usage({"input_tokens": 5})
        assert usage.input_tokens == 5
        assert usage.output_tokens is None
        assert usage.cache_read_tokens is None
        assert usage.cache_write_tokens is None


# =============================================================================
# ClaudeSDKRuntime lifecycle (fake ClaudeSDKClient)
# =============================================================================


class FakeSDKClient:
    """Drop-in fake for `claude_agent_sdk.ClaudeSDKClient`.

    Records every method call so tests can assert the adapter forwards
    correctly, and lets tests prime the `receive_messages()` stream with a
    canned list of SDK messages.
    """

    def __init__(
        self,
        *,
        options: Any = None,
        messages: Optional[list[Any]] = None,
    ) -> None:
        self.options = options
        self.messages: list[Any] = messages or []
        self.connected = False
        self.disconnected = False
        self.queries: list[str] = []
        self.interrupted = False
        self.permission_modes: list[str] = []
        self.models: list[str] = []

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def query(self, prompt: str) -> None:
        self.queries.append(prompt)

    def receive_messages(self) -> AsyncIterator[Any]:
        messages = list(self.messages)

        async def _gen() -> AsyncIterator[Any]:
            for m in messages:
                yield m

        return _gen()

    async def interrupt(self) -> None:
        self.interrupted = True

    async def set_permission_mode(self, mode: str) -> None:
        self.permission_modes.append(mode)

    async def set_model(self, model: str) -> None:
        self.models.append(model)


@pytest.fixture
def patch_sdk_client(monkeypatch: pytest.MonkeyPatch) -> list[FakeSDKClient]:
    """Swap `ClaudeSDKClient` in the adapter module with `FakeSDKClient`.

    Returns a list that accumulates every FakeSDKClient instance constructed
    during the test, so assertions can reach into the fake after the runtime
    has been exercised.
    """
    constructed: list[FakeSDKClient] = []

    def _factory(*, options: Any) -> FakeSDKClient:
        client = FakeSDKClient(options=options)
        constructed.append(client)
        return client

    monkeypatch.setattr("omoi_os.agents.runtime.claude_sdk.ClaudeSDKClient", _factory)
    return constructed


class TestClaudeSDKRuntimeLifecycle:
    @pytest.mark.asyncio
    async def test_connect_then_disconnect(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        await runtime.connect()
        await runtime.disconnect()

        assert len(patch_sdk_client) == 1
        fake = patch_sdk_client[0]
        assert fake.connected is True
        assert fake.disconnected is True

    @pytest.mark.asyncio
    async def test_connect_is_idempotent(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        await runtime.connect()
        await runtime.connect()
        await runtime.disconnect()

        # Only one client ever constructed.
        assert len(patch_sdk_client) == 1

    @pytest.mark.asyncio
    async def test_disconnect_without_connect_is_noop(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        # Should not raise.
        await runtime.disconnect()
        assert patch_sdk_client == []

    @pytest.mark.asyncio
    async def test_async_context_manager(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        async with ClaudeSDKRuntime(options=object()) as runtime:  # type: ignore[arg-type]
            assert isinstance(runtime, AgentRuntime)
        fake = patch_sdk_client[0]
        assert fake.connected is True
        assert fake.disconnected is True

    @pytest.mark.asyncio
    async def test_send_prompt_forwards_to_query(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        async with runtime:
            await runtime.send_prompt("do the thing")
            await runtime.send_prompt("another turn")

        assert patch_sdk_client[0].queries == ["do the thing", "another turn"]

    @pytest.mark.asyncio
    async def test_send_prompt_before_connect_raises(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        with pytest.raises(RuntimeError, match="send_prompt called before connect"):
            await runtime.send_prompt("nope")

    @pytest.mark.asyncio
    async def test_events_before_connect_raises(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        with pytest.raises(RuntimeError, match="events called before connect"):
            async for _ in runtime.events():
                pass

    @pytest.mark.asyncio
    async def test_events_translates_stream_and_stops_on_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        messages = [
            AssistantMessage(
                content=[TextBlock(text="hello")],
                model="m",
                parent_tool_use_id=None,
                error=None,
            ),
            AssistantMessage(
                content=[ToolUseBlock(id="t1", name="Bash", input={"cmd": "ls"})],
                model="m",
                parent_tool_use_id=None,
                error=None,
            ),
            ResultMessage(
                subtype="final",
                duration_ms=10,
                duration_api_ms=5,
                is_error=False,
                num_turns=2,
                session_id="s1",
                total_cost_usd=0.01,
                usage=None,
                result=None,
                structured_output=None,
            ),
            # This sentinel would explode if the adapter doesn't stop at
            # ResultMessage — a `str` has no attributes the translator can
            # read, and we'd notice by the assertion below.
            AssistantMessage(
                content=[TextBlock(text="should not reach")],
                model="m",
                parent_tool_use_id=None,
                error=None,
            ),
        ]
        fake = FakeSDKClient(messages=messages)
        monkeypatch.setattr(
            "omoi_os.agents.runtime.claude_sdk.ClaudeSDKClient",
            lambda *, options: fake,
        )

        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        collected = []
        async with runtime:
            async for event in runtime.events():
                collected.append(event)

        # Expect exactly 3 events: 2 assistant messages + 1 result.
        assert len(collected) == 3
        assert isinstance(collected[0], AssistantMessageEvent)
        assert collected[0].parts == [TextPart(text="hello")]
        assert isinstance(collected[1], AssistantMessageEvent)
        assert isinstance(collected[1].parts[0], ToolCallPart)
        assert collected[1].parts[0].name == "Bash"
        assert isinstance(collected[2], ResultEvent)
        assert collected[2].session_id == "s1"

    @pytest.mark.asyncio
    async def test_interrupt_forwards_when_connected(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        async with runtime:
            await runtime.interrupt()
        assert patch_sdk_client[0].interrupted is True

    @pytest.mark.asyncio
    async def test_interrupt_without_connect_is_noop(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        await runtime.interrupt()
        assert patch_sdk_client == []

    @pytest.mark.asyncio
    async def test_set_permission_mode_forwards(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        async with runtime:
            await runtime.set_permission_mode("acceptEdits")
            await runtime.set_permission_mode("plan")
        assert patch_sdk_client[0].permission_modes == ["acceptEdits", "plan"]

    @pytest.mark.asyncio
    async def test_set_model_forwards(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        async with runtime:
            await runtime.set_model("claude-opus-4-6")
        assert patch_sdk_client[0].models == ["claude-opus-4-6"]

    @pytest.mark.asyncio
    async def test_set_permission_mode_before_connect_raises(
        self, patch_sdk_client: list[FakeSDKClient]
    ) -> None:
        runtime = ClaudeSDKRuntime(options=object())  # type: ignore[arg-type]
        with pytest.raises(
            RuntimeError, match="set_permission_mode called before connect"
        ):
            await runtime.set_permission_mode("plan")
