"""FastAPI dependency injection functions."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from agentrouter.auth.api_key import AuthContext, authenticate_request
from agentrouter.config import Settings
from agentrouter.services.proxy import ProxyService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_proxy_service(request: Request) -> ProxyService:
    return request.app.state.proxy_service  # type: ignore[no-any-return]


async def get_auth_context(request: Request) -> AuthContext:
    settings: Settings = request.app.state.settings

    # Dev mode short-circuit: no DB needed
    if settings.dev_mode:
        return await authenticate_request(
            authorization=request.headers.get("authorization"),
            x_agentrouter_key=request.headers.get("x-agentrouter-key"),
            session=None,  # type: ignore[arg-type]
            dev_mode=True,
            dev_openai_api_key=settings.dev_openai_api_key,
        )

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        return await authenticate_request(
            authorization=request.headers.get("authorization"),
            x_agentrouter_key=request.headers.get("x-agentrouter-key"),
            session=session,
            dev_mode=False,
        )


SettingsDep = Annotated[Settings, Depends(get_settings)]
ProxyDep = Annotated[ProxyService, Depends(get_proxy_service)]
AuthDep = Annotated[AuthContext, Depends(get_auth_context)]
