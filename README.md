# AgentRouter

**Drop-in LLM API proxy that routes requests to the cheapest capable model.**

AgentRouter sits between your AI agent and LLM providers. It intercepts every outgoing API request, classifies the complexity of the prompt, and automatically routes it to the cheapest model that can handle it. You change one line of code — your base URL — and start saving 50-80% on LLM API costs. The response format is identical. Streaming works. Function calling works. Your agent doesn't know routing happened.

## How It Works

1. **Receive** — Your agent sends a request to AgentRouter instead of directly to OpenAI/Anthropic/etc.
2. **Analyze** — Extract structural features: prompt length, tool presence, domain keywords, code blocks, conversation depth
3. **Score** — Rate complexity across 5 dimensions (reasoning depth, output complexity, domain specificity, instruction nuance, error tolerance)
4. **Route** — Map the score to a tier (Economy/Standard/Premium) and pick the cheapest model that fits, never exceeding the model you specified
5. **Forward** — Translate the request to the selected provider's format, forward it, translate the response back to OpenAI format

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/agentrouter/agentrouter.git
cd agentrouter
cp .env.example .env
# Edit .env — add at least one provider API key
docker compose up
```

Test it:

```bash
curl http://localhost:8080/health

curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-openai-key" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "What is 2+2?"}]
  }'
```

### Local Development

```bash
cd packages/core
uv sync --all-extras
cp ../../.env.example ../../.env
# Edit .env
AR_DEV_MODE=true AR_DEV_OPENAI_API_KEY=sk-... uv run uvicorn agentrouter.app:create_app --factory --reload --port 8080
```

### Python SDK

```bash
pip install agentrouter
```

```python
import agentrouter

client = agentrouter.Client(
    api_key="ar-your-agentrouter-key",
    provider_key="sk-your-openai-key",
    base_url="http://localhost:8080/v1",
)

response = client.chat.completions.create(
    model="gpt-4o",  # ceiling — AgentRouter may route to a cheaper model
    messages=[{"role": "user", "content": "What is 2+2?"}],
)
print(response.choices[0].message.content)
```

## Supported Providers

| Provider | Models | Format |
|----------|--------|--------|
| **OpenAI** | gpt-4o, gpt-4o-mini, o1, o3, o4 | Native (pass-through) |
| **Anthropic** | claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5 | Full translation (Messages API) |
| **Google Gemini** | gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-* | Full translation (generateContent API) |
| **Groq** | llama-3.1-8b/70b, mixtral, gemma | OpenAI-compatible (minor field stripping) |

All providers expose the same OpenAI-compatible API. Send any supported model name and AgentRouter auto-detects the provider and handles format translation.

## Routing

Every request is scored across 5 dimensions (each 1-5):

| Dimension | What it measures | Low score example | High score example |
|-----------|-----------------|-------------------|-------------------|
| Reasoning Depth | Multi-step logic needed | "What is 2+2?" | "Analyze strategic implications of..." |
| Output Complexity | Structure of expected response | Yes/no answer | Multi-section report |
| Domain Specificity | Specialized knowledge required | General chat | Legal/medical analysis |
| Instruction Nuance | Precision of instruction following | Simple question | Complex system prompt with tools |
| Error Tolerance | Cost of imperfect response | Draft note | Production code, legal document |

The composite score (5-25) maps to a tier:

| Score | Tier | Example Models |
|-------|------|---------------|
| 5-9 | Economy | gpt-4o-mini, claude-haiku, gemini-flash, llama-3.1-8b |
| 10-16 | Standard | gpt-4o-mini, claude-haiku, gemini-flash, llama-3.1-70b |
| 17-25 | Premium | gpt-4o, claude-sonnet, gemini-pro |

**The model you specify is the ceiling.** If you send `model=gpt-4o` (Premium), a simple prompt may route to `gpt-4o-mini` (Economy). If you send `model=gpt-4o-mini` (Standard), the request will never route to a more expensive model.

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `AR_DEV_MODE` | `false` | Bypass auth, use dev API keys |
| `AR_ROUTING_ENABLED` | `true` | Enable/disable automatic routing |
| `AR_DEV_OPENAI_API_KEY` | — | OpenAI API key (dev mode) |
| `AR_DEV_ANTHROPIC_API_KEY` | — | Anthropic API key (dev mode) |
| `AR_DEV_GEMINI_API_KEY` | — | Gemini API key (dev mode) |
| `AR_DEV_GROQ_API_KEY` | — | Groq API key (dev mode) |
| `AR_ROUTING_TIER_FLOOR` | — | Minimum tier (`economy`, `standard`, `premium`) |
| `AR_ROUTING_TIER_CEILING` | — | Maximum tier |

See `.env.example` for the full list.

## Architecture

```
packages/core/src/agentrouter/
  app.py                 # FastAPI application factory
  config.py              # Settings (AR_ env vars)
  providers/             # LLM provider adapters
    openai.py            #   OpenAI (native pass-through)
    anthropic.py         #   Anthropic (full format translation)
    gemini.py            #   Google Gemini (full format translation)
    groq.py              #   Groq (OpenAI-compatible, field stripping)
    base.py              #   Abstract LLMProvider interface
    openai_compat.py     #   Shared base for OpenAI-format APIs
  routing/               # Complexity analysis and model selection
    analyzer.py          #   Extract features from requests
    scorer.py            #   Rule-based 5-dimension scoring
    tier_resolver.py     #   Score → tier with ceiling logic
    model_selector.py    #   Tier → concrete model selection
    engine.py            #   Orchestrates the routing pipeline
  services/              # Business logic
    proxy.py             #   Request forwarding with failover
    provider_registry.py #   Model → provider mapping, health tracking
    health_check.py      #   Background provider health monitoring
    request_log.py       #   Async request/response logging
  auth/                  # API key authentication
  models/                # Pydantic models (OpenAI format), DB models
  routes/                # FastAPI route handlers
  middleware/            # Request ID, timing
```

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd packages/core
uv sync --all-extras    # Install all dependencies

make lint               # Ruff check
make format             # Ruff format
make typecheck          # Mypy strict mode
make test               # Pytest with coverage
```

128 tests, ~78% coverage. All tests use mocked providers — no real API calls.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and how to add new providers.

## License

[MIT](LICENSE)
