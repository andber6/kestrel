# Quick Start

## Option 1: Docker

The fastest way to get a running proxy.

```bash
git clone https://github.com/andber6/kestrel.git
cd kestrel

# Configure
cp .env.example .env
# Edit .env — add at least one provider API key (e.g. KS_DEV_OPENAI_API_KEY)

# Start
docker compose up
```

Visit [http://localhost:8080/docs](http://localhost:8080/docs) for the interactive API explorer.

Verify it works:

```bash
# Health check
curl http://localhost:8080/health
# → {"status": "ok"}

# Chat completion (dev mode uses Authorization header as provider key)
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-openai-key" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "What is 2+2?"}]
  }'
```

## Option 2: Local Development

```bash
git clone https://github.com/andber6/kestrel.git
cd kestrel/packages/core

# Install dependencies
uv sync --all-extras

# Start the proxy in dev mode
KS_DEV_MODE=true KS_DEV_OPENAI_API_KEY=sk-your-key \
  uv run uvicorn kestrel.app:create_app --factory --reload --port 8080
```

Or use the Makefile (from the project root):

```bash
make install
make dev  # starts on port 8080 with --reload
```

## Option 3: Python SDK

```bash
pip install kestrel-sdk
```

```python
import kestrel_sdk

# Point at your running Kestrel proxy
client = kestrel_sdk.Client(
    api_key="ks-your-kestrel-key",
    provider_key="sk-your-openai-key",
    base_url="http://localhost:8080/v1",
)

# Use it exactly like the OpenAI client
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is 2+2?"}],
)
print(response.choices[0].message.content)
```

## Using Any Supported Model

Kestrel auto-detects the provider from the model name:

```python
# OpenAI
response = client.chat.completions.create(model="gpt-4o", messages=[...])

# Anthropic
response = client.chat.completions.create(model="claude-sonnet-4-6", messages=[...])

# Google Gemini
response = client.chat.completions.create(model="gemini-1.5-flash", messages=[...])

# Groq
response = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[...])
```

All requests and responses use the OpenAI format regardless of the underlying provider.

## Streaming

Streaming works exactly as with the OpenAI SDK:

```python
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## Next Steps

- [How routing works](routing.md)
- [Configuration reference](configuration.md)
- [Supported providers](providers.md)
