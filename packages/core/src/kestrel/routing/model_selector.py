"""Select the best concrete model for a given tier."""

from __future__ import annotations

from kestrel.routing.models import Tier

# Tier → ordered list of preferred models per tier
# First available model wins. These are ordered by quality/cost balance.
TIER_MODELS: dict[Tier, list[str]] = {
    Tier.ECONOMY: [
        "gpt-4o-mini",
        "claude-haiku-4-5",
        "gemini-2.5-flash",
        "llama-3.1-8b-instant",
        "command-light",
    ],
    Tier.STANDARD: [
        "gpt-4o-mini",
        "claude-haiku-4-5",
        "gemini-2.5-flash",
        "mistral-small-latest",
        "command-r",
        "llama-3.1-70b-versatile",
    ],
    Tier.PREMIUM: [
        "gpt-4o",
        "claude-sonnet-4-6",
        "gemini-2.5-pro",
        "mistral-large-latest",
        "command-r-plus",
        "grok-3",
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

    Prefers same-provider models first (e.g. claude-sonnet → claude-haiku),
    then falls back to cross-provider if the original provider is unavailable.

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
    original_provider = _model_to_provider(original_model)

    def _is_eligible(model: str) -> bool:
        provider = _model_to_provider(model)
        if provider is None:
            return False
        if provider not in available_providers:
            return False
        if allowed_providers and provider not in allowed_providers:
            return False
        return not (denied_providers and provider in denied_providers)

    # First pass: prefer a model from the same provider
    if original_provider:
        for model in candidates:
            if _model_to_provider(model) == original_provider and _is_eligible(model):
                return model

    # Second pass: fall back to any eligible provider
    for model in candidates:
        if _is_eligible(model):
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
    if model_lower.startswith(("mistral-", "codestral", "pixtral")):
        return "mistral"
    if model_lower.startswith("command-"):
        return "cohere"
    if model_lower.startswith("grok-"):
        return "xai"
    if "/" in model_lower:  # Together AI uses org/model format
        return "together"
    return None
