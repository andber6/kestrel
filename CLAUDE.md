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
│   │   └── tests/              167 tests, all mocked (no real API calls)
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
make test         # Pytest with coverage (167 tests)
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

**Health endpoints:**
- `GET /health` — liveness probe, always returns `{"status": "ok"}`
- `GET /ready` — readiness probe, checks DB connectivity and provider health (returns 503 if not ready)

**Dev mode** (`KS_DEV_MODE=true`): bypasses auth, uses `KS_DEV_*_API_KEY` settings directly.

## Design Decisions

**No proxy-level rate limiting.** Customers bring their own provider API keys, so rate limits are enforced directly between the customer and the upstream provider. Adding a proxy-level rate limiter would be redundant and would break the trust model (the proxy doesn't own the quota). If this changes in the future (e.g., shared key pools), rate limiting should be added at that point.

**No mid-stream failover.** Once streaming has started (first byte sent to client), the proxy commits to that provider. Recovering mid-stream would require buffering the entire response or breaking the SSE contract. This is an intentional limitation — failover only happens before the first byte.

**Rule-based scorer (Phase 1).** The routing scorer uses heuristic rules (keyword matching, character counts, structural analysis) rather than ML. This is intentional for the open-source core — it requires no model files, no GPU, and no training data. The ML classifier (Phase 2) lives in the closed-source `kestrel-server` repo and plugs in via the `Scorer` protocol.

**Fire-and-forget logging.** Request logging is non-blocking (`asyncio.create_task`). If the database is down, requests still succeed — log failures are caught and logged as warnings. This means some logs may be lost during DB outages, which is an acceptable trade-off for never blocking the hot path.

## CLI Commands

Beyond `serve`, `key`, and `migrate`, the CLI includes:

```bash
kestrel logs prune --older-than 30d          # Delete old request logs
kestrel logs prune --older-than 7d --dry-run # Preview deletion count
```

## What NOT to Put in This Repo

- Billing/Stripe code → goes in `kestrel-server` (private)
- ML classifier model → goes in `kestrel-server` (private)
- Semantic cache → goes in `kestrel-server` (private)
- Dashboard frontend → goes in `kestrel-server` (private)
- Real API keys or `.env` files
