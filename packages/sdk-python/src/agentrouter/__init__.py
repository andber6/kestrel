"""AgentRouter Python SDK — route LLM requests to the cheapest capable model."""

from agentrouter._version import __version__
from agentrouter.client import AsyncClient, Client

__all__ = ["Client", "AsyncClient", "__version__"]
