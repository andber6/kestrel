"""Google Gemini provider adapter — full OpenAI ↔ Gemini API translation."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import quote

import httpx

from kestrel.models.openai import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from kestrel.providers.base import LLMProvider

# Gemini finish_reason → OpenAI finish_reason
_FINISH_REASON_MAP = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
}


class GeminiProvider(LLMProvider):
    """Google Gemini API adapter with full format translation."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
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
        return "gemini"

    def _generate_url(self, model: str) -> str:
        return f"{self._base_url}/models/{quote(model, safe='')}:generateContent"

    def _stream_url(self, model: str) -> str:
        return f"{self._base_url}/models/{quote(model, safe='')}:streamGenerateContent?alt=sse"

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key}

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._timeout_connect,
            read=self._timeout_read,
            write=5.0,
            pool=5.0,
        )

    # ------------------------------------------------------------------
    # Request translation: OpenAI → Gemini
    # ------------------------------------------------------------------

    def translate_request(self, request: ChatCompletionRequest) -> dict[str, Any]:
        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []

        for msg in request.messages:
            role = msg.role
            content = msg.content

            if role in ("system", "developer"):
                if isinstance(content, str):
                    system_parts.append(content)
                continue

            gemini_role = "model" if role == "assistant" else "user"

            if role == "tool":
                # Tool results become functionResponse parts
                fn_response = {
                    "functionResponse": {
                        "name": msg.tool_call_id or "unknown",
                        "response": _parse_json_safe(content if isinstance(content, str) else ""),
                    }
                }
                # Merge with previous user message if possible
                if contents and contents[-1]["role"] == "user":
                    contents[-1]["parts"].append(fn_response)
                else:
                    contents.append({"role": "user", "parts": [fn_response]})
                continue

            parts: list[dict[str, Any]] = []

            if role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append(
                        {
                            "functionCall": {
                                "name": tc.function.name,
                                "args": json.loads(tc.function.arguments),
                            }
                        }
                    )
            elif isinstance(content, str) and content:
                parts.append({"text": content})
            elif isinstance(content, list):
                for part in content:
                    raw = (
                        part.model_dump(exclude_none=True) if hasattr(part, "model_dump") else part
                    )
                    part_dict = dict(raw)
                    if part_dict.get("type") == "text":
                        parts.append({"text": part_dict["text"]})
                    elif part_dict.get("type") == "image_url":
                        url = part_dict["image_url"]["url"]
                        if url.startswith("data:"):
                            media_type, _, b64_data = url.partition(";base64,")
                            media_type = media_type.replace("data:", "")
                            parts.append(
                                {
                                    "inlineData": {
                                        "mimeType": media_type,
                                        "data": b64_data,
                                    }
                                }
                            )

            if parts:
                contents.append({"role": gemini_role, "parts": parts})

        body: dict[str, Any] = {"contents": contents}

        if system_parts:
            body["systemInstruction"] = {"parts": [{"text": t} for t in system_parts]}

        # Generation config
        gen_config: dict[str, Any] = {}
        if request.temperature is not None:
            gen_config["temperature"] = request.temperature
        if request.top_p is not None:
            gen_config["topP"] = request.top_p
        if request.max_tokens is not None:
            gen_config["maxOutputTokens"] = request.max_tokens
        elif request.max_completion_tokens is not None:
            gen_config["maxOutputTokens"] = request.max_completion_tokens
        if request.stop is not None:
            gen_config["stopSequences"] = (
                request.stop if isinstance(request.stop, list) else [request.stop]
            )
        if request.response_format is not None and request.response_format.type == "json_object":
            gen_config["responseMimeType"] = "application/json"

        if gen_config:
            body["generationConfig"] = gen_config

        # Tools
        if request.tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t.function.name,
                            "description": t.function.description or "",
                            "parameters": t.function.parameters or {"type": "OBJECT"},
                        }
                        for t in request.tools
                    ]
                }
            ]

        return body

    # ------------------------------------------------------------------
    # Response translation: Gemini → OpenAI
    # ------------------------------------------------------------------

    def translate_response(self, raw: dict[str, Any]) -> ChatCompletionResponse:
        candidates = raw.get("candidates", [{}])
        candidate = candidates[0] if candidates else {}
        parts = candidate.get("content", {}).get("parts", [])

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    {
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": fc["name"],
                            "arguments": json.dumps(fc.get("args", {})),
                        },
                    }
                )

        message: dict[str, Any] = {"role": "assistant"}
        message["content"] = "\n".join(text_parts) if text_parts else None
        if tool_calls:
            message["tool_calls"] = tool_calls

        gemini_reason = candidate.get("finishReason", "STOP")
        finish_reason = _FINISH_REASON_MAP.get(gemini_reason, "stop")

        usage_meta = raw.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        }

        return ChatCompletionResponse.model_validate(
            {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": raw.get("modelVersion", ""),
                "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
                "usage": usage,
            }
        )

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        body = self.translate_request(request)
        response = await self._http_client.post(
            self._generate_url(request.model),
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        )
        response.raise_for_status()
        return self.translate_response(response.json())

    # ------------------------------------------------------------------
    # Streaming: Gemini SSE → OpenAI chunk format
    # Gemini streaming returns cumulative content, so we must diff.
    # ------------------------------------------------------------------

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[str, None]:
        body = self.translate_request(request)
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        model = request.model
        prev_text_len = 0
        sent_role = False

        async with self._http_client.stream(
            "POST",
            self._stream_url(request.model),
            json=body,
            headers=self._headers(),
            timeout=self._timeout(),
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except (json.JSONDecodeError, ValueError):
                    continue

                candidates = data.get("candidates", [])
                if not candidates:
                    continue
                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])

                # Emit role chunk once
                if not sent_role:
                    chunk = _make_chunk(completion_id, created, model, delta={"role": "assistant"})
                    yield f"data: {json.dumps(chunk)}\n\n"
                    sent_role = True

                # Emit text deltas
                for part in parts:
                    if "text" in part:
                        full_text = part["text"]
                        if len(full_text) > prev_text_len:
                            delta_text = full_text[prev_text_len:]
                            prev_text_len = len(full_text)
                            chunk = _make_chunk(
                                completion_id,
                                created,
                                model,
                                delta={"content": delta_text},
                            )
                            yield f"data: {json.dumps(chunk)}\n\n"

                # Check for finish
                finish_reason_raw = candidate.get("finishReason")
                if finish_reason_raw and finish_reason_raw != "FINISH_REASON_UNSPECIFIED":
                    finish = _FINISH_REASON_MAP.get(finish_reason_raw, "stop")
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


def _parse_json_safe(s: str) -> dict[str, Any]:
    try:
        return json.loads(s)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, ValueError):
        return {"result": s}
