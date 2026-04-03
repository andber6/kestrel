"""Async request/response logging to PostgreSQL."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kestrel.models.db import RequestLog

logger = logging.getLogger(__name__)


class RequestLogService:
    """Writes request/response log entries to the database."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def log(
        self,
        *,
        api_key_id: str,
        model_requested: str,
        model_used: str,
        messages: list[dict[str, Any]],
        request_params: dict[str, Any] | None = None,
        is_streaming: bool = False,
        has_tools: bool = False,
        has_json_mode: bool = False,
        response: dict[str, Any] | None = None,
        finish_reason: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
        time_to_first_token_ms: int | None = None,
        error: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Write a log entry. Errors are logged but not raised."""
        try:
            async with self._session_factory() as session:
                entry = RequestLog(
                    api_key_id=api_key_id,
                    model_requested=model_requested,
                    model_used=model_used,
                    messages_json=_strip_base64(messages),
                    request_params_json=request_params,
                    is_streaming=is_streaming,
                    has_tools=has_tools,
                    has_json_mode=has_json_mode,
                    response_json=response,
                    finish_reason=finish_reason,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    time_to_first_token_ms=time_to_first_token_ms,
                    error=error,
                    status_code=status_code,
                )
                session.add(entry)
                await session.commit()
        except Exception as exc:
            logger.warning("Failed to write request log: %s", exc)


def _strip_base64(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace base64 image data with a placeholder to avoid bloating logs."""
    stripped = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_parts = []
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "image_url"
                    and isinstance(part.get("image_url"), dict)
                ):
                    url = part["image_url"].get("url", "")
                    if url.startswith("data:"):
                        part = {
                            **part,
                            "image_url": {
                                **part["image_url"],
                                "url": "[base64 image stripped]",
                            },
                        }
                new_parts.append(part)
            stripped.append({**msg, "content": new_parts})
        else:
            stripped.append(msg)
    return stripped
