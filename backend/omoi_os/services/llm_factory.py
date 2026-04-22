"""Factory for creating LLM services based on mode configuration.

This module provides a factory function that creates the appropriate LLM service
based on the mode setting in LLMSettings:
- "live": Standard LLM service (default)
- "record": Wraps a live service and records responses to disk
- "replay": Returns cached responses from disk recordings
- "null": Returns placeholder responses without making API calls

Usage:
    from omoi_os.services.llm_factory import create_llm_service

    # Create service based on config mode
    llm = create_llm_service()

    # Or with explicit settings
    from omoi_os.config import LLMSettings
    settings = LLMSettings(mode="null")
    llm = create_llm_service(settings)
"""

from omoi_os.config import LLMSettings, get_app_settings
from omoi_os.logging import get_logger

logger = get_logger(__name__)


def create_llm_service(settings: LLMSettings | None = None):
    """Create the appropriate LLM service based on mode config.

    Args:
        settings: Optional LLM settings. If not provided, loads from app config.

    Returns:
        An LLM service instance matching the configured mode:
        - NullLLMService for "null" mode
        - ReplayLLMService for "replay" mode
        - RecordingLLMService for "record" mode (wraps live service)
        - LLMService for "live" mode (default)

    Example:
        >>> llm = create_llm_service()
        >>> result = await llm.complete("Hello!")
    """
    settings = settings or get_app_settings().llm
    mode = settings.mode

    if mode == "null":
        from omoi_os.services.null_llm_service import NullLLMService

        logger.info(f"Creating NullLLMService (mode: {mode})")
        return NullLLMService()
    elif mode == "replay":
        from omoi_os.services.replay_llm_service import ReplayLLMService

        logger.info(
            f"Creating ReplayLLMService (mode: {mode}, dir: {settings.recording_dir}, strict: {settings.replay_strict})"
        )
        return ReplayLLMService(
            recording_dir=settings.recording_dir, strict=settings.replay_strict
        )
    elif mode == "record":
        from omoi_os.services.llm_service import LLMService
        from omoi_os.services.recording_llm_service import RecordingLLMService

        logger.info(
            f"Creating RecordingLLMService (mode: {mode}, dir: {settings.recording_dir})"
        )
        inner = LLMService(settings=settings)
        return RecordingLLMService(inner=inner, recording_dir=settings.recording_dir)
    else:
        # "live" mode (default) - current behavior
        from omoi_os.services.llm_service import LLMService

        logger.info(f"Creating LLMService (mode: {mode})")
        return LLMService(settings=settings)
