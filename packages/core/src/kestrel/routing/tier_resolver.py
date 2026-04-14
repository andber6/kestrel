"""Resolve scores to a tier, respecting the model ceiling."""

from __future__ import annotations

from kestrel.routing.models import RoutingScores, Tier

# Score range → tier mapping (scores are 5-25 from the scorer, but we handle
# out-of-range values defensively: <5 → ECONOMY, >25 → PREMIUM)
_TIER_THRESHOLDS: list[tuple[int, int, Tier]] = [
    (0, 8, Tier.ECONOMY),
    (9, 14, Tier.STANDARD),
    (15, 25, Tier.PREMIUM),
]

# Model → tier ceiling mapping. The requested model determines the max tier.
# Unknown models default to PREMIUM (safe — never accidentally downgrade).
_MODEL_TIER_MAP: dict[str, Tier] = {
    # Economy
    "gpt-4o-mini": Tier.STANDARD,
    "claude-haiku-4-5": Tier.ECONOMY,
    "gemini-2.5-flash": Tier.STANDARD,
    "gemini-2.5-flash-lite": Tier.ECONOMY,
    "llama-3.1-8b-instant": Tier.ECONOMY,
    "llama-3.1-70b-versatile": Tier.STANDARD,
    "mixtral-8x7b-32768": Tier.STANDARD,
    # Premium
    "gpt-4o": Tier.PREMIUM,
    "gpt-4-turbo": Tier.PREMIUM,
    "claude-sonnet-4-6": Tier.PREMIUM,
    "claude-opus-4-6": Tier.PREMIUM,
    "gemini-2.5-pro": Tier.PREMIUM,
    # Mistral
    "mistral-large-latest": Tier.PREMIUM,
    "mistral-medium-latest": Tier.STANDARD,
    "mistral-small-latest": Tier.STANDARD,
    "codestral-latest": Tier.PREMIUM,
    # Cohere
    "command-r-plus": Tier.PREMIUM,
    "command-r": Tier.STANDARD,
    "command-light": Tier.ECONOMY,
    # xAI
    "grok-2": Tier.PREMIUM,
    "grok-2-mini": Tier.STANDARD,
    "grok-3": Tier.PREMIUM,
    "grok-3-mini": Tier.STANDARD,
    "grok-4-0709": Tier.PREMIUM,
    # Together AI
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": Tier.ECONOMY,
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": Tier.STANDARD,
    "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": Tier.PREMIUM,
    # Groq
    "llama-3.3-70b-versatile": Tier.STANDARD,
}

_TIER_RANK = {Tier.ECONOMY: 0, Tier.STANDARD: 1, Tier.PREMIUM: 2}


def get_model_tier(model: str) -> Tier:
    """Get the tier/ceiling for a given model name."""
    return _MODEL_TIER_MAP.get(model, Tier.PREMIUM)


def score_to_tier(scores: RoutingScores) -> Tier:
    """Map a composite score to a tier."""
    total = scores.total
    for low, high, tier in _TIER_THRESHOLDS:
        if low <= total <= high:
            return tier
    return Tier.PREMIUM  # Scores above 25 (shouldn't happen)


def resolve_tier(
    scores: RoutingScores,
    requested_model: str,
    *,
    tier_floor: Tier | None = None,
    tier_ceiling: Tier | None = None,
) -> tuple[Tier, list[str]]:
    """Resolve the final tier, applying ceiling and floor constraints.

    Returns (tier, reasons) where reasons explain any clamping.
    """
    classified_tier = score_to_tier(scores)
    model_ceiling = get_model_tier(requested_model)
    reasons: list[str] = []

    final = classified_tier

    # Never exceed the model's tier (route cheaper, never more expensive)
    if _TIER_RANK[final] > _TIER_RANK[model_ceiling]:
        reasons.append(
            f"Clamped from {final.value} to {model_ceiling.value} "
            f"(model ceiling: {requested_model})"
        )
        final = model_ceiling

    # Apply operator ceiling if set
    if tier_ceiling and _TIER_RANK[final] > _TIER_RANK[tier_ceiling]:
        reasons.append(f"Clamped from {final.value} to {tier_ceiling.value} (operator ceiling)")
        final = tier_ceiling

    # Apply operator floor if set
    if tier_floor and _TIER_RANK[final] < _TIER_RANK[tier_floor]:
        reasons.append(f"Raised from {final.value} to {tier_floor.value} (operator floor)")
        final = tier_floor

    if not reasons and classified_tier != model_ceiling:
        reasons.append(f"Classified as {classified_tier.value} (score {scores.total}/25)")

    return final, reasons
