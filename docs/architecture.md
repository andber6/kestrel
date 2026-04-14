# Architecture

## Directory Structure

```
packages/core/src/kestrel/
  app.py                    FastAPI application factory + lifespan management
  config.py                 Settings loaded from KS_ environment variables
  dependencies.py           FastAPI dependency injection (auth, proxy service)

  auth/
    api_key.py              API key verification (two auth patterns)

  routes/
    chat.py                 POST /v1/chat/completions endpoint

  services/
    proxy.py                Core orchestration: routing → provider selection → forwarding
    provider_registry.py    Model → provider mapping, health tracking, failover
    health_check.py         Background task: ping providers every 30s
    request_log.py          Async fire-and-forget logging to PostgreSQL

  routing/
    analyzer.py             Extract ~15 structural features from a request
    scorer.py               Rule-based 5-dimension complexity scoring
    tier_resolver.py        Score → tier mapping with ceiling logic
    model_selector.py       Tier → concrete model selection
    engine.py               Orchestrates analyze → score → resolve → select
    models.py               Data types: Tier, RequestFeatures, RoutingScores, etc.

  providers/
    base.py                 Abstract LLMProvider interface
    openai_compat.py        Shared base for OpenAI-format APIs (HTTP mechanics)
    openai.py               OpenAI adapter (native pass-through)
    anthropic.py            Anthropic adapter (full format translation)
    gemini.py               Google Gemini adapter (full format translation)
    groq.py                 Groq adapter (OpenAI-compat, strips unsupported fields)
    xai.py                  xAI Grok adapter (OpenAI-compat)
    mistral.py              Mistral adapter (OpenAI-compat)
    cohere.py               Cohere adapter (full format translation)
    together.py             Together AI adapter (OpenAI-compat)

  models/
    openai.py               Pydantic models for OpenAI Chat Completions API
    db.py                   SQLAlchemy ORM models (ApiKey, RequestLog)

  middleware/
    logging.py              Request ID + response timing headers

  db/
    session.py              Async SQLAlchemy engine + session factory
```

## Request Lifecycle

```
1. HTTP POST /v1/chat/completions
   │
2. ├─ Middleware: assign request ID, start timer
   │
3. ├─ Authentication (dependencies.py → auth/api_key.py)
   │   ├─ Dev mode: bypass, use dev keys
   │   ├─ Pattern 1: X-Kestrel-Key + Authorization (provider key)
   │   └─ Pattern 2: Authorization: Bearer ks-... (provider key from DB)
   │
4. ├─ Proxy Service (services/proxy.py)
   │   │
   │   ├─ Build provider registry with operator's API keys
   │   │
   │   ├─ Routing (if enabled)
   │   │   ├─ Analyze request features (routing/analyzer.py)
   │   │   ├─ Score 5 dimensions (routing/scorer.py)
   │   │   ├─ Resolve tier + apply ceiling (routing/tier_resolver.py)
   │   │   └─ Select cheapest model for tier (routing/model_selector.py)
   │   │
   │   ├─ Build attempt list (primary + failover models)
   │   │
   │   └─ For each attempt:
   │       ├─ Get provider for model (provider_registry.py)
   │       ├─ Translate request to provider format
   │       ├─ Forward to upstream API
   │       ├─ Translate response to OpenAI format
   │       ├─ On success: log, return response
   │       └─ On 429/5xx/timeout: mark unhealthy, try next
   │
5. ├─ Fire-and-forget: log request to PostgreSQL
   │
6. └─ Return response (JSON or SSE stream)
```

## Key Design Decisions

- **OpenAI format as the standard**: All requests/responses use the OpenAI Chat Completions API format, regardless of the underlying provider. This makes the proxy truly drop-in.

- **`extra="allow"` on request models**: Unknown fields from newer OpenAI SDK versions are forwarded transparently, not rejected.

- **Fire-and-forget logging**: The response is returned to the client before the log write completes. If the database is down, the proxy still works.

- **Scorer protocol**: The `Scorer` interface (`routing/models.py`) allows the rule-based heuristics to be replaced by an ML classifier without changing any other code.

- **Model-as-ceiling**: The requested model determines the maximum tier. Routing only goes cheaper, never more expensive.
