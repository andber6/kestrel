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

## Learn More

- [Kestrel documentation](https://github.com/usekestrel/kestrel)
- [How routing works](https://github.com/usekestrel/kestrel/blob/main/docs/routing.md)
