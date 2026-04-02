"""Rule-based scorer — heuristic complexity classification."""

from __future__ import annotations

from kestrel.routing.models import RequestFeatures, RoutingScores


def _clamp(value: int, lo: int = 1, hi: int = 5) -> int:
    return max(lo, min(hi, value))


class RuleBasedScorer:
    """Scores request complexity using structural heuristics.

    Each dimension is scored 1-5 based on thresholds derived from
    the request features. This is the open-source base scorer;
    the ML classifier (Phase 2) replaces it by implementing the
    same Scorer protocol.
    """

    def score(self, features: RequestFeatures) -> RoutingScores:
        return RoutingScores(
            reasoning_depth=self._score_reasoning(features),
            output_complexity=self._score_output(features),
            domain_specificity=self._score_domain(features),
            instruction_nuance=self._score_nuance(features),
            error_tolerance=self._score_error_tolerance(features),
        )

    def _score_reasoning(self, f: RequestFeatures) -> int:
        """How much multi-step reasoning is needed?"""
        score = 1

        # Longer prompts tend to require more reasoning
        if f.last_user_message_chars > 500:
            score += 1
        if f.last_user_message_chars > 1500:
            score += 1

        # Multi-turn conversations suggest iterative reasoning
        if f.conversation_depth >= 3:
            score += 1
        if f.conversation_depth >= 8:
            score += 1

        # Tool use implies multi-step reasoning
        if f.has_tools and f.tool_count >= 3:
            score += 1

        # Code blocks suggest technical reasoning
        if f.code_block_count >= 2:
            score += 1

        # Analytical keywords suggest complex reasoning
        if f.analytical_keyword_hits >= 1:
            score += 1
        if f.analytical_keyword_hits >= 3:
            score += 1

        # Technical keywords compound with analytical
        if f.technical_keyword_hits >= 3:
            score += 1

        return _clamp(score)

    def _score_output(self, f: RequestFeatures) -> int:
        """How complex is the expected output?"""
        score = 1

        # Short user messages usually expect short answers
        if f.last_user_message_chars > 300:
            score += 1
        if f.last_user_message_chars > 1000:
            score += 1

        # JSON mode suggests structured output
        if f.has_json_mode:
            score += 1

        # Tools suggest the model needs to produce structured function calls
        if f.has_tools:
            score += 1

        # Code in the conversation suggests code output expected
        if f.code_block_count >= 1:
            score += 1

        # Instruction keywords suggest detailed output expected
        if f.instruction_keyword_hits >= 1:
            score += 1
        if f.instruction_keyword_hits >= 3:
            score += 1

        return _clamp(score)

    def _score_domain(self, f: RequestFeatures) -> int:
        """Does this require specialized domain knowledge?"""
        score = 1

        # Domain keyword presence
        if f.domain_keyword_hits >= 1:
            score += 2
        if f.domain_keyword_hits >= 3:
            score += 1

        # Multiple domain categories = cross-domain complexity
        if len(f.domain_categories) >= 2:
            score += 1

        # Images may require vision capabilities
        if f.has_images:
            score += 1

        # Heavy technical keywords suggest specialized knowledge
        if f.technical_keyword_hits >= 2:
            score += 1
        if f.technical_keyword_hits >= 5:
            score += 1

        return _clamp(score)

    def _score_nuance(self, f: RequestFeatures) -> int:
        """How precisely must the model follow complex instructions?"""
        score = 1

        # Long system prompts = complex instruction sets
        if f.system_prompt_chars > 200:
            score += 1
        if f.system_prompt_chars > 800:
            score += 1
        if f.system_prompt_chars > 2000:
            score += 1

        # Many tools = complex decision space
        if f.tool_count >= 3:
            score += 1
        if f.tool_count >= 6:
            score += 1

        # JSON mode + tools = precise structured output needed
        if f.has_json_mode and f.has_tools:
            score += 1

        # Multiple questions suggest multi-part instructions
        if f.question_count >= 2:
            score += 1
        if f.question_count >= 4:
            score += 1

        # Instruction keywords signal precise output needed
        if f.instruction_keyword_hits >= 2:
            score += 1
        if f.instruction_keyword_hits >= 4:
            score += 1

        return _clamp(score)

    def _score_error_tolerance(self, f: RequestFeatures) -> int:
        """How costly is a slightly imperfect response?

        Higher score = lower tolerance for errors = needs better model.
        We can't know this from structure alone, so we use proxies.
        """
        score = 2  # Default: moderate tolerance

        # Domain-specific content is more error-sensitive
        if f.domain_keyword_hits >= 1:
            score += 1
        if len(f.domain_categories) >= 2:
            score += 1

        # Code output is verifiable but errors are costly
        if f.code_block_count >= 1:
            score += 1

        # Technical content needs accuracy
        if f.technical_keyword_hits >= 2:
            score += 1

        # Very short, simple prompts are low-stakes
        if (
            f.last_user_message_chars < 100
            and f.system_prompt_chars < 100
            and not f.has_tools
            and f.domain_keyword_hits == 0
            and f.technical_keyword_hits == 0
            and f.analytical_keyword_hits == 0
        ):
            score = 1

        return _clamp(score)
