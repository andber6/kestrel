"""Data models for the routing system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class Tier(StrEnum):
    """Model quality/cost tier."""

    ECONOMY = "economy"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass(frozen=True)
class RequestFeatures:
    """Structural features extracted from a chat completion request."""

    # Message analysis
    total_message_count: int = 0
    user_message_count: int = 0
    total_char_count: int = 0
    last_user_message_chars: int = 0
    system_prompt_chars: int = 0
    avg_message_chars: float = 0.0
    conversation_depth: int = 0  # number of user↔assistant turns

    # Complexity signals
    has_tools: bool = False
    tool_count: int = 0
    has_json_mode: bool = False
    has_images: bool = False
    code_block_count: int = 0

    # Keyword signals
    domain_keyword_hits: int = 0
    domain_categories: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RoutingScores:
    """Scores for the 5 routing dimensions (each 1-5)."""

    reasoning_depth: int = 1
    output_complexity: int = 1
    domain_specificity: int = 1
    instruction_nuance: int = 1
    error_tolerance: int = 1

    @property
    def total(self) -> int:
        return (
            self.reasoning_depth
            + self.output_complexity
            + self.domain_specificity
            + self.instruction_nuance
            + self.error_tolerance
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "reasoning_depth": self.reasoning_depth,
            "output_complexity": self.output_complexity,
            "domain_specificity": self.domain_specificity,
            "instruction_nuance": self.instruction_nuance,
            "error_tolerance": self.error_tolerance,
            "total": self.total,
        }


@dataclass(frozen=True)
class RoutingDecision:
    """The complete routing decision with audit trail."""

    original_model: str
    routed_model: str
    original_tier: Tier
    selected_tier: Tier
    was_routed: bool  # True if model was changed
    scores: RoutingScores
    reasons: list[str]  # Human-readable explanations

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_model": self.original_model,
            "routed_model": self.routed_model,
            "original_tier": self.original_tier.value,
            "selected_tier": self.selected_tier.value,
            "was_routed": self.was_routed,
            "scores": self.scores.to_dict(),
            "reasons": self.reasons,
        }


class Scorer(Protocol):
    """Protocol for scoring a request's complexity.

    The rule-based scorer (Week 3) and ML classifier (Phase 2)
    both implement this protocol.
    """

    def score(self, features: RequestFeatures) -> RoutingScores: ...
