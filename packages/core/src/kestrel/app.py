"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kestrel.auth.api_key import AuthError
from kestrel.config import Settings
from kestrel.db.session import create_db_engine
from kestrel.middleware.logging import RequestIdMiddleware, SecurityHeadersMiddleware
from kestrel.routes.chat import router as chat_router
from kestrel.services.health_check import HealthCheckService
from kestrel.services.provider_registry import ProviderRegistry
from kestrel.services.proxy import ProxyService
from kestrel.services.request_log import RequestLogService

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
    proxy_service = ProxyService(
        http_client=http_client,
        settings=settings,
        log_service=log_service,
    )
    app.state.proxy_service = proxy_service

    # Background health checks for provider monitoring.
    # Uses a standalone registry for tracking health status only
    # (per-request registries carry user-specific API keys).
    health_registry = ProviderRegistry.from_settings(settings, http_client, provider_api_keys={})
    provider_urls = {
        "openai": settings.openai_base_url,
        "anthropic": settings.anthropic_base_url,
        "gemini": settings.gemini_base_url,
        "groq": settings.groq_base_url,
        "mistral": settings.mistral_base_url,
    }
    health_check = HealthCheckService(
        registry=health_registry,
        http_client=http_client,
        interval_seconds=settings.health_check_interval,
        provider_urls=provider_urls,
    )
    app.state.health_registry = health_registry
    health_check.start()
    app.state.health_check = health_check

    logger.info("Kestrel started (dev_mode=%s)", settings.dev_mode)
    yield

    # Shutdown
    await health_check.stop()
    await http_client.aclose()
    await engine.dispose()
    logger.info("Kestrel shut down")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="Kestrel",
        version="0.1.0",
        description="Drop-in LLM API proxy for cost optimization",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Middleware (outermost runs first)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

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
