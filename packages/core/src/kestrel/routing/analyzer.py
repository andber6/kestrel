"""Extract structural features from a chat completion request."""

from __future__ import annotations

import re

from kestrel.models.openai import ChatCompletionRequest
from kestrel.routing.models import RequestFeatures

# Domain-specific keyword categories that signal higher complexity
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "legal": [
        "legal",
        "attorney",
        "lawyer",
        "court",
        "statute",
        "regulation",
        "compliance",
        "liability",
        "jurisdiction",
        "tort",
        "plaintiff",
        "defendant",
        "contract law",
        "intellectual property",
    ],
    "medical": [
        "medical",
        "clinical",
        "diagnosis",
        "patient",
        "treatment",
        "symptom",
        "prescription",
        "dosage",
        "pathology",
        "prognosis",
        "contraindication",
        "adverse effect",
    ],
    "financial": [
        "financial",
        "investment",
        "portfolio",
        "hedge",
        "derivative",
        "valuation",
        "securities",
        "fiduciary",
        "tax implications",
        "audit",
        "revenue recognition",
        "amortization",
    ],
    "security": [
        "vulnerability",
        "exploit",
        "authentication",
        "authorization",
        "encryption",
        "penetration test",
        "security audit",
        "CVE",
        "zero-day",
        "privilege escalation",
    ],
    "math": [
        "theorem",
        "proof",
        "integral",
        "differential equation",
        "eigenvalue",
        "topology",
        "linear algebra",
        "stochastic",
        "bayesian",
        "optimization problem",
    ],
}

_CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```")


def analyze_request(request: ChatCompletionRequest) -> RequestFeatures:
    """Extract structural features from a request for scoring."""
    messages = request.messages
    total_chars = 0
    user_chars = 0
    user_count = 0
    system_chars = 0
    last_user_chars = 0
    code_blocks = 0
    has_images = False

    # Count conversation turns (user↔assistant pairs)
    turns = 0
    prev_role: str | None = None

    # Aggregate all text for keyword analysis
    all_text_parts: list[str] = []

    for msg in messages:
        content = msg.content
        text = ""

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            for part in content:
                if hasattr(part, "text"):
                    text += part.text
                if hasattr(part, "image_url"):
                    has_images = True

        char_count = len(text)
        total_chars += char_count
        all_text_parts.append(text)

        if msg.role == "user":
            user_count += 1
            user_chars += char_count
            last_user_chars = char_count
            if prev_role == "assistant":
                turns += 1
        elif msg.role in ("system", "developer"):
            system_chars += char_count

        prev_role = msg.role

        # Count code blocks
        code_blocks += len(_CODE_BLOCK_PATTERN.findall(text))

    # Keyword analysis
    all_text = " ".join(all_text_parts).lower()
    domain_hits = 0
    domain_cats: list[str] = []

    for category, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in all_text:
                domain_hits += 1
                if category not in domain_cats:
                    domain_cats.append(category)
                break  # Count each category once

    msg_count = len(messages)
    has_tools = request.tools is not None and len(request.tools) > 0
    has_json_mode = request.response_format is not None and request.response_format.type != "text"

    return RequestFeatures(
        total_message_count=msg_count,
        user_message_count=user_count,
        total_char_count=total_chars,
        last_user_message_chars=last_user_chars,
        system_prompt_chars=system_chars,
        avg_message_chars=total_chars / msg_count if msg_count > 0 else 0.0,
        conversation_depth=turns,
        has_tools=has_tools,
        tool_count=len(request.tools) if request.tools else 0,
        has_json_mode=has_json_mode,
        has_images=has_images,
        code_block_count=code_blocks,
        domain_keyword_hits=domain_hits,
        domain_categories=domain_cats,
    )
