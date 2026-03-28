# AgentRouter Python SDK

Drop-in LLM cost optimization. Route requests to the cheapest capable model with one line of code.

## Install

```bash
pip install agentrouter
```

## Usage

```python
import agentrouter

client = agentrouter.Client(
    api_key="ar-your-agentrouter-key",
    provider_key="sk-your-openai-key",
    base_url="http://localhost:8080/v1",
)

# Send requests as usual — AgentRouter handles routing
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is 2+2?"}],
)
```

The SDK is a thin wrapper over the [OpenAI Python SDK](https://github.com/openai/openai-python). All `openai.OpenAI` methods work as expected.

## Async

```python
import agentrouter

client = agentrouter.AsyncClient(
    api_key="ar-your-key",
    provider_key="sk-your-openai-key",
)

response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

## Learn More

- [AgentRouter documentation](https://github.com/agentrouter/agentrouter)
- [How routing works](https://github.com/agentrouter/agentrouter/blob/main/docs/routing.md)
