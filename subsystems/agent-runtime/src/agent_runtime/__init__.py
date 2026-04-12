"""Provider-agnostic agent runtime adapter layer.

This package exposes a neutral interface (`AgentRuntime`) and normalized event
types that wrap different AI agent backends (Claude Agent SDK today, OpenCode
server soon) so upstream code (omoi-os backend workers, spec-sandbox phase
executor) doesn't have to care which backend runs a session.

Layout: pure interface types in `base.py`, Claude Agent SDK implementation in
`claude_sdk.py`. Future backends (OpenCode HTTP client, local mocks, ...) live
alongside `claude_sdk.py` and register themselves by subclassing `AgentRuntime`
from `base.py`.
"""

from agent_runtime.base import (
    AgentRuntime,
    AssistantMessageEvent,
    ContentPart,
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
from agent_runtime.claude_sdk import ClaudeSDKRuntime

__all__ = [
    "AgentRuntime",
    "AssistantMessageEvent",
    "ClaudeSDKRuntime",
    "ContentPart",
    "ResultEvent",
    "RuntimeEvent",
    "SystemEvent",
    "TextPart",
    "ThinkingPart",
    "ToolCallPart",
    "ToolResultPart",
    "Usage",
    "UserMessageEvent",
]
