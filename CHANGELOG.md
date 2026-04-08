# Changelog

All notable changes to Kestrel will be documented in this file.

## [0.1.0] — 2026-04-08

Initial open-source release.

### Core
- Drop-in LLM API proxy with OpenAI-compatible request/response format
- 8 provider adapters: OpenAI, Anthropic, Google Gemini, Groq, xAI, Mistral, Cohere, Together AI
- Full format translation for Anthropic, Gemini, and Cohere; OpenAI-compatible pass-through for the rest
- Streaming (SSE) support across all providers

### Routing
- Rule-based complexity scoring across 5 dimensions (reasoning depth, output complexity, domain specificity, instruction nuance, error tolerance)
- 3-tier routing: Economy, Standard, Premium
- Model-as-ceiling: never routes to a more expensive model than requested
- Pluggable `Scorer` protocol for swapping in ML classifiers

### Reliability
- Provider failover with exponential backoff and jitter (up to 2 retries)
- Background health checks for all 8 providers (30s interval)
- Cross-provider fallback via model equivalence mapping
- Fire-and-forget request logging (non-blocking, DB failure never blocks requests)

### Auth & Security
- Two auth patterns: dual-header (Kestrel key + provider key) or single bearer (provider keys from DB)
- Fernet encryption for provider API keys at rest
- SHA-256 key hashing, security headers middleware
- Pydantic input validation with field limits

### Operations
- CLI: `kestrel serve`, `key generate/list/revoke`, `migrate`, `logs prune`
- `/health` liveness probe, `/ready` readiness probe (checks DB connectivity)
- Request logging with token usage, latency, and TTFT tracking
- Docker Compose setup (proxy + PostgreSQL)

### Developer Experience
- 167 tests, all mocked (no real API calls)
- mypy strict mode, Ruff linting (line-length 99)
- GitHub Actions CI (lint, typecheck, test) and PyPI publish workflow
- Python SDK (`kestrel-sdk`) for easy integration
