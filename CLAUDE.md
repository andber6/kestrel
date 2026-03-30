# CLAUDE.md — Kestrel

## What This Project Is

Kestrel is a drop-in LLM API proxy that intercepts requests, classifies prompt complexity, and routes to the cheapest capable model. One base_url change, 50-80% cost savings.

This repo is the **open-source core** (MIT license). The closed-source hosted service (billing, ML classifier, semantic cache) lives in a separate `kestrel-server` repo.

## Repository Structure

```
kestrel/
├── packages/
│   ├── core/               ← The proxy server (FastAPI + Python 3.12+)
│   │   ├── src/kestrel/
│   │   │   ├── app.py              FastAPI factory, lifespan
│   │   │   ├── config.py           Settings (KS_ env vars, pydantic-settings)
│   │   │   ├── providers/          LLM adapters (OpenAI, Anthropic, Gemini, Groq, Mistral, Cohere, Together)
│   │   │   ├── routing/            Complexity analysis → scoring → tier → model
│   │   │   ├── services/           Proxy orchestration, registry, health, logging
│   │   │   ├── auth/               API key auth (two patterns)
│   │   │   ├── models/             Pydantic (OpenAI format) + SQLAlchemy (DB)
│   │   │   ├── routes/             POST /v1/chat/completions
│   │   │   └── middleware/         Request ID + timing
│   │   └── tests/              145 tests, all mocked (no real API calls)
│   └── sdk-python/             ← Python SDK (thin wrapper over openai package)
├── docs/                       ← Markdown documentation
├── .github/workflows/ci.yml   ← GitHub Actions (ruff, mypy, pytest)
└── docker-compose.yml          ← Proxy + PostgreSQL
```

## Development Commands

All commands run from the project root:

```bash
make install      # Install core dependencies (cd packages/core && uv sync)
make dev          # Start dev server on :8080 with --reload
make lint         # Ruff check + format check
make format       # Ruff format + fix
make typecheck    # Mypy strict mode
make test         # Pytest with coverage (135 tests)
make sdk-test     # Run SDK tests (10 tests)
```

## Key Conventions

- **Package manager**: `uv` (not pip/poetry)
- **Python**: 3.12+ with modern syntax (`X | Y` unions, `StrEnum`)
- **Lint**: Ruff, line length 99
- **Types**: mypy strict mode with pydantic plugin
- **Tests**: pytest + pytest-asyncio, mode=auto. All external calls mocked with `respx`
- **Config**: All settings via env vars with `KS_` prefix (see `.env.example`)
- **Working directory**: Most commands expect `packages/core/` as cwd (Makefile handles this)

## Architecture Quick Reference

**Request flow:**
HTTP → `routes/chat.py` → `services/proxy.py` → `routing/engine.py` (analyze → score → tier → model) → `providers/*.py` (translate + forward) → upstream LLM API

**Adding a provider:**
- OpenAI-compatible: subclass `OpenAICompatibleProvider`, override `translate_request()`. See `providers/groq.py` (~40 lines)
- Different format: subclass `LLMProvider`, implement all methods. See `providers/anthropic.py`
- Register in `services/provider_registry.py`, add config in `config.py`, add tier mappings in `routing/tier_resolver.py`

**Routing scorer is pluggable:** The `Scorer` protocol in `routing/models.py` allows the rule-based heuristics to be replaced by an ML classifier without touching other code.

**Auth supports two patterns:**
1. `X-Kestrel-Key: ar-...` + `Authorization: Bearer sk-...` (provider key)
2. `Authorization: Bearer ar-...` (Kestrel key only, provider key from DB)

**Dev mode** (`KS_DEV_MODE=true`): bypasses auth, uses `KS_DEV_*_API_KEY` settings directly.

## What NOT to Put in This Repo

- Billing/Stripe code → goes in `kestrel-server` (private)
- ML classifier model → goes in `kestrel-server` (private)
- Semantic cache → goes in `kestrel-server` (private)
- Dashboard frontend → goes in `kestrel-server` (private)
- Real API keys or `.env` files
