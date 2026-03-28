"""Tests for rule-based scorer."""

from __future__ import annotations

from agentrouter.routing.models import RequestFeatures
from agentrouter.routing.scorer import RuleBasedScorer


def _scorer() -> RuleBasedScorer:
    return RuleBasedScorer()


class TestScorer:
    def test_simple_request_scores_low(self) -> None:
        """Short, simple prompt with no tools/domain keywords → low score."""
        features = RequestFeatures(
            total_message_count=1,
            user_message_count=1,
            last_user_message_chars=20,
            system_prompt_chars=0,
        )
        scores = _scorer().score(features)
        assert scores.total <= 9  # Economy tier

    def test_complex_request_scores_high(self) -> None:
        """Long prompt with tools, code, domain keywords → high score."""
        features = RequestFeatures(
            total_message_count=10,
            user_message_count=5,
            last_user_message_chars=2000,
            system_prompt_chars=1500,
            conversation_depth=4,
            has_tools=True,
            tool_count=5,
            has_json_mode=True,
            code_block_count=3,
            domain_keyword_hits=3,
            domain_categories=["legal", "financial"],
        )
        scores = _scorer().score(features)
        assert scores.total >= 17  # Premium tier

    def test_moderate_request_scores_mid(self) -> None:
        """Medium prompt with some complexity signals → mid score."""
        features = RequestFeatures(
            total_message_count=5,
            user_message_count=3,
            last_user_message_chars=600,
            system_prompt_chars=500,
            conversation_depth=3,
            has_tools=True,
            tool_count=3,
            code_block_count=1,
        )
        scores = _scorer().score(features)
        assert 10 <= scores.total <= 16  # Standard tier

    def test_all_scores_are_1_to_5(self) -> None:
        """No dimension should be outside the 1-5 range."""
        features = RequestFeatures(
            total_message_count=100,
            user_message_count=50,
            last_user_message_chars=50000,
            system_prompt_chars=10000,
            conversation_depth=50,
            has_tools=True,
            tool_count=20,
            has_json_mode=True,
            has_images=True,
            code_block_count=20,
            domain_keyword_hits=10,
            domain_categories=["legal", "medical", "financial", "security"],
        )
        scores = _scorer().score(features)
        for dim in [
            scores.reasoning_depth,
            scores.output_complexity,
            scores.domain_specificity,
            scores.instruction_nuance,
            scores.error_tolerance,
        ]:
            assert 1 <= dim <= 5

    def test_empty_request_scores_minimum(self) -> None:
        features = RequestFeatures()
        scores = _scorer().score(features)
        assert scores.total == 5  # All 1s except error_tolerance defaults to 2
        assert scores.total <= 9
