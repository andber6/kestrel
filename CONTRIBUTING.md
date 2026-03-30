# Contributing to Kestrel

## Development Setup

1. Clone the repo and install dependencies:

```bash
git clone https://github.com/usekestrel/kestrel.git
cd kestrel/packages/core
uv sync --all-extras
```

2. Copy the env template:

```bash
cp ../../.env.example ../../.env
# Edit .env with your provider API keys
```

3. Run the tests:

```bash
make test
```

All 145 tests use mocked providers — no real API calls, no database needed.

## Code Style

- **Formatter/linter:** [Ruff](https://docs.astral.sh/ruff/) — `make lint` to check, `make format` to fix
- **Type checker:** [mypy](https://mypy-lang.org/) in strict mode — `make typecheck`
- **Line length:** 99 characters
- **Python:** 3.12+ with modern syntax (`X | Y` unions, `StrEnum`, etc.)

## Adding a New Provider

1. **Create the adapter** in `src/kestrel/providers/your_provider.py`

   - For OpenAI-compatible APIs (same request/response format), subclass `OpenAICompatibleProvider` from `providers/openai_compat.py` and override `translate_request()` to strip unsupported fields. See `providers/groq.py` for an example.
   - For non-OpenAI APIs, subclass `LLMProvider` from `providers/base.py` and implement all methods: `chat_completion()`, `chat_completion_stream()`, `translate_request()`, `translate_response()`. See `providers/anthropic.py` for a complete example.

2. **Register in the provider registry** at `services/provider_registry.py`:
   - Add model prefixes to `_MODEL_PROVIDER_MAP`
   - Add failover entries to `MODEL_EQUIVALENTS`
   - Add construction logic in `ProviderRegistry.from_settings()`

3. **Add config** in `config.py`:
   - Add `your_provider_base_url` setting
   - Add `dev_your_provider_api_key` setting

4. **Add tier mappings** in `routing/tier_resolver.py`:
   - Add your models to `_MODEL_TIER_MAP`

5. **Write tests** in `tests/test_providers_your_provider.py`:
   - Test `translate_request()` — verify correct format translation
   - Test `translate_response()` — verify OpenAI format output
   - Test edge cases (missing fields, unsupported features)

6. **Update documentation** — add the provider to the table in `README.md` and `docs/providers.md`

## Pull Request Process

1. Branch from `main`
2. Make your changes
3. Ensure all checks pass:

```bash
make lint && make typecheck && make test
```

4. Submit a PR with a clear description of what and why

## Request Flow

```
HTTP Request
  → routes/chat.py (FastAPI endpoint)
    → services/proxy.py (orchestration)
      → routing/engine.py (if routing enabled)
        → routing/analyzer.py (extract features)
        → routing/scorer.py (score 5 dimensions)
        → routing/tier_resolver.py (score → tier + ceiling)
        → routing/model_selector.py (tier → model)
      → providers/*.py (format translation + HTTP call)
    → response returned in OpenAI format
```
