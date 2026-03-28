"""Cohere provider adapter — full OpenAI ↔ Cohere Chat API translation."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from kestrel.models.openai import ChatCompletionRequest, ChatCompletionResponse
from kestrel.providers.base import LLMProvider

# Cohere finish_reason → OpenAI finish_reason
_FINISH_REASON_MAP = {
    "COMPLETE": "stop",
    "STOP_SEQUENCE": "stop",
    "MAX_TOKENS": "length",
    "TOOL_CALL": "tool_calls",
    "ERROR": "stop",
}


class CohereProvider(LLMProvider):
    """Cohere Chat API adapter with full format translation."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.cohere.com/v2",
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
        return "cohere"

    def _chat_url(self) -> str:
        return f"{self._base_url}/chat"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._timeout_connect,
            read=self._timeout_read,
            write=5.0,
            pool=5.0,
        )

    # ------------------------------------------------------------------
    # Request translation: OpenAI → Cohere v2
    # ------------------------------------------------------------------

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []

        for msg in request.messages:
            role = msg.role
            content = msg.content

            if role in ("system", "developer"):
                messages.append(
                    {
                        "role": "system",
                        "content": content if isinstance(content, str) else "",
                    }
                )
            elif role == "user":
                messages.append(
                    {
                        "role": "user",
                        "content": content if isinstance(content, str) else "",
                    }
                )
            elif role == "assistant":
                cohere_msg: dict[str, Any] = {"role": "assistant"}
                if isinstance(content, str) and content:
                    cohere_msg["content"] = content
                if msg.tool_calls:
                    cohere_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                messages.append(cohere_msg)
            elif role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id or "",
                        "content": content if isinstance(content, str) else "",
                    }
                )

        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }

        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["p"] = request.top_p
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        elif request.max_completion_tokens is not None:
            body["max_tokens"] = request.max_completion_tokens
        if request.stop is not None:
            body["stop_sequences"] = (
                request.stop if isinstance(request.stop, list) else [request.stop]
            )

        # Tools
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.function.name,
                        "description": t.function.description or "",
                        "parameters": t.function.parameters or {"type": "object"},
                    },
                }
                for t in request.tools
            ]

        return body

    # ------------------------------------------------------------------
    # Response translation: Cohere → OpenAI
    # ------------------------------------------------------------------

    def translate_response(self, raw: dict[str, Any]) -> ChatCompletionResponse:
        message_data = raw.get("message", {})
        content_parts = message_data.get("content", [])
        tool_calls_raw = message_data.get("tool_calls", [])

        # Extract text content
        text_parts: list[str] = []
        for part in content_parts:
            if isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)

        message: dict[str, Any] = {"role": "assistant"}
        message["content"] = "\n".join(text_parts) if text_parts else None

        # Tool calls
        if tool_calls_raw:
            message["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                }
                for tc in tool_calls_raw
            ]

        finish_reason_raw = raw.get("finish_reason", "COMPLETE")
        finish_reason = _FINISH_REASON_MAP.get(finish_reason_raw, "stop")

        usage_raw = raw.get("usage", {})
        billed = usage_raw.get("billed_units", {})
        tokens = usage_raw.get("tokens", {})
        prompt_tokens = tokens.get("input_tokens", billed.get("input_tokens", 0))
        completion_tokens = tokens.get("output_tokens", billed.get("output_tokens", 0))

        return ChatCompletionResponse.model_validate(
            {
                "id": f"chatcmpl-{raw.get('id', uuid.uuid4().hex[:12])}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": raw.get("model", ""),
                "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }
        )

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        body = self.translate_request(request)

        response = await self._http_client.post(
            self._chat_url(),
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        )
        response.raise_for_status()
        return self.translate_response(response.json())

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[str, None]:
        body = self.translate_request(request)
        body["stream"] = True

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        model = request.model
        sent_role = False

        async with self._http_client.stream(
            "POST",
            self._chat_url(),
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except (json.JSONDecodeError, ValueError):
                    continue

                event_type = event.get("type", "")

                if event_type == "content-start" and not sent_role:
                    chunk = _make_chunk(completion_id, created, model, delta={"role": "assistant"})
                    yield f"data: {json.dumps(chunk)}\n\n"
                    sent_role = True

                elif event_type == "content-delta":
                    delta = event.get("delta", {})
                    text = delta.get("message", {}).get("content", {}).get("text", "")
                    if text:
                        chunk = _make_chunk(completion_id, created, model, delta={"content": text})
                        yield f"data: {json.dumps(chunk)}\n\n"

                elif event_type == "message-end":
                    delta = event.get("delta", {})
                    finish = _FINISH_REASON_MAP.get(delta.get("finish_reason", "COMPLETE"), "stop")
                    chunk = _make_chunk(
                        completion_id,
                        created,
                        model,
                        delta={},
                        finish_reason=finish,
                    )
                    yield f"data: {json.dumps(chunk)}\n\n"

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
