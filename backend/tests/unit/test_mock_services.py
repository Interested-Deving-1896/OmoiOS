"""Tests for unified mock service layer.

Comprehensive tests for all mock services to ensure they work correctly
and provide the expected interface.
"""

import pytest
from pydantic import BaseModel

from omoi_os.services.event_bus import SystemEvent
from tests.mocks.daytona import MockDaytonaService
from tests.mocks.event_bus import MockEventBus
from tests.mocks.github import MockGitHubService
from tests.mocks.llm import MockLLMService
from tests.mocks.stripe import MockStripeService


# =============================================================================
# Test Pydantic Models for LLM Tests
# =============================================================================


class MockAnalysis(BaseModel):
    """Test model for analysis results."""

    score: float = 0.0
    summary: str = ""


class MockRequirements(BaseModel):
    """Test model for requirements."""

    items: list[str] = []
    priority: str = "medium"


# =============================================================================
# MockLLMService Tests
# =============================================================================


@pytest.mark.asyncio
async def test_mock_llm_default_complete():
    """Test that complete() returns default string when no response configured."""
    mock = MockLLMService()
    result = await mock.complete("Test prompt")
    assert result == "[mock-llm: no response configured]"


@pytest.mark.asyncio
async def test_mock_llm_set_complete_response():
    """Test that complete() returns custom response when configured."""
    mock = MockLLMService()
    mock.set_complete_response("Custom response")
    result = await mock.complete("Test prompt")
    assert result == "Custom response"


@pytest.mark.asyncio
async def test_mock_llm_structured_output_default():
    """Test that structured_output generates placeholder for Pydantic model."""
    mock = MockLLMService()
    result = await mock.structured_output("Test prompt", MockAnalysis)
    assert isinstance(result, MockAnalysis)
    assert result.score == 0.0  # Default value
    assert result.summary == ""  # Default value


@pytest.mark.asyncio
async def test_mock_llm_set_response_for_type():
    """Test that structured_output returns canned response for type."""
    mock = MockLLMService()
    expected = MockAnalysis(score=0.95, summary="Great result")
    mock.set_response(MockAnalysis, expected)
    result = await mock.structured_output("Test prompt", MockAnalysis)
    assert result == expected


@pytest.mark.asyncio
async def test_mock_llm_set_response_for_prompt():
    """Test that response can be triggered by prompt content."""
    mock = MockLLMService()
    expected = MockAnalysis(score=0.9, summary="Prompt match")
    mock.set_response_for_prompt("special keyword", expected)
    result = await mock.structured_output(
        "This contains special keyword here", MockAnalysis
    )
    assert result == expected


@pytest.mark.asyncio
async def test_mock_llm_call_tracking():
    """Test that all calls are tracked."""
    mock = MockLLMService()
    await mock.complete("Prompt 1")
    await mock.structured_output("Prompt 2", MockAnalysis)
    await mock.complete("Prompt 3")

    assert len(mock.calls) == 3
    assert mock.calls[0]["method"] == "complete"
    assert mock.calls[0]["prompt"] == "Prompt 1"
    assert mock.calls[1]["method"] == "structured_output"
    assert mock.calls[1]["prompt"] == "Prompt 2"
    assert mock.calls[2]["method"] == "complete"


@pytest.mark.asyncio
async def test_mock_llm_assert_called_with_type():
    """Test assert_called_with_type passes and fails correctly."""
    mock = MockLLMService()

    # Should raise before any calls
    with pytest.raises(AssertionError):
        mock.assert_called_with_type(MockAnalysis)

    await mock.structured_output("Test", MockAnalysis)
    mock.assert_called_with_type(MockAnalysis)  # Should pass

    with pytest.raises(AssertionError):
        mock.assert_called_with_type(MockRequirements)


@pytest.mark.asyncio
async def test_mock_llm_assert_call_count():
    """Test assert_call_count passes and fails correctly."""
    mock = MockLLMService()

    mock.assert_call_count(0)  # Should pass

    with pytest.raises(AssertionError):
        mock.assert_call_count(1)

    await mock.complete("Test")
    mock.assert_call_count(1)  # Should pass

    with pytest.raises(AssertionError):
        mock.assert_call_count(0)


@pytest.mark.asyncio
async def test_mock_llm_reset():
    """Test that reset clears call history."""
    mock = MockLLMService()
    mock.set_complete_response("custom")
    await mock.complete("Test")
    assert len(mock.calls) == 1

    mock.reset()

    assert len(mock.calls) == 0
    result = await mock.complete("Test")
    assert result == "[mock-llm: no response configured]"


