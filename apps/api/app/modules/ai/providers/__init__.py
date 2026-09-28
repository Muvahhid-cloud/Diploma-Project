"""Provider selection (AI_PROVIDER). The rest of the code asks `get_ai_provider()` only."""

from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import Settings, get_settings
from app.modules.ai.errors import AIConfigurationError
from app.modules.ai.providers.base import AIProvider
from app.modules.ai.providers.mock import MockAIProvider

_cached: AIProvider | None = None
_override: AIProvider | None = None


def create_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "mock":
        return MockAIProvider()
    if settings.ai_provider == "anthropic":
        if settings.anthropic_api_key is None or not settings.ai_model:
            raise AIConfigurationError("anthropic: ANTHROPIC_API_KEY and AI_MODEL are required")
        # Imported here so the SDK is loaded only when the provider is actually used.
        from app.modules.ai.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.ai_model,
            base_url=settings.anthropic_base_url,
            timeout_s=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
            effort=settings.ai_effort,
        )
    raise AIConfigurationError(f"unknown AI_PROVIDER {settings.ai_provider!r}")


def get_ai_provider() -> AIProvider:
    global _cached
    if _override is not None:
        return _override
    if _cached is None:
        _cached = create_provider(get_settings())
    return _cached


@contextmanager
def use_ai_provider(provider: AIProvider) -> Iterator[AIProvider]:
    """Temporarily replace the configured provider (tests)."""
    global _override
    previous, _override = _override, provider
    try:
        yield provider
    finally:
        _override = previous
