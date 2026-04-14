# Routing

Kestrel analyzes every incoming request and decides whether a cheaper model can handle it. This page explains how the routing pipeline works.

## Overview

```
Request → Analyze → Score → Resolve Tier → Select Model → Forward
```

1. **Analyze**: Extract structural features from the request
2. **Score**: Rate complexity across 5 dimensions (1-5 each)
3. **Resolve Tier**: Map the composite score to a tier, apply ceiling
4. **Select Model**: Pick the cheapest available model for the tier
5. **Forward**: Translate format and send to the selected provider

The entire pipeline is pure CPU computation — no API calls, no I/O. It runs in sub-millisecond time.

## The Five Scoring Dimensions

### 1. Reasoning Depth (1-5)

Does the task require multi-step logical reasoning?

| Score | Example |
|-------|---------|
| 1 | "What is 2+2?", "Format this as a date" |
| 3 | "Summarize this article in 3 points" |
| 5 | "Analyze the strategic implications of this acquisition" |

**Heuristic signals**: prompt length, conversation depth, tool count, code block count

### 2. Output Complexity (1-5)

How complex is the expected output?

| Score | Example |
|-------|---------|
| 1 | Yes/no, a number, a single word |
| 3 | A paragraph, a short list, an email |
| 5 | A multi-section report, a full code module |

**Heuristic signals**: prompt length, JSON mode, tool presence, code blocks

### 3. Domain Specificity (1-5)

Does the task require specialized domain knowledge?

| Score | Example |
|-------|---------|
| 1 | General chat, formatting, arithmetic |
| 3 | Business writing, basic code, research |
| 5 | Legal analysis, medical reasoning, advanced math |

**Heuristic signals**: domain keyword presence (legal, medical, financial, security, math), cross-domain complexity, vision content

### 4. Instruction Nuance (1-5)

How precisely must the model follow complex instructions?

| Score | Example |
|-------|---------|
| 1 | Simple single-step instruction |
| 3 | Multi-part instruction with some ambiguity |
| 5 | Complex system prompt with tools and structured output |

**Heuristic signals**: system prompt length, tool count, JSON mode + tools combination

### 5. Error Tolerance (1-5)

How costly is a slightly imperfect response?

| Score | Example |
|-------|---------|
| 1 | Internal note, rough draft, exploratory query |
| 3 | Customer-facing content, code for review |
| 5 | Legal document, financial calculation, production code |

**Heuristic signals**: domain keyword presence, code output, prompt simplicity

## Tier Mapping

The composite score (5-25) maps to three tiers:

| Score Range | Tier | Example Models |
|-------------|------|---------------|
| 0-8 | Economy | gpt-4o-mini, claude-haiku-4-5, gemini-2.5-flash, llama-3.1-8b |
| 9-14 | Standard | gpt-4o-mini, claude-haiku-4-5, gemini-2.5-flash, llama-3.1-70b |
| 15-25 | Premium | gpt-4o, claude-sonnet-4-6, gemini-2.5-pro |

## Model Ceiling

The model you specify in the request acts as a **ceiling** — Kestrel will never route to a more expensive model, only cheaper ones.

| Requested Model | Ceiling Tier | Can route to |
|----------------|-------------|-------------|
| `gpt-4o` | Premium | Economy, Standard, or Premium |
| `claude-sonnet-4-6` | Premium | Economy, Standard, or Premium |
| `gpt-4o-mini` | Standard | Economy or Standard |
| `claude-haiku-4-5` | Economy | Economy only |

If you request `claude-haiku-4-5` (Economy), the request stays at Economy regardless of the complexity score — the model ceiling is never exceeded.

## Operator Controls

| Environment Variable | Effect |
|---------------------|--------|
| `KS_ROUTING_ENABLED` | Set to `false` to disable routing entirely (pass-through mode) |
| `KS_ROUTING_TIER_FLOOR` | Minimum tier — never route below this (e.g. `standard`) |
| `KS_ROUTING_TIER_CEILING` | Maximum tier — never route above this |
| `KS_ROUTING_ALLOWED_PROVIDERS` | Comma-separated list of providers to consider |
| `KS_ROUTING_DENIED_PROVIDERS` | Comma-separated list of providers to exclude |

## Extensibility

The routing scorer implements a `Scorer` protocol:

```python
class Scorer(Protocol):
    def score(self, features: RequestFeatures) -> RoutingScores: ...
```

The current implementation uses rule-based heuristics. The ML classifier (planned for Phase 2) will implement the same protocol, enabling a drop-in replacement without changing any other code.
