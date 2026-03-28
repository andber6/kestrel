"""Background health check task for provider monitoring."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

import httpx

from kestrel.services.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)

# Lightweight endpoints to ping per provider (no tokens consumed)
_HEALTH_ENDPOINTS: dict[str, dict[str, str]] = {
    "openai": {"method": "GET", "path": "/models"},
    "groq": {"method": "GET", "path": "/models"},
    "anthropic": {"method": "GET", "path": "/messages"},  # Returns 405, confirms API is up
    "gemini": {"method": "GET", "path": "/models"},
}


class HealthCheckService:
    """Periodically pings providers and updates their health status."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        http_client: httpx.AsyncClient,
        interval_seconds: int = 30,
        provider_urls: dict[str, str] | None = None,
    ) -> None:
        self._registry = registry
        self._http_client = http_client
        self._interval = interval_seconds
        self._provider_urls = provider_urls or {}
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Start the background health check loop."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Health check started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        """Stop the background health check loop."""
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            logger.info("Health check stopped")

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._check_all()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Health check iteration failed")
            await asyncio.sleep(self._interval)

    async def _check_all(self) -> None:
        """Check all registered providers concurrently."""
        # Check all providers including unhealthy ones (to detect recovery)
        all_names = list(self._registry._health.keys())

        tasks = [self._check_one(name) for name in all_names]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_one(self, provider_name: str) -> None:
        """Ping a single provider and update its health status."""
        endpoint = _HEALTH_ENDPOINTS.get(provider_name)
        base_url = self._provider_urls.get(provider_name)

        if not endpoint or not base_url:
            return

        url = f"{base_url.rstrip('/')}{endpoint['path']}"
        start = time.monotonic()

        try:
            response = await self._http_client.request(
                endpoint["method"],
                url,
                timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            # 2xx or 405 (Anthropic /messages GET) = healthy
            if response.status_code < 500:
                self._registry.mark_healthy(provider_name, latency_ms)
            else:
                self._registry.mark_unhealthy(provider_name)

        except (httpx.TimeoutException, httpx.ConnectError):
            self._registry.mark_unhealthy(provider_name)
            logger.warning("Health check failed for %s (timeout/connection error)", provider_name)
