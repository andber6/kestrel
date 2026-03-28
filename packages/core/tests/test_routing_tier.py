"""Tests for tier resolution and model selection."""

from __future__ import annotations

from kestrel.routing.model_selector import select_model
from kestrel.routing.models import RoutingScores, Tier
from kestrel.routing.tier_resolver import (
    get_model_tier,
    resolve_tier,
    score_to_tier,
)


class TestScoreToTier:
    def test_economy_range(self) -> None:
        for total in range(5, 10):
            scores = RoutingScores(
                reasoning_depth=1,
                output_complexity=1,
                domain_specificity=1,
                instruction_nuance=1,
                error_tolerance=total - 4,
            )
            assert score_to_tier(scores) == Tier.ECONOMY

    def test_standard_range(self) -> None:
        scores = RoutingScores(
            reasoning_depth=2,
            output_complexity=3,
            domain_specificity=2,
            instruction_nuance=2,
            error_tolerance=2,
        )
        assert scores.total == 11
        assert score_to_tier(scores) == Tier.STANDARD

    def test_premium_range(self) -> None:
        scores = RoutingScores(
            reasoning_depth=4,
            output_complexity=4,
            domain_specificity=3,
            instruction_nuance=3,
            error_tolerance=4,
        )
        assert scores.total == 18
        assert score_to_tier(scores) == Tier.PREMIUM


class TestModelTier:
    def test_gpt4o_is_premium(self) -> None:
        assert get_model_tier("gpt-4o") == Tier.PREMIUM

    def test_gpt4o_mini_is_standard(self) -> None:
        assert get_model_tier("gpt-4o-mini") == Tier.STANDARD

    def test_claude_haiku_is_economy(self) -> None:
        assert get_model_tier("claude-haiku-4-5") == Tier.ECONOMY

    def test_unknown_model_is_premium(self) -> None:
        assert get_model_tier("some-unknown-model") == Tier.PREMIUM


class TestResolveTier:
    def test_economy_score_with_premium_model_routes_down(self) -> None:
        scores = RoutingScores(
            reasoning_depth=1,
            output_complexity=1,
            domain_specificity=1,
            instruction_nuance=1,
            error_tolerance=1,
        )
        tier, reasons = resolve_tier(scores, "gpt-4o")
        assert tier == Tier.ECONOMY
        assert any("economy" in r.lower() for r in reasons)

    def test_premium_score_with_economy_model_clamps(self) -> None:
        scores = RoutingScores(
            reasoning_depth=5,
            output_complexity=4,
            domain_specificity=3,
            instruction_nuance=3,
            error_tolerance=4,
        )
        tier, reasons = resolve_tier(scores, "claude-haiku-4-5")
        assert tier == Tier.ECONOMY
        assert any("clamped" in r.lower() for r in reasons)

    def test_floor_raises_tier(self) -> None:
        scores = RoutingScores(
            reasoning_depth=1,
            output_complexity=1,
            domain_specificity=1,
            instruction_nuance=1,
            error_tolerance=1,
        )
        tier, reasons = resolve_tier(scores, "gpt-4o", tier_floor=Tier.STANDARD)
        assert tier == Tier.STANDARD
        assert any("floor" in r.lower() for r in reasons)

    def test_operator_ceiling_clamps(self) -> None:
        scores = RoutingScores(
            reasoning_depth=4,
            output_complexity=4,
            domain_specificity=3,
            instruction_nuance=3,
            error_tolerance=4,
        )
        tier, reasons = resolve_tier(scores, "gpt-4o", tier_ceiling=Tier.STANDARD)
        assert tier == Tier.STANDARD


class TestModelSelector:
    def test_selects_economy_model(self) -> None:
        model = select_model(
            Tier.ECONOMY,
            {"openai", "anthropic", "groq"},
            original_model="gpt-4o",
        )
        assert model in ("gpt-4o-mini", "claude-haiku-4-5", "llama-3.1-8b-instant")

    def test_selects_from_available_providers_only(self) -> None:
        model = select_model(
            Tier.ECONOMY,
            {"groq"},  # Only Groq available
            original_model="gpt-4o",
        )
        assert model == "llama-3.1-8b-instant"

    def test_falls_back_to_original_when_no_providers(self) -> None:
        model = select_model(
            Tier.ECONOMY,
            set(),  # No providers
            original_model="gpt-4o",
        )
        assert model == "gpt-4o"

    def test_respects_denied_providers(self) -> None:
        model = select_model(
            Tier.ECONOMY,
            {"openai", "anthropic", "groq"},
            original_model="gpt-4o",
            denied_providers={"openai"},
        )
        assert model != "gpt-4o-mini"  # OpenAI denied

    def test_respects_allowed_providers(self) -> None:
        model = select_model(
            Tier.PREMIUM,
            {"openai", "anthropic", "gemini"},
            original_model="gpt-4o",
            allowed_providers={"anthropic"},
        )
        assert model == "claude-sonnet-4-6"
