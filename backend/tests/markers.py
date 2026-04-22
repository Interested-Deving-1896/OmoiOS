"""Pytest markers for skipping tests based on environment capabilities."""

import os

import pytest

requires_llm = pytest.mark.skipif(
    not os.getenv("FIREWORKS_API_KEY") and not os.getenv("LLM_API_KEY"),
    reason="Requires LLM API key (set FIREWORKS_API_KEY or LLM_API_KEY)",
)

requires_github = pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="Requires GitHub token (set GITHUB_TOKEN)",
)

requires_daytona = pytest.mark.skipif(
    not os.getenv("DAYTONA_API_KEY"),
    reason="Requires Daytona API key (set DAYTONA_API_KEY)",
)

requires_redis = pytest.mark.skipif(
    not os.getenv("REDIS_URL"),
    reason="Requires Redis (set REDIS_URL or start Redis)",
)

requires_stripe = pytest.mark.skipif(
    not os.getenv("STRIPE_API_KEY"),
    reason="Requires Stripe API key (set STRIPE_API_KEY)",
)
