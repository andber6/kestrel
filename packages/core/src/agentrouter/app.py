"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agentrouter.auth.api_key import AuthError
from agentrouter.config import Settings
from agentrouter.db.session import create_db_engine
from agentrouter.middleware.logging import RequestIdMiddleware
from agentrouter.routes.chat import router as chat_router
from agentrouter.services.proxy import ProxyService
from agentrouter.services.request_log import RequestLogService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage shared resources: HTTP client, DB engine."""
    settings: Settings = app.state.settings

    # HTTP client for upstream provider calls
    http_client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    app.state.http_client = http_client

    # Database
    engine, session_factory = create_db_engine(settings.database_url)
    app.state.db_engine = engine
    app.state.session_factory = session_factory

    # Services
    log_service = RequestLogService(session_factory)
    app.state.proxy_service = ProxyService(
        http_client=http_client,
        log_service=log_service,
        openai_base_url=settings.openai_base_url,
    )

    logger.info("AgentRouter started (dev_mode=%s)", settings.dev_mode)
    yield

    # Shutdown
    await http_client.aclose()
    await engine.dispose()
    logger.info("AgentRouter shut down")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="AgentRouter",
        version="0.1.0",
        description="Drop-in LLM API proxy for cost optimization",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Middleware
    app.add_middleware(RequestIdMiddleware)

    # Exception handler for auth errors
    @app.exception_handler(AuthError)
    async def auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": {"message": exc.detail}})

    # Routes
    app.include_router(chat_router)

    # Health check
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
