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
        status = exc.response.status_code
        if status == 401:
            detail = (
                "Provider rejected the API key. Check that your provider"
                " credentials are correct and active in your Kestrel dashboard."
            )
        elif status == 429:
            detail = (
                "Provider rate limit exceeded. Try again shortly or check"
                " your provider's usage limits."
            )
        elif status == 404:
            detail = (
                "Model not available from provider. The requested model"
                " may not exist or may have been deprecated."
            )
        elif status >= 500:
            # Don't leak upstream provider error details to clients
            logger.error("Upstream provider returned %s: %s", status, exc.response.text[:500])
            detail = "Upstream provider error. Please try again shortly."
        else:
            # For other 4xx errors, provide a generic message
            detail = f"Provider returned error {status}."
        raise HTTPException(status_code=status, detail=detail) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Upstream provider timed out. Try again shortly.",
        ) from exc
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to upstream provider.",
        ) from exc
