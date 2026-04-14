# Kestrel Python SDK

Drop-in LLM cost optimization. Route requests to the cheapest capable model with one line of code.

## Install

```bash
pip install kestrel-sdk
```

## Usage

```python
import kestrel_sdk

client = kestrel_sdk.Client(
    api_key="ks-your-kestrel-key",
    provider_key="sk-your-openai-key",
    base_url="http://localhost:8080/v1",
)

# Send requests as usual — Kestrel handles routing
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is 2+2?"}],
)
```

The SDK is a thin wrapper over the [OpenAI Python SDK](https://github.com/openai/openai-python). All `openai.OpenAI` methods work as expected.

## Async

```python
import kestrel_sdk

client = kestrel_sdk.AsyncClient(
    api_key="ks-your-key",
    provider_key="sk-your-openai-key",
)

response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

## Streaming

```python
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
)

for chunk in stream:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)
```

## Function Calling

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's the weather in NYC?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    }],
)
```

## Pass-Through Mode

If you don't have a Kestrel API key yet, pass the provider key directly:

```python
client = kestrel_sdk.Client(
    api_key="sk-your-openai-key",
    base_url="http://localhost:8080/v1",
)
```

In dev mode (`KS_DEV_MODE=true`), this sends the provider key in the Authorization header and bypasses Kestrel authentication.

## Learn More

- [Kestrel documentation](https://github.com/andber6/kestrel)
- [How routing works](https://github.com/andber6/kestrel/blob/main/docs/routing.md)
