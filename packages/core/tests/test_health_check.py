"""Tests for HealthCheckService and /ready endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import respx

from kestrel.app import create_app
from kestrel.config import Settings
from kestrel.services.health_check import HealthCheckService
from kestrel.services.provider_registry import ProviderRegistry
from kestrel.services.proxy import ProxyService


def _make_health_service() -> tuple[HealthCheckService, ProviderRegistry]:
    settings = Settings(dev_mode=True, dev_openai_api_key="sk-test")
    http_client = httpx.AsyncClient()
    registry = ProviderRegistry.from_settings(
        settings,
        http_client,
        provider_api_keys={"openai": "sk-test"},
    )
    provider_urls = {"openai": "https://api.openai.com/v1"}
    service = HealthCheckService(
        registry=registry,
        http_client=http_client,
        interval_seconds=30,
        provider_urls=provider_urls,
    )
    return service, registry


class TestHealthCheckOneProvider:
    @respx.mock
    async def test_marks_provider_healthy_on_success(self) -> None:
        service, registry = _make_health_service()

        respx.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        await service._check_all()

        assert registry.is_healthy("openai")
        status = registry.get_health_status()
        assert status["openai"]["available"] is True
        assert status["openai"]["last_latency_ms"] is not None

    @respx.mock
    async def test_marks_provider_unhealthy_on_500(self) -> None:
        service, registry = _make_health_service()

        respx.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(500, text="Internal error")
        )

        # Need 3 consecutive failures to mark unhealthy
        await service._check_all()
        await service._check_all()
        await service._check_all()

        assert not registry.is_healthy("openai")

    @respx.mock
    async def test_marks_provider_unhealthy_on_timeout(self) -> None:
        service, registry = _make_health_service()

        respx.get("https://api.openai.com/v1/models").mock(
            side_effect=httpx.TimeoutException("timed out")
        )

        await service._check_all()
        await service._check_all()
        await service._check_all()

        assert not registry.is_healthy("openai")

    @respx.mock
    async def test_recovers_after_success(self) -> None:
        service, registry = _make_health_service()

        # Fail 3 times
        respx.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(500, text="error")
        )
        for _ in range(3):
            await service._check_all()
        assert not registry.is_healthy("openai")

        # Recover
        respx.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        await service._check_all()

        assert registry.is_healthy("openai")

    @respx.mock
    async def test_405_counts_as_healthy(self) -> None:
        """Sub-500 status codes (like 405) should be treated as healthy."""
        service, registry = _make_health_service()

        respx.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(405, text="Method not allowed")
        )

        await service._check_all()

        assert registry.is_healthy("openai")


class TestReadyEndpoint:
    async def test_ready_returns_503_without_db(self) -> None:
        """Without a real DB engine, /ready should return 503."""
        settings = Settings(dev_mode=True, dev_openai_api_key="sk-test")
        app = create_app(settings)

        # Set up minimal app state without lifespan (no real DB)
        http_client = httpx.AsyncClient()
        app.state.http_client = http_client
        app.state.db_engine = None
        app.state.session_factory = AsyncMock()
        app.state.proxy_service = ProxyService(
            http_client=http_client, settings=settings, log_service=None
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        await http_client.aclose()

    async def test_ready_returns_200_with_mock_db(self) -> None:
        """With a mock DB engine that responds, /ready should return 200."""
        settings = Settings(dev_mode=True, dev_openai_api_key="sk-test")
        app = create_app(settings)

        http_client = httpx.AsyncClient()

        # Mock engine with working connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_conn)

        app.state.http_client = http_client
        app.state.db_engine = mock_engine
        app.state.session_factory = AsyncMock()
        app.state.proxy_service = ProxyService(
            http_client=http_client, settings=settings, log_service=None
        )

        # Add a health registry with a healthy provider
        registry = ProviderRegistry.from_settings(
            settings, http_client, provider_api_keys={"openai": "sk-test"}
        )
        registry.mark_healthy("openai", 50)
        app.state.health_registry = registry

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"] == "ok"
        assert "1 available" in body["checks"]["providers"]
        await http_client.aclose()
