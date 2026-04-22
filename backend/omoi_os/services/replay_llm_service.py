"""Replay LLM service that returns cached responses from disk recordings.

This service loads previously recorded LLM responses from disk and replays them
without making any API calls. Useful for:
- Deterministic testing with known responses
- CI/CD pipelines where you want consistent results
- Local development with recorded responses
"""

import hashlib
import json
from pathlib import Path
from typing import Optional, TypeVar

from pydantic import BaseModel

from omoi_os.logging import get_logger
from omoi_os.services.null_llm_service import NullLLMService

logger = get_logger(__name__)

T = TypeVar("T")


class ReplayLLMService:
    """LLM service that replays cached responses from disk recordings.

    Loads all .json recording files from the recording directory on initialization.
    Uses SHA256 hashes of (model + output_type + prompt) as cache keys.

    On cache miss:
    - If strict=True: raises LookupError
    - If strict=False: returns placeholder (like NullLLMService)
    """

    def __init__(self, recording_dir: str, strict: bool = False):
        """Initialize the replay service and load recordings from disk.

        Args:
            recording_dir: Directory containing .json recording files
            strict: If True, raise LookupError on cache miss; if False, return placeholder
        """
        self.recording_dir = Path(recording_dir)
        self.strict = strict
        self._cache: dict[str, dict] = {}
        self._null_service = NullLLMService()

        self._load_recordings()
        logger.info(
            f"ReplayLLMService initialized with {len(self._cache)} recordings from {recording_dir}"
        )

    def _load_recordings(self) -> None:
        """Load all recording files from the recording directory."""
        if not self.recording_dir.exists():
            logger.warning(f"Recording directory does not exist: {self.recording_dir}")
            return

        for file_path in self.recording_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    recording = json.load(f)
                    hash_key = recording.get("hash")
                    if hash_key:
                        self._cache[hash_key] = recording
                        logger.debug(
                            f"Loaded recording: {file_path.name} (hash: {hash_key})"
                        )
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse recording file {file_path}: {e}")
            except Exception as e:
                logger.warning(f"Failed to load recording file {file_path}: {e}")

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
        """Get the model identifier to use for hashing.

        Returns:
            Model string (in replay mode, we use a default)
        """
        # In replay mode, we use a consistent model identifier
        # The actual model isn't used since we're not making API calls
        return "replay/default"

    async def complete(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """Return a cached text response or placeholder.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (ignored for replay)
            **kwargs: Additional arguments (ignored)

        Returns:
            Cached text response, or placeholder if not found

        Raises:
            LookupError: If strict=True and no cached response found
        """
        model = self._get_model_or_default()
        hash_key = self._compute_hash(model, "__complete__", prompt)

        if hash_key in self._cache:
            recording = self._cache[hash_key]
            logger.info(
                f"ReplayLLMService: cache HIT for complete() (hash: {hash_key})"
            )
            return recording.get("response", "[replay: empty response]")

        logger.info(f"ReplayLLMService: cache MISS for complete() (hash: {hash_key})")

        if self.strict:
            raise LookupError(
                f"No cached response found for complete() call. "
                f"Hash: {hash_key}, prompt: {prompt[:100]}..."
            )

        return await self._null_service.complete(prompt, system_prompt, **kwargs)

    async def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        system_prompt: Optional[str] = None,
        output_retries: int = 5,
        http_retries: int = 3,
        **kwargs,
    ) -> T:
        """Return a cached structured response or placeholder.

        Args:
            prompt: User prompt
            output_type: Pydantic model class for structured output
            system_prompt: Optional system prompt (ignored for replay)
            output_retries: Number of retries for structured output validation (ignored)
            http_retries: Number of retries for transient HTTP errors (ignored)
            **kwargs: Additional arguments (ignored)

        Returns:
            Cached structured response, or placeholder if not found

        Raises:
            LookupError: If strict=True and no cached response found
        """
        model = self._get_model_or_default()
        output_type_name = output_type.__name__
        hash_key = self._compute_hash(model, output_type_name, prompt)

        if hash_key in self._cache:
            recording = self._cache[hash_key]
            response_data = recording.get("response", {})
            logger.info(
                f"ReplayLLMService: cache HIT for {output_type_name} (hash: {hash_key})"
            )

            try:
                if issubclass(output_type, BaseModel):
                    return output_type.model_validate(response_data)
                else:
                    # For non-Pydantic types, return the response directly
                    return response_data
            except Exception as e:
                logger.warning(f"Failed to deserialize cached response: {e}")
                if self.strict:
                    raise LookupError(
                        f"Cached response deserialization failed for {output_type_name}. "
                        f"Hash: {hash_key}, error: {e}"
                    )
                return await self._null_service.structured_output(
                    prompt,
                    output_type,
                    system_prompt,
                    output_retries,
                    http_retries,
                    **kwargs,
                )

        logger.info(
            f"ReplayLLMService: cache MISS for {output_type_name} (hash: {hash_key})"
        )

        if self.strict:
            raise LookupError(
                f"No cached response found for {output_type_name}. "
                f"Hash: {hash_key}, prompt: {prompt[:100]}..."
            )

        return await self._null_service.structured_output(
            prompt, output_type, system_prompt, output_retries, http_retries, **kwargs
        )
