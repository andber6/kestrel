"""Routing engine — orchestrates analysis, scoring, tier resolution, and model selection."""

from __future__ import annotations

import logging

from kestrel.models.openai import ChatCompletionRequest
from kestrel.routing.analyzer import analyze_request
from kestrel.routing.model_selector import select_model
from kestrel.routing.models import RoutingDecision, Scorer, Tier
from kestrel.routing.scorer import RuleBasedScorer
from kestrel.routing.tier_resolver import get_model_tier, resolve_tier

logger = logging.getLogger(__name__)


class RoutingEngine:
    """Decides which model to use for a given request.

    Orchestrates: analyze → score → resolve tier → select model.
    Pure computation, no I/O. Sub-millisecond.
    """

    def __init__(
        self,
        *,
        scorer: Scorer | None = None,
        available_providers: set[str] | None = None,
        allowed_providers: set[str] | None = None,
        denied_providers: set[str] | None = None,
        tier_floor: Tier | None = None,
        tier_ceiling: Tier | None = None,
    ) -> None:
        self._scorer = scorer or RuleBasedScorer()
        self._available_providers = available_providers or set()
        self._allowed_providers = allowed_providers
        self._denied_providers = denied_providers
        self._tier_floor = tier_floor
        self._tier_ceiling = tier_ceiling

    def route(self, request: ChatCompletionRequest) -> RoutingDecision:
        """Analyze the request and decide which model to use."""
        original_model = request.model
        original_tier = get_model_tier(original_model)

        # Step 1: Analyze
        features = analyze_request(request)

        # Step 2: Score
        scores = self._scorer.score(features)

        # Step 3: Resolve tier
        selected_tier, reasons = resolve_tier(
            scores,
            original_model,
            tier_floor=self._tier_floor,
            tier_ceiling=self._tier_ceiling,
        )

        # Step 4: Select model
        routed_model = select_model(
            selected_tier,
            self._available_providers,
            original_model=original_model,
            allowed_providers=self._allowed_providers,
            denied_providers=self._denied_providers,
        )

        was_routed = routed_model != original_model

        if was_routed:
            logger.info(
                "Routed %s → %s (tier: %s → %s, score: %d/25)",
                original_model,
                routed_model,
                original_tier.value,
                selected_tier.value,
                scores.total,
            )

        return RoutingDecision(
            original_model=original_model,
            routed_model=routed_model,
            original_tier=original_tier,
            selected_tier=selected_tier,
            was_routed=was_routed,
            scores=scores,
            reasons=reasons,
        )
