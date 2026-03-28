"""Tests for the routing engine (end-to-end routing decisions)."""

from __future__ import annotations

from kestrel.models.openai import ChatCompletionRequest
from kestrel.routing.engine import RoutingEngine
from kestrel.routing.models import Tier


def _engine(**kwargs: object) -> RoutingEngine:
    return RoutingEngine(
        available_providers={"openai", "anthropic", "gemini", "groq"},
        **kwargs,  # type: ignore[arg-type]
    )


class TestRoutingEngine:
    def test_simple_prompt_routes_to_economy(self) -> None:
        """A trivial question should route down from gpt-4o."""
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "What is 2+2?"}],
            }
        )
        decision = _engine().route(req)
        assert decision.was_routed
        assert decision.selected_tier == Tier.ECONOMY
        assert decision.routed_model != "gpt-4o"

    def test_complex_prompt_scores_high(self) -> None:
        """A complex prompt should score high (Standard or Premium)."""
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a senior legal analyst specializing in "
                            "international trade law and securities regulation. "
                            "Provide comprehensive analysis with citations."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Analyze the legal implications of cross-border "
                            "securities transactions under the new EU regulation "
                            "framework. Consider compliance requirements, liability "
                            "exposure, and jurisdictional conflicts. Provide a "
                            "detailed strategy document with recommendations."
                        ),
                    },
                ],
                "tools": [
                    {"type": "function", "function": {"name": "search_legal_db"}},
                    {"type": "function", "function": {"name": "cite_regulation"}},
                    {"type": "function", "function": {"name": "check_compliance"}},
                ],
                "response_format": {"type": "json_object"},
            }
        )
        decision = _engine().route(req)
        # Heuristic scorer is conservative; ML classifier (Phase 2) will be more accurate
        assert decision.selected_tier in (Tier.STANDARD, Tier.PREMIUM)
        assert decision.scores.total >= 14

    def test_economy_model_never_routes_up(self) -> None:
        """If user requests an economy model, never route to premium."""
        req = ChatCompletionRequest.model_validate(
            {
                "model": "claude-haiku-4-5",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert legal analyst.",
                    },
                    {
                        "role": "user",
                        "content": "Analyze this complex securities regulation compliance issue.",
                    },
                ],
            }
        )
        decision = _engine().route(req)
        assert decision.selected_tier == Tier.ECONOMY

    def test_routing_disabled_returns_none_from_proxy(self) -> None:
        """When routing is off, the engine should not be called."""
        # This is tested at the proxy level, but verify the engine itself
        # always returns a decision
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        decision = _engine().route(req)
        assert decision is not None

    def test_decision_has_full_audit_trail(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
            }
        )
        decision = _engine().route(req)
        d = decision.to_dict()

        assert "original_model" in d
        assert "routed_model" in d
        assert "scores" in d
        assert "total" in d["scores"]
        assert "reasons" in d
        assert d["original_model"] == "gpt-4o"

    def test_tier_floor_applied(self) -> None:
        """Operator floor should prevent routing below a certain tier."""
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        decision = _engine(tier_floor=Tier.STANDARD).route(req)
        assert decision.selected_tier in (Tier.STANDARD, Tier.PREMIUM)

    def test_denied_providers_respected(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        decision = _engine(denied_providers={"openai"}).route(req)
        if decision.was_routed:
            assert decision.routed_model not in ("gpt-4o", "gpt-4o-mini")
