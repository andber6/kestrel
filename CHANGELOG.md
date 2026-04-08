# Changelog

All notable changes to Kestrel will be documented in this file.

## [0.2.0] — 2026-04-08

### Added
- xAI (Grok) as 8th provider adapter
- Fernet encryption for provider API keys at rest
- Background health checks for all 8 providers (30s interval)
- Provider failover with exponential backoff and jitter (up to 2 retries)
- Cross-provider fallback via model equivalence mapping
- `/ready` readiness probe (checks DB connectivity, reports provider health)
- `kestrel logs prune --older-than 30d` CLI command for request log retention
- Text-level complexity analysis (analytical/technical keywords, vocabulary sophistication)
- Security headers middleware (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)
- Request ID and response timing headers (`X-Request-Id`, `X-Response-Time-Ms`)

### Fixed
- Provider error messages no longer leak upstream details to clients
- Fire-and-forget log tasks now surface exceptions via error callback
- Encryption module fails fast on invalid key instead of silent plaintext fallback

### Changed
- Routing tier thresholds adjusted (Economy 5-8, Standard 9-14, Premium 15-25)
- Gemini and xAI model catalogs updated to current API offerings
- Test count increased from 135 to 167

## [0.1.0] — 2026-03-28

Initial open-source release.

### Core
- Drop-in LLM API proxy with OpenAI-compatible request/response format
- 7 provider adapters: OpenAI, Anthropic, Google Gemini, Groq, Mistral, Cohere, Together AI
- Full format translation for Anthropic, Gemini, and Cohere; OpenAI-compatible pass-through for the rest
- Streaming (SSE) support across all providers

### Routing
- Rule-based complexity scoring across 5 dimensions
- 3-tier routing: Economy, Standard, Premium
- Model-as-ceiling: never routes to a more expensive model than requested
- Pluggable `Scorer` protocol for swapping in ML classifiers

### Auth
- Two auth patterns: dual-header (Kestrel key + provider key) or single bearer (provider keys from DB)
- SHA-256 key hashing, Pydantic input validation with field limits

### Operations
- CLI: `kestrel serve`, `key generate/list/revoke`, `migrate`
- `/health` liveness probe
- Fire-and-forget request logging with token usage, latency, and TTFT tracking
- Docker Compose setup (proxy + PostgreSQL)

### Developer Experience
- 135 tests, all mocked (no real API calls)
- mypy strict mode, Ruff linting (line-length 99)
- GitHub Actions CI (lint, typecheck, test) and PyPI publish workflow
- Python SDK (`kestrel-sdk`) for easy integration
