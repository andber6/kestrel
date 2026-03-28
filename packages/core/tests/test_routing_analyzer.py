"""Tests for request feature extraction."""

from __future__ import annotations

from kestrel.models.openai import ChatCompletionRequest
from kestrel.routing.analyzer import analyze_request


class TestAnalyzer:
    def test_basic_message_features(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
            }
        )
        f = analyze_request(req)
        assert f.total_message_count == 1
        assert f.user_message_count == 1
        assert f.last_user_message_chars == 5
        assert not f.has_tools
        assert not f.has_json_mode

    def test_system_prompt_chars(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hi"},
                ],
            }
        )
        f = analyze_request(req)
        assert f.system_prompt_chars == len("You are a helpful assistant.")

    def test_conversation_depth(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [
                    {"role": "user", "content": "Q1"},
                    {"role": "assistant", "content": "A1"},
                    {"role": "user", "content": "Q2"},
                    {"role": "assistant", "content": "A2"},
                    {"role": "user", "content": "Q3"},
                ],
            }
        )
        f = analyze_request(req)
        assert f.conversation_depth == 2  # 2 user messages after assistant

    def test_tool_detection(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Search"}],
                "tools": [
                    {"type": "function", "function": {"name": "search"}},
                    {"type": "function", "function": {"name": "read"}},
                ],
            }
        )
        f = analyze_request(req)
        assert f.has_tools
        assert f.tool_count == 2

    def test_json_mode_detection(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "JSON"}],
                "response_format": {"type": "json_object"},
            }
        )
        f = analyze_request(req)
        assert f.has_json_mode

    def test_code_block_detection(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Fix this:\n```python\nprint('hello')\n```\n"
                            "And this:\n```js\nconsole.log('hi')\n```"
                        ),
                    }
                ],
            }
        )
        f = analyze_request(req)
        assert f.code_block_count == 2

    def test_domain_keyword_detection(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "What are the legal implications of this contract? "
                            "Consider the financial liability."
                        ),
                    }
                ],
            }
        )
        f = analyze_request(req)
        assert f.domain_keyword_hits >= 2
        assert "legal" in f.domain_categories
        assert "financial" in f.domain_categories

    def test_image_detection(self) -> None:
        req = ChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What's this?"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "https://example.com/img.png"},
                            },
                        ],
                    }
                ],
            }
        )
        f = analyze_request(req)
        assert f.has_images
