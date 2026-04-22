"""Mock LLM service for testing.

Provides typed mock implementations for LLM calls with call tracking
and configurable responses.
"""

from typing import Any, TypeVar

from omoi_os.services.null_llm_service import NullLLMService

T = TypeVar("T")


class MockLLMService:
    """Mock LLM service with call tracking and configurable responses.

    Tracks all calls and returns canned or default responses.
    Useful for testing workflows that depend on LLM calls without
    making actual API requests.
    """

    def __init__(self):
        """Initialize the mock LLM service."""
        self.calls: list[dict] = []
        self._responses: dict[str, Any] = {}
        self._default_responses: dict[type, Any] = {}
        self._complete_response: str = "[mock-llm: no response configured]"
        self._null_service = NullLLMService()

    def set_response(self, output_type: type, response: Any) -> None:
        """Set a canned response for a specific output type.

        Args:
            output_type: The Pydantic model type to respond to
            response: The response to return for this type
        """
        self._default_responses[output_type] = response

    def set_response_for_prompt(self, prompt_contains: str, response: Any) -> None:
        """Set a response triggered by prompt content.

        Args:
            prompt_contains: Substring to match in prompts
            response: The response to return when prompt contains this substring
        """
        self._responses[prompt_contains] = response

    def set_complete_response(self, response: str) -> None:
        """Set the response for complete() calls.

        Args:
            response: The string to return from complete()
        """
        self._complete_response = response

    async def complete(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> str:
        """Return a configured string response.

        Args:
            prompt: User prompt (tracked)
            system_prompt: Optional system prompt (tracked)
            **kwargs: Additional arguments (tracked)

        Returns:
            Configured response or default string
        """
        self.calls.append(
            {
                "method": "complete",
                "prompt": prompt,
                "system_prompt": system_prompt,
                "kwargs": kwargs,
            }
        )

        # Check for prompt-specific response
        for prompt_match, response in self._responses.items():
            if prompt_match in prompt and isinstance(response, str):
                return response

        return self._complete_response

    async def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        system_prompt: str | None = None,
        output_retries: int = 5,
        http_retries: int = 3,
        **kwargs,
    ) -> T:
        """Return a configured or placeholder response.

        Args:
            prompt: User prompt (tracked)
            output_type: Pydantic model class for structured output
            system_prompt: Optional system prompt (tracked)
            output_retries: Number of retries for structured output validation (tracked)
            http_retries: Number of retries for transient HTTP errors (tracked)
            **kwargs: Additional arguments (tracked)

        Returns:
            Configured response, type-specific default, or placeholder instance
        """
        self.calls.append(
            {
                "method": "structured_output",
                "prompt": prompt,
                "output_type": output_type,
                "system_prompt": system_prompt,
                "output_retries": output_retries,
                "http_retries": http_retries,
                "kwargs": kwargs,
            }
        )

        # Check for prompt-specific response
        for prompt_match, response in self._responses.items():
            if prompt_match in prompt:
                if isinstance(response, output_type):
                    return response

        # Check for type-specific response
        if output_type in self._default_responses:
            return self._default_responses[output_type]

        # Fall back to placeholder generation using NullLLMService logic
        return self._null_service._create_placeholder_instance(output_type)

    def assert_called_with_type(self, output_type: type) -> None:
        """Assert that structured_output was called with a specific type.

        Args:
            output_type: The expected output type

        Raises:
            AssertionError: If no call with the specified type was made
        """
        for call in self.calls:
            if call.get("method") == "structured_output":
                if call.get("output_type") == output_type:
                    return
        raise AssertionError(
            f"structured_output was not called with output_type={output_type}"
        )

    def assert_call_count(self, expected: int) -> None:
        """Assert the total call count.

        Args:
            expected: Expected number of calls

        Raises:
            AssertionError: If call count doesn't match expected
        """
        actual = len(self.calls)
        if actual != expected:
            raise AssertionError(f"Expected {expected} calls, got {actual}")

    def reset(self) -> None:
        """Clear all call history and configured responses."""
        self.calls.clear()
        self._responses.clear()
        self._default_responses.clear()
        self._complete_response = "[mock-llm: no response configured]"
