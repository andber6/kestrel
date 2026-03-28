# Configuration

All settings use environment variables with the `AR_` prefix. Copy `.env.example` to `.env` to get started.

## Core Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AR_DATABASE_URL` | string | `postgresql+asyncpg://agentrouter:agentrouter@localhost:5432/agentrouter` | PostgreSQL connection URL |
| `AR_LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `AR_DEV_MODE` | bool | `false` | Bypass authentication, use dev API keys |

## Provider API Keys

In dev mode, set these directly. In production, provider keys are stored per-operator in the database.

| Variable | Description |
|----------|-------------|
| `AR_DEV_OPENAI_API_KEY` | OpenAI API key |
| `AR_DEV_ANTHROPIC_API_KEY` | Anthropic API key |
| `AR_DEV_GEMINI_API_KEY` | Google Gemini API key |
| `AR_DEV_GROQ_API_KEY` | Groq API key |

## Provider Base URLs

Override these if you're using a proxy or custom endpoint.

| Variable | Default |
|----------|---------|
| `AR_OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `AR_ANTHROPIC_BASE_URL` | `https://api.anthropic.com/v1` |
| `AR_GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` |
| `AR_GROQ_BASE_URL` | `https://api.groq.com/openai/v1` |

## Routing

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AR_ROUTING_ENABLED` | bool | `true` | Enable automatic complexity-based routing |
| `AR_ROUTING_ALLOWED_PROVIDERS` | string | _(empty = all)_ | Comma-separated list of providers to consider for routing |
| `AR_ROUTING_DENIED_PROVIDERS` | string | _(empty)_ | Comma-separated list of providers to exclude from routing |
| `AR_ROUTING_TIER_FLOOR` | string | _(empty)_ | Minimum tier: `economy`, `standard`, or `premium` |
| `AR_ROUTING_TIER_CEILING` | string | _(empty)_ | Maximum tier (overrides model ceiling if lower) |

## Health Checks

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AR_HEALTH_CHECK_INTERVAL` | int | `30` | Seconds between provider health pings |
