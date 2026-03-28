"""Select the best concrete model for a given tier."""

from __future__ import annotations

from agentrouter.routing.models import Tier

# Tier → ordered list of preferred models per tier
# First available model wins. These are ordered by quality/cost balance.
TIER_MODELS: dict[Tier, list[str]] = {
    Tier.ECONOMY: [
        "gpt-4o-mini",
        "claude-haiku-4-5",
        "gemini-1.5-flash",
        "llama-3.1-8b-instant",
    ],
    Tier.STANDARD: [
        "gpt-4o-mini",
        "claude-haiku-4-5",
        "gemini-1.5-flash",
        "llama-3.1-70b-versatile",
    ],
    Tier.PREMIUM: [
        "gpt-4o",
        "claude-sonnet-4-6",
        "gemini-1.5-pro",
    ],
}


def select_model(
    tier: Tier,
    available_providers: set[str],
    *,
    original_model: str,
    allowed_providers: set[str] | None = None,
    denied_providers: set[str] | None = None,
) -> str:
    """Pick the best model for the tier from available providers.

    Args:
        tier: The target tier.
        available_providers: Set of provider names that are registered and healthy.
        original_model: The model the operator originally requested (fallback).
        allowed_providers: If set, only these providers are considered.
        denied_providers: If set, these providers are excluded.

    Returns:
        The selected model name, or the original model if no routing is possible.
    """
    candidates = TIER_MODELS.get(tier, [])

    for model in candidates:
        provider = _model_to_provider(model)
        if provider is None:
            continue
        if provider not in available_providers:
            continue
        if allowed_providers and provider not in allowed_providers:
            continue
        if denied_providers and provider in denied_providers:
            continue
        return model

    # No suitable model found for this tier — keep original
    return original_model


def _model_to_provider(model: str) -> str | None:
    """Quick model→provider resolution for the known models."""
    model_lower = model.lower()
    if model_lower.startswith("gpt-") or model_lower.startswith(("o1", "o3", "o4")):
        return "openai"
    if model_lower.startswith("claude-"):
        return "anthropic"
    if model_lower.startswith("gemini-"):
        return "gemini"
    if model_lower.startswith(("llama", "mixtral", "gemma")):
        return "groq"
    return None
