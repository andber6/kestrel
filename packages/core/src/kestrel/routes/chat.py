"""Chat completions endpoint — /v1/chat/completions."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from kestrel.dependencies import AuthDep, ProxyDep
from kestrel.models.openai import ChatCompletionRequest, ChatCompletionResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: ChatCompletionRequest,
    auth: AuthDep,
    proxy: ProxyDep,
) -> ChatCompletionResponse | StreamingResponse:
    if request.stream:
        return StreamingResponse(
            proxy.proxy_stream(request, auth),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        return await proxy.proxy_request(request, auth)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Upstream provider timed out",
        ) from exc
