"""Recording LLM service that wraps a live service and saves responses to disk.

This service wraps an inner LLM service (typically a live one) and records all
prompt/response pairs to disk as JSON files. The recordings can then be replayed
using ReplayLLMService.

Recording format:
{
    "hash": "a1b2c3...",
    "model": "...",
    "prompt": "...",
    "output_type": "ClassName" (or "__complete__" for complete()),
    "response": { ... } (model_dump for structured, plain string for complete),
    "recorded_at": "ISO timestamp",
    "latency_ms": 1234
}
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional, TypeVar

from pydantic import BaseModel

from omoi_os.logging import get_logger
from omoi_os.utils.datetime import utc_now

logger = get_logger(__name__)

T = TypeVar("T")


class RecordingLLMService:
    """LLM service that records all calls to disk for later replay.

    Wraps an inner LLM service and saves all prompt/response pairs to disk.
    The recordings can be used with ReplayLLMService for deterministic testing.
    """

    def __init__(self, inner, recording_dir: str):
        """Initialize the recording service.

        Args:
            inner: The inner LLM service to wrap (typically a live LLMService)
            recording_dir: Directory where recordings will be saved
        """
        self.inner = inner
        self.recording_dir = Path(recording_dir)

        # Create recording directory if it doesn't exist
        self.recording_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"RecordingLLMService initialized, saving to: {recording_dir}")

    def _compute_hash(self, model: str, output_type_name: str, prompt: str) -> str:
        """Compute the hash key for a given request.

        Args:
            model: Model identifier
            output_type_name: Name of the output type (or "__complete__" for complete())
            prompt: The prompt text

        Returns:
            16-character hex hash string
        """
        key = f"{model}::{output_type_name}::{prompt}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def _get_model_or_default(self) -> str:
        """Get the model identifier from the inner service.

        Returns:
            Model string
        """
        # Try to get the model from inner service settings
        if hasattr(self.inner, "settings") and self.inner.settings:
            return getattr(self.inner.settings, "model", "unknown/default")
        return "unknown/default"

    def _save_recording(
        self,
        hash_key: str,
        model: str,
        prompt: str,
        output_type_name: str,
        response: any,
        latency_ms: int,
    ) -> None:
        """Save a recording to disk.

        Args:
            hash_key: The hash key for this request
            model: Model identifier
            prompt: The prompt text
            output_type_name: Name of the output type
            response: The response data (Pydantic model dict or string)
            latency_ms: Request latency in milliseconds
        """
        recording = {
            "hash": hash_key,
            "model": model,
            "prompt": prompt,
            "output_type": output_type_name,
            "response": response,
            "recorded_at": utc_now().isoformat(),
            "latency_ms": latency_ms,
        }

        file_path = self.recording_dir / f"{hash_key}.json"
        try:
            with open(file_path, "w") as f:
                json.dump(recording, f, indent=2)
            logger.debug(f"Saved recording: {file_path.name}")
        except Exception as e:
            logger.warning(f"Failed to save recording to {file_path}: {e}")

    async def complete(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """Call inner service and record the response.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional arguments passed to inner service

        Returns:
            Text response from the inner service
        """
        start_time = time.monotonic()

        # Call inner service
        response = await self.inner.complete(prompt, system_prompt, **kwargs)

        # Calculate latency
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Record the call
        model = self._get_model_or_default()
        hash_key = self._compute_hash(model, "__complete__", prompt)
        self._save_recording(
            hash_key=hash_key,
            model=model,
            prompt=prompt,
            output_type_name="__complete__",
            response=response,
            latency_ms=latency_ms,
        )

        logger.info(
            f"RecordingLLMService: recorded complete() call (hash: {hash_key}, latency: {latency_ms}ms)"
        )

        return response

    async def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        system_prompt: Optional[str] = None,
        output_retries: int = 5,
        http_retries: int = 3,
        **kwargs,
    ) -> T:
        """Call inner service and record the response.

        Args:
            prompt: User prompt
            output_type: Pydantic model class for structured output
            system_prompt: Optional system prompt
            output_retries: Number of retries for structured output validation
            http_retries: Number of retries for transient HTTP errors
            **kwargs: Additional arguments passed to inner service

        Returns:
            Structured response from the inner service
        """
        start_time = time.monotonic()

        # Call inner service
        response = await self.inner.structured_output(
            prompt, output_type, system_prompt, output_retries, http_retries, **kwargs
        )

        # Calculate latency
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Serialize response
        if isinstance(response, BaseModel):
            response_data = response.model_dump(mode="json")
        else:
            response_data = response

        # Record the call
        model = self._get_model_or_default()
        output_type_name = output_type.__name__
        hash_key = self._compute_hash(model, output_type_name, prompt)
        self._save_recording(
            hash_key=hash_key,
            model=model,
            prompt=prompt,
            output_type_name=output_type_name,
            response=response_data,
            latency_ms=latency_ms,
        )

        logger.info(
            f"RecordingLLMService: recorded {output_type_name} call (hash: {hash_key}, latency: {latency_ms}ms)"
        )

        return response
