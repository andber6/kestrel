# Kestrel

[![CI](https://github.com/andber6/kestrel/actions/workflows/ci.yml/badge.svg)](https://github.com/andber6/kestrel/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/kestrel-ai)](https://pypi.org/project/kestrel-ai/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Drop-in LLM API proxy that routes requests to the cheapest capable model.**

Kestrel sits between your AI agent and LLM providers. It intercepts every outgoing API request, classifies the complexity of the prompt, and automatically routes it to the cheapest model that can handle it. You change one line of code — your base URL — and start saving 50-80% on LLM API costs. The response format is identical. Streaming works. Function calling works. Your agent doesn't know routing happened.

```python
# One-line integration: just swap the base URL
client = openai.OpenAI(
    base_url="https://api.usekestrel.io/v1",
    api_key="ks-your-key",
)
```

**Managed service:** [usekestrel.io](https://usekestrel.io) — sign up, add your provider keys, and start saving.

## How It Works

1. **Receive** — Your agent sends a request to Kestrel instead of directly to OpenAI/Anthropic/etc.
2. **Analyze** — Extract features: prompt length, analytical/technical keywords, tool presence, domain keywords, code blocks, conversation depth
3. **Score** — Rate complexity across 5 dimensions (reasoning depth, output complexity, domain specificity, instruction nuance, error tolerance)
4. **Route** — Map the score to a tier (Economy/Standard/Premium) and pick the cheapest model that fits, never exceeding the model you specified
5. **Forward** — Translate the request to the selected provider's format, forward it, translate the response back to OpenAI format

## Quick Start

### Using the managed service

The fastest way to get started — no infrastructure to manage:

1. Sign in at [app.usekestrel.io](https://app.usekestrel.io) with GitHub or Google
2. Add your provider API keys and generate a Kestrel key
3. Change your base URL:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.usekestrel.io/v1",
    api_key="ks-your-key",
)

response = client.chat.completions.create(
    model="gpt-4o",  # Kestrel may route to a cheaper model
    messages=[{"role": "user", "content": "Hello"}],
)
```

See the [docs](https://usekestrel.io/docs) for more examples.

### Self-hosted

```bash
cd packages/core
uv sync --all-extras
cp ../../.env.example ../../.env
# Edit .env — add at least one provider API key
KS_DEV_MODE=true KS_DEV_OPENAI_API_KEY=sk-... uv run kestrel serve --reload
```

### Docker

```bash
git clone https://github.com/andber6/kestrel.git
cd kestrel
cp .env.example .env
# Edit .env — add at least one provider API key
docker compose up
```

Visit [http://localhost:8080/docs](http://localhost:8080/docs) for the interactive API explorer.

### Test it

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-openai-key" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "What is 2+2?"}]
  }'
```

### Python SDK

```bash
pip install kestrel-sdk
```

```python
import kestrel_sdk

client = kestrel_sdk.Client(
    api_key="ks-your-kestrel-key",
    provider_key="sk-your-openai-key",
    base_url="https://api.usekestrel.io/v1",
)

response = client.chat.completions.create(
    model="gpt-4o",  # ceiling — Kestrel may route to a cheaper model
    messages=[{"role": "user", "content": "What is 2+2?"}],
)
print(response.choices[0].message.content)
```

Async:

```python
import kestrel_sdk

client = kestrel_sdk.AsyncClient(
    api_key="ks-your-key",
    provider_key="sk-your-openai-key",
    base_url="https://api.usekestrel.io/v1",
)

response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

## Supported Providers

| Provider | Models | Format |
|----------|--------|--------|
| **OpenAI** | gpt-4o, gpt-4o-mini, o1, o3, o4 | Native (pass-through) |
| **Anthropic** | claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5 | Full translation (Messages API) |
| **Google Gemini** | gemini-2.5-pro, gemini-2.5-flash | Full translation (generateContent API) |
| **Groq** | llama-3.1-8b/70b, mixtral, gemma | OpenAI-compatible (field stripping) |
| **xAI** | grok-3, grok-3-mini, grok-4 | OpenAI-compatible (field stripping) |
| **Mistral** | mistral-large, mistral-small, codestral | OpenAI-compatible (field stripping) |
| **Cohere** | command-r-plus, command-r, command-light | Full translation (Chat V2 API) |
| **Together AI** | meta-llama/*, mistralai/*, qwen/* | OpenAI-compatible (field stripping) |

All providers expose the same OpenAI-compatible API. Send any supported model name and Kestrel auto-detects the provider and handles format translation.

## Routing

Every request is scored across 5 dimensions (each 1-5):

| Dimension | What it measures | Low score example | High score example |
|-----------|-----------------|-------------------|-------------------|
| Reasoning Depth | Multi-step logic needed | "What is 2+2?" | "Analyze strategic implications of..." |
| Output Complexity | Structure of expected response | Yes/no answer | Multi-section report with code |
| Domain Specificity | Specialized knowledge required | General chat | Legal/medical/financial analysis |
| Instruction Nuance | Precision of instruction following | Simple question | Complex system prompt with tools |
| Error Tolerance | Cost of imperfect response | Draft note | Production code, legal document |

The composite score (5-25) maps to a tier:

| Score | Tier | Example Models |
|-------|------|---------------|
| 0-8 | Economy | gpt-4o-mini, claude-haiku, gemini-flash, llama-3.1-8b |
| 9-14 | Standard | gpt-4o-mini, claude-haiku, gemini-flash, mistral-small |
| 15-25 | Premium | gpt-4o, claude-sonnet, gemini-pro, grok-3 |

**The model you specify is the ceiling.** If you send `model=gpt-4o` (Premium), a simple prompt may route to `gpt-4o-mini` (Economy). If you send `model=gpt-4o-mini` (Standard), the request will never route to a more expensive model.

## Reliability

- **Failover with backoff** — If a provider returns 429/5xx or times out, Kestrel retries with a fallback provider using exponential backoff with jitter (up to 2 retries)
- **Cross-provider fallback** — `gpt-4o` can fall back to `claude-sonnet-4-6` or `gemini-2.5-pro` if OpenAI is down
- **Health monitoring** — Background health checks ping all 8 providers every 30 seconds. Unhealthy providers are skipped during routing
- **Non-blocking logging** — Request logs are written asynchronously. A database outage never blocks API requests

### Health endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness probe — always returns `{"status": "ok"}` |
| `GET /ready` | Readiness probe — checks database connectivity, reports provider health. Returns 503 if DB is unreachable |

## CLI

```bash
kestrel serve                           # Start the proxy server
kestrel serve --port 9090 --reload      # Custom port with auto-reload
kestrel key generate --name "my-app"    # Generate an API key
kestrel key generate --name "multi" \
  --openai-key sk-... \
  --anthropic-key sk-ant-... \
  --xai-key xai-...                     # Key with multiple providers
kestrel key list                        # List all API keys
kestrel key revoke ks-xxxxx...          # Revoke a key
kestrel migrate                         # Run database migrations
kestrel logs prune --older-than 30d     # Delete old request logs
kestrel logs prune --older-than 7d --dry-run  # Preview deletion count
kestrel --version                       # Show version
```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `KS_DEV_MODE` | `false` | Bypass auth, use dev API keys |
| `KS_ROUTING_ENABLED` | `true` | Enable/disable automatic routing |
| `KS_ENCRYPTION_KEY` | — | Fernet key for encrypting provider keys at rest |
| `KS_DEV_OPENAI_API_KEY` | — | OpenAI API key (dev mode) |
| `KS_DEV_ANTHROPIC_API_KEY` | — | Anthropic API key (dev mode) |
| `KS_DEV_GEMINI_API_KEY` | — | Gemini API key (dev mode) |
| `KS_DEV_GROQ_API_KEY` | — | Groq API key (dev mode) |
| `KS_DEV_XAI_API_KEY` | — | xAI API key (dev mode) |
| `KS_DEV_MISTRAL_API_KEY` | — | Mistral API key (dev mode) |
| `KS_DEV_COHERE_API_KEY` | — | Cohere API key (dev mode) |
| `KS_DEV_TOGETHER_API_KEY` | — | Together AI API key (dev mode) |
| `KS_ROUTING_TIER_FLOOR` | — | Minimum tier (`economy`, `standard`, `premium`) |
| `KS_ROUTING_TIER_CEILING` | — | Maximum tier |

See `.env.example` for the full list.

## Architecture

```
packages/core/src/kestrel/
  app.py                 # FastAPI application factory
  config.py              # Settings (KS_ env vars)
  cli.py                 # CLI (serve, key, migrate)
  providers/             # LLM provider adapters (8 providers)
    openai.py            #   OpenAI (native pass-through)
    anthropic.py         #   Anthropic (full format translation)
    gemini.py            #   Google Gemini (full format translation)
    groq.py              #   Groq (OpenAI-compatible, field stripping)
    xai.py               #   xAI Grok (OpenAI-compatible, field stripping)
    mistral.py           #   Mistral (OpenAI-compatible, field stripping)
    cohere.py            #   Cohere (full format translation)
    together.py          #   Together AI (OpenAI-compatible, field stripping)
    base.py              #   Abstract LLMProvider interface
    openai_compat.py     #   Shared base for OpenAI-format APIs
  routing/               # Complexity analysis and model selection
    analyzer.py          #   Extract features from requests (structural + text-level)
    scorer.py            #   Rule-based 5-dimension scoring
    tier_resolver.py     #   Score → tier with ceiling logic
    model_selector.py    #   Tier → concrete model selection
    engine.py            #   Orchestrates the routing pipeline
  services/              # Business logic
    proxy.py             #   Request forwarding with failover
    provider_registry.py #   Model → provider mapping, health tracking
    health_check.py      #   Background provider health monitoring
    request_log.py       #   Async request/response logging
  auth/                  # API key authentication, encryption
  models/                # Pydantic models (OpenAI format), DB models
  routes/                # FastAPI route handlers
  middleware/            # Request ID, timing
```

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd packages/core
uv sync --all-extras    # Install all dependencies

# Install pre-commit hook (auto-formats with ruff)
./scripts/install-hooks.sh

uv run ruff check src/  # Lint
uv run ruff format src/ # Format
uv run mypy src/        # Type check (strict)
uv run pytest -v        # Test with coverage
```

167 tests, all mocked — no real API calls.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and how to add new providers.

## License

[MIT](LICENSE)
