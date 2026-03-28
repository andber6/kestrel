"""Request ID and timing middleware."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID and timing headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()

        response = await call_next(request)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
        return response
