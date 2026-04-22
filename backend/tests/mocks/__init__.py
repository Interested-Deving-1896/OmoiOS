"""Unified mock service layer for OmoiOS tests.

Provides typed mock implementations that match actual service interfaces,
replacing ad-hoc MagicMock usage across test files.
"""

from tests.mocks.llm import MockLLMService
from tests.mocks.github import MockGitHubService
from tests.mocks.event_bus import MockEventBus
from tests.mocks.daytona import MockDaytonaService
from tests.mocks.stripe import MockStripeService

__all__ = [
    "MockLLMService",
    "MockGitHubService",
    "MockEventBus",
    "MockDaytonaService",
    "MockStripeService",
]
