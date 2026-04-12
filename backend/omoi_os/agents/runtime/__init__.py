"""Provider-agnostic agent runtime adapter layer.

This package exposes a neutral interface (`AgentRuntime`) and normalized event
types that wrap different AI agent backends (Claude Agent SDK today, OpenCode
server soon) so upstream workers don't have to care which backend runs a session.

The adapter exists purely as a seam: Phase 1a ships the interface and a
Claude-SDK-backed implementation with no callers rewired yet. Phase 1b will
switch `claude_sandbox_worker.py` and `spec-sandbox/executor/claude_executor.py`
to talk to this interface instead of the SDK directly.
"""

from omoi_os.agents.runtime.base import (
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
from omoi_os.agents.runtime.claude_sdk import ClaudeSDKRuntime

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
