"""Anthropic provider adapter — full OpenAI ↔ Anthropic Messages API translation."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from kestrel.models.openai import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from kestrel.providers.base import LLMProvider

# Anthropic stop_reason → OpenAI finish_reason
_STOP_REASON_MAP = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}

# Default max_tokens when not specified (Anthropic requires it)
_DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API adapter with full format translation."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        http_client: httpx.AsyncClient,
        timeout_connect: float = 5.0,
        timeout_read: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http_client = http_client
        self._timeout_connect = timeout_connect
        self._timeout_read = timeout_read

    @property
    def name(self) -> str:
        return "anthropic"

    def _messages_url(self) -> str:
        return f"{self._base_url}/messages"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._timeout_connect,
            read=self._timeout_read,
            write=5.0,
            pool=5.0,
        )

    # ------------------------------------------------------------------
    # Request translation: OpenAI → Anthropic
    # ------------------------------------------------------------------

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []

        for msg in request.messages:
            role = msg.role
            content = msg.content

            # System/developer messages → Anthropic's top-level `system` param
            if role in ("system", "developer"):
                if isinstance(content, str):
                    system_parts.append(content)
                elif isinstance(content, list):
                    for part in content:
                        text = part.text if hasattr(part, "text") else str(part)
                        system_parts.append(text)
                continue

            if role == "assistant":
                anthropic_content: list[dict[str, Any]] = []
                if isinstance(content, str) and content:
                    anthropic_content.append({"type": "text", "text": content})
                # Tool calls → tool_use content blocks
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        anthropic_content.append(
                            {
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.function.name,
                                "input": json.loads(tc.function.arguments),
                            }
                        )
                messages.append(
                    {
                        "role": "assistant",
                        "content": anthropic_content or [{"type": "text", "text": ""}],
                    }
                )

            elif role == "tool":
                # Tool results: merge consecutive tool messages into one user message
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": content if isinstance(content, str) else "",
                }
                # If the previous message is a user message with tool_results, merge
                if (
                    messages
                    and messages[-1]["role"] == "user"
                    and isinstance(messages[-1]["content"], list)
                    and messages[-1]["content"]
                    and messages[-1]["content"][-1].get("type") == "tool_result"
                ):
                    messages[-1]["content"].append(tool_result)
                else:
                    messages.append({"role": "user", "content": [tool_result]})

            elif role == "user":
                if isinstance(content, str):
                    messages.append(
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": content}],
                        }
                    )
                elif isinstance(content, list):
                    parts = []
                    for part in content:
                        raw = (
                            part.model_dump(exclude_none=True)
                            if hasattr(part, "model_dump")
                            else part
                        )
                        part_dict = dict(raw)
                        if part_dict.get("type") == "text":
                            parts.append({"type": "text", "text": part_dict["text"]})
                        elif part_dict.get("type") == "image_url":
                            url = part_dict["image_url"]["url"]
                            if url.startswith("data:"):
                                # Base64 inline image
                                media_type, _, b64_data = url.partition(";base64,")
                                media_type = media_type.replace("data:", "")
                                parts.append(
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": b64_data,
                                        },
                                    }
                                )
                            else:
                                parts.append(
                                    {
                                        "type": "image",
                                        "source": {"type": "url", "url": url},
                                    }
                                )
                    messages.append({"role": "user", "content": parts})

        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens
            or request.max_completion_tokens
            or _DEFAULT_MAX_TOKENS,
        }

        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.stop is not None:
            body["stop_sequences"] = (
                request.stop if isinstance(request.stop, list) else [request.stop]
            )

        # Tools
        if request.tools:
            body["tools"] = [
                {
                    "name": t.function.name,
                    "description": t.function.description or "",
                    "input_schema": t.function.parameters or {"type": "object"},
                }
                for t in request.tools
            ]

        return body

    # ------------------------------------------------------------------
    # Response translation: Anthropic → OpenAI
    # ------------------------------------------------------------------

    def translate_response(self, raw: dict[str, Any]) -> ChatCompletionResponse:
        content_blocks = raw.get("content", [])
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append(
                    {
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    }
                )

        message: dict[str, Any] = {"role": "assistant"}
        if text_parts:
            message["content"] = "\n".join(text_parts)
        else:
            message["content"] = None

        if tool_calls:
            message["tool_calls"] = tool_calls

        stop_reason = raw.get("stop_reason", "end_turn")
        finish_reason = _STOP_REASON_MAP.get(stop_reason, "stop")

        usage_raw = raw.get("usage", {})
        usage = {
            "prompt_tokens": usage_raw.get("input_tokens", 0),
            "completion_tokens": usage_raw.get("output_tokens", 0),
            "total_tokens": usage_raw.get("input_tokens", 0) + usage_raw.get("output_tokens", 0),
        }

        return ChatCompletionResponse.model_validate(
            {
                "id": f"chatcmpl-{raw.get('id', uuid.uuid4().hex[:12])}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": raw.get("model", ""),
                "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
                "usage": usage,
            }
        )

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        body = self.translate_request(request)
        body.pop("stream", None)

        response = await self._http_client.post(
            self._messages_url(),
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        )
        response.raise_for_status()
        return self.translate_response(response.json())

    # ------------------------------------------------------------------
    # Streaming: translate Anthropic SSE events → OpenAI chunk format
    # ------------------------------------------------------------------

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[str, None]:
        body = self.translate_request(request)
        body["stream"] = True

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        model = request.model

        async with self._http_client.stream(
            "POST",
            self._messages_url(),
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                try:
                    event = json.loads(data_str)
                except (json.JSONDecodeError, ValueError):
                    continue

                event_type = event.get("type", "")

                if event_type == "message_start":
                    msg = event.get("message", {})
                    model = msg.get("model", model)
                    # Emit role chunk
                    chunk = _make_chunk(completion_id, created, model, delta={"role": "assistant"})
                    yield f"data: {json.dumps(chunk)}\n\n"

                elif event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        # Start of tool call
                        tc = {
                            "id": block.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": block.get("name", ""),
                                "arguments": "",
                            },
                        }
                        chunk = _make_chunk(
                            completion_id,
                            created,
                            model,
                            delta={"tool_calls": [tc]},
                        )
                        yield f"data: {json.dumps(chunk)}\n\n"

                elif event_type == "content_block_delta":
                    delta_data = event.get("delta", {})
                    delta_type = delta_data.get("type", "")

                    if delta_type == "text_delta":
                        chunk = _make_chunk(
                            completion_id,
                            created,
                            model,
                            delta={"content": delta_data.get("text", "")},
                        )
                        yield f"data: {json.dumps(chunk)}\n\n"

                    elif delta_type == "input_json_delta":
                        tc = {"function": {"arguments": delta_data.get("partial_json", "")}}
                        chunk = _make_chunk(
                            completion_id,
                            created,
                            model,
                            delta={"tool_calls": [tc]},
                        )
                        yield f"data: {json.dumps(chunk)}\n\n"

                elif event_type == "message_delta":
                    stop_reason = event.get("delta", {}).get("stop_reason")
                    finish_reason = _STOP_REASON_MAP.get(stop_reason or "", "stop")
                    chunk = _make_chunk(
                        completion_id,
                        created,
                        model,
                        delta={},
                        finish_reason=finish_reason,
                    )
                    # Include usage if available
                    usage = event.get("usage")
                    if usage:
                        chunk["usage"] = {
                            "prompt_tokens": usage.get("input_tokens", 0),
                            "completion_tokens": usage.get("output_tokens", 0),
                            "total_tokens": usage.get("input_tokens", 0)
                            + usage.get("output_tokens", 0),
                        }
                    yield f"data: {json.dumps(chunk)}\n\n"

                elif event_type == "message_stop":
                    yield "data: [DONE]\n\n"


def _make_chunk(
    completion_id: str,
    created: int,
    model: str,
    *,
    delta: dict[str, Any],
    finish_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
