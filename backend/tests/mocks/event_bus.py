"""Mock EventBus service for testing.

Provides in-memory event capture without Redis dependency.
"""

from typing import Callable

from omoi_os.services.event_bus import SystemEvent


class MockEventBus:
    """Mock EventBus that captures events without Redis.

    Captures all published events in memory for assertions
    and supports subscriber callbacks for testing event flows.
    """

    def __init__(self):
        """Initialize the mock event bus."""
        self.published_events: list[SystemEvent] = []
        self._subscribers: dict[str, list[Callable]] = {}

    async def publish(self, event: SystemEvent) -> None:
        """Store event and notify subscribers.

        Args:
            event: The event to publish
        """
        self.published_events.append(event)

        # Notify pattern-based subscribers
        for pattern, callbacks in self._subscribers.items():
            if pattern == "*" or pattern in event.event_type:
                for callback in callbacks:
                    await callback(event)

    async def subscribe(self, pattern: str, callback: Callable) -> None:
        """Register a subscriber callback.

        Args:
            pattern: Event type pattern to match ("*" for all)
            callback: Async function to call when matching events are published
        """
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(callback)

    def assert_event_published(self, event_type: str) -> None:
        """Assert that an event type was published.

        Args:
            event_type: Expected event type

        Raises:
            AssertionError: If event type was not published
        """
        for event in self.published_events:
            if event.event_type == event_type:
                return
        raise AssertionError(f"Event type '{event_type}' was not published")

    def get_events_of_type(self, event_type: str) -> list[SystemEvent]:
        """Get all events of a specific type.

        Args:
            event_type: Event type to filter by

        Returns:
            List of matching events
        """
        return [
            event for event in self.published_events if event.event_type == event_type
        ]

    def clear(self) -> None:
        """Reset all captured events and subscribers."""
        self.published_events.clear()
        self._subscribers.clear()
