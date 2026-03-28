"""Kestrel Python SDK — route LLM requests to the cheapest capable model."""

from kestrel._version import __version__
from kestrel.client import AsyncClient, Client

__all__ = ["Client", "AsyncClient", "__version__"]