# =============================================================================
# MockGitHubService Tests
# =============================================================================


@pytest.mark.asyncio
async def test_mock_github_create_branch():
    """Test that create_branch adds branch to memory."""
    mock = MockGitHubService()
    result = await mock.create_branch(
        "testowner", "testrepo", "feature-branch", "abc123"
    )

    assert result["name"] == "feature-branch"
    assert result["sha"] == "abc123"
    assert "feature-branch" in mock.branches


@pytest.mark.asyncio
async def test_mock_github_create_pr():
    """Test that create_pull_request adds PR to memory."""
    mock = MockGitHubService()
    result = await mock.create_pull_request(
        "testowner", "testrepo", "My PR", "feature-branch", "main", "PR body"
    )

    assert result["title"] == "My PR"
    assert result["head"] == "feature-branch"
    assert result["base"] == "main"
    assert result["body"] == "PR body"
    assert result["number"] == 1
    assert len(mock.pull_requests) == 1


@pytest.mark.asyncio
async def test_mock_github_get_repository():
    """Test that get_repository returns mock repo info."""
    mock = MockGitHubService()
    result = await mock.get_repository("testowner", "testrepo")

    assert result["owner"] == "testowner"
    assert result["repo"] == "testrepo"
    assert result["default_branch"] == "main"


@pytest.mark.asyncio
async def test_mock_github_operations_log():
    """Test that operations are logged."""
    mock = MockGitHubService()
    await mock.create_branch("owner", "repo", "branch1", "sha1")
    await mock.create_pull_request("owner", "repo", "PR1", "branch1", "main")

    assert len(mock.operations) == 2
    assert mock.operations[0]["type"] == "create_branch"
    assert mock.operations[1]["type"] == "create_pull_request"


@pytest.mark.asyncio
async def test_mock_github_assert_helpers():
    """Test assertion helpers."""
    mock = MockGitHubService()

    # Should raise before any operations
    with pytest.raises(AssertionError):
        mock.assert_branch_created("feature-branch")

    with pytest.raises(AssertionError):
        mock.assert_pr_created("My PR")

    await mock.create_branch("owner", "repo", "feature-branch", "sha")
    await mock.create_pull_request("owner", "repo", "My PR", "feature-branch", "main")

    mock.assert_branch_created("feature-branch")  # Should pass
    mock.assert_pr_created("My PR")  # Should pass


# =============================================================================
# MockEventBus Tests
# =============================================================================


@pytest.mark.asyncio
async def test_mock_event_bus_publish():
    """Test that publish captures events."""
    mock = MockEventBus()
    event = SystemEvent(
        event_type="TEST_EVENT",
        entity_type="task",
        entity_id="123",
        payload={"key": "value"},
    )
    await mock.publish(event)

    assert len(mock.published_events) == 1
    assert mock.published_events[0].event_type == "TEST_EVENT"


@pytest.mark.asyncio
async def test_mock_event_bus_subscribe():
    """Test that subscribers are notified."""
    mock = MockEventBus()
    received = []

    async def callback(event):
        received.append(event)

    await mock.subscribe("TEST_EVENT", callback)

    event = SystemEvent(
        event_type="TEST_EVENT",
        entity_type="task",
        entity_id="123",
    )
    await mock.publish(event)

    assert len(received) == 1


@pytest.mark.asyncio
async def test_mock_event_bus_assert_event_published():
    """Test assert_event_published helper."""
    mock = MockEventBus()

    with pytest.raises(AssertionError):
        mock.assert_event_published("TEST_EVENT")

    event = SystemEvent(
        event_type="TEST_EVENT",
        entity_type="task",
        entity_id="123",
    )
    await mock.publish(event)

    mock.assert_event_published("TEST_EVENT")  # Should pass


@pytest.mark.asyncio
async def test_mock_event_bus_get_events_of_type():
    """Test get_events_of_type filtering."""
    mock = MockEventBus()

    await mock.publish(
        SystemEvent(event_type="TYPE_A", entity_type="task", entity_id="1")
    )
    await mock.publish(
        SystemEvent(event_type="TYPE_B", entity_type="task", entity_id="2")
    )
    await mock.publish(
        SystemEvent(event_type="TYPE_A", entity_type="task", entity_id="3")
    )

    type_a_events = mock.get_events_of_type("TYPE_A")
    assert len(type_a_events) == 2


@pytest.mark.asyncio
async def test_mock_event_bus_clear():
    """Test clear resets state."""
    mock = MockEventBus()
    await mock.publish(
        SystemEvent(event_type="TEST", entity_type="task", entity_id="1")
    )
    assert len(mock.published_events) == 1

    mock.clear()
    assert len(mock.published_events) == 0


