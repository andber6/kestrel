# Configuration

All settings use environment variables with the `KS_` prefix. Copy `.env.example` to `.env` to get started.

## Core Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KS_DATABASE_URL` | string | `postgresql+asyncpg://kestrel:kestrel@localhost:5432/kestrel` | PostgreSQL connection URL |
| `KS_LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `KS_DEV_MODE` | bool | `false` | Bypass authentication, use dev API keys |

## Provider API Keys

In dev mode, set these directly. In production, provider keys are stored per-operator in the database.

| Variable | Description |
|----------|-------------|
| `KS_DEV_OPENAI_API_KEY` | OpenAI API key |
| `KS_DEV_ANTHROPIC_API_KEY` | Anthropic API key |
| `KS_DEV_GEMINI_API_KEY` | Google Gemini API key |
| `KS_DEV_GROQ_API_KEY` | Groq API key |
| `KS_DEV_XAI_API_KEY` | xAI API key |
| `KS_DEV_MISTRAL_API_KEY` | Mistral API key |
| `KS_DEV_COHERE_API_KEY` | Cohere API key |
| `KS_DEV_TOGETHER_API_KEY` | Together AI API key |

## Provider Base URLs

Override these if you're using a proxy or custom endpoint.

| Variable | Default |
|----------|---------|
| `KS_OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `KS_ANTHROPIC_BASE_URL` | `https://api.anthropic.com/v1` |
| `KS_GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` |
| `KS_GROQ_BASE_URL` | `https://api.groq.com/openai/v1` |
| `KS_XAI_BASE_URL` | `https://api.x.ai/v1` |
| `KS_MISTRAL_BASE_URL` | `https://api.mistral.ai/v1` |
| `KS_COHERE_BASE_URL` | `https://api.cohere.com/v2` |
| `KS_TOGETHER_BASE_URL` | `https://api.together.xyz/v1` |

## Routing

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KS_ROUTING_ENABLED` | bool | `true` | Enable automatic complexity-based routing |
| `KS_ROUTING_ALLOWED_PROVIDERS` | string | _(empty = all)_ | Comma-separated list of providers to consider for routing |
| `KS_ROUTING_DENIED_PROVIDERS` | string | _(empty)_ | Comma-separated list of providers to exclude from routing |
| `KS_ROUTING_TIER_FLOOR` | string | _(empty)_ | Minimum tier: `economy`, `standard`, or `premium` |
| `KS_ROUTING_TIER_CEILING` | string | _(empty)_ | Maximum tier (overrides model ceiling if lower) |

## Health Checks

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KS_HEALTH_CHECK_INTERVAL` | int | `30` | Seconds between provider health pings |