# =============================================================================
# MockDaytonaService Tests
# =============================================================================


@pytest.mark.asyncio
async def test_mock_daytona_create_sandbox():
    """Test that create_sandbox adds to memory."""
    mock = MockDaytonaService()
    result = await mock.create_sandbox("workspace-123", image="python:3.11")

    assert result["workspace_id"] == "workspace-123"
    assert result["image"] == "python:3.11"
    assert result["status"] == "running"
    assert len(mock.sandboxes) == 1


@pytest.mark.asyncio
async def test_mock_daytona_delete_sandbox():
    """Test that delete_sandbox removes from memory."""
    mock = MockDaytonaService()
    result = await mock.create_sandbox("workspace-123")
    sandbox_id = result["id"]

    assert sandbox_id in mock.sandboxes

    success = await mock.delete_sandbox(sandbox_id)
    assert success is True
    assert sandbox_id not in mock.sandboxes

    # Deleting non-existent should return False
    success = await mock.delete_sandbox("non-existent")
    assert success is False


@pytest.mark.asyncio
async def test_mock_daytona_list_sandboxes():
    """Test that list_sandboxes returns all sandboxes."""
    mock = MockDaytonaService()
    await mock.create_sandbox("workspace-1")
    await mock.create_sandbox("workspace-2")

    sandboxes = await mock.list_sandboxes()
    assert len(sandboxes) == 2


@pytest.mark.asyncio
async def test_mock_daytona_assert_helper():
    """Test assert_sandbox_created helper."""
    mock = MockDaytonaService()

    with pytest.raises(AssertionError):
        mock.assert_sandbox_created()

    await mock.create_sandbox("workspace-123")

    mock.assert_sandbox_created()  # Should pass
    mock.assert_sandbox_created("workspace-123")  # Should pass

    with pytest.raises(AssertionError):
        mock.assert_sandbox_created("non-existent")


# =============================================================================
# MockStripeService Tests
# =============================================================================


@pytest.mark.asyncio
async def test_mock_stripe_create_customer():
    """Test that create_customer adds to memory."""
    mock = MockStripeService()
    result = await mock.create_customer("test@example.com", "Test User")

    assert result["email"] == "test@example.com"
    assert result["name"] == "Test User"
    assert result["id"].startswith("cus_")
    assert len(mock.customers) == 1


@pytest.mark.asyncio
async def test_mock_stripe_create_subscription():
    """Test that create_subscription adds to memory."""
    mock = MockStripeService()
    customer = await mock.create_customer("test@example.com")
    result = await mock.create_subscription(
        customer["id"], "price_123", items=["item1"]
    )

    assert result["customer"] == customer["id"]
    assert result["price"] == "price_123"
    assert result["status"] == "active"
    assert result["id"].startswith("sub_")
    assert len(mock.subscriptions) == 1


@pytest.mark.asyncio
async def test_mock_stripe_cancel_subscription():
    """Test that cancel_subscription updates status."""
    mock = MockStripeService()
    customer = await mock.create_customer("test@example.com")
    sub = await mock.create_subscription(customer["id"], "price_123")

    assert sub["status"] == "active"

    result = await mock.cancel_subscription(sub["id"])
    assert result["status"] == "canceled"


@pytest.mark.asyncio
async def test_mock_stripe_is_configured():
    """Test that is_configured returns True."""
    mock = MockStripeService()
    assert mock.is_configured is True


@pytest.mark.asyncio
async def test_mock_stripe_assert_helper():
    """Test assert_customer_created helper."""
    mock = MockStripeService()

    with pytest.raises(AssertionError):
        mock.assert_customer_created()

    await mock.create_customer("test@example.com")

    mock.assert_customer_created()  # Should pass
    mock.assert_customer_created("test@example.com")  # Should pass

    with pytest.raises(AssertionError):
        mock.assert_customer_created("other@example.com")


# =============================================================================
# Markers Tests
# =============================================================================


def test_markers_importable():
    """Test that all markers can be imported."""
    from tests.markers import (
        requires_daytona,
        requires_github,
        requires_llm,
        requires_redis,
        requires_stripe,
    )

    # Verify they are pytest markers
    assert hasattr(requires_llm, "markname")
    assert hasattr(requires_github, "markname")
    assert hasattr(requires_daytona, "markname")
    assert hasattr(requires_redis, "markname")
    assert hasattr(requires_stripe, "markname")
