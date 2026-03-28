# Python SDK

The AgentRouter Python SDK is a thin wrapper over the [OpenAI Python SDK](https://github.com/openai/openai-python). It configures the client to route through AgentRouter — all `openai.OpenAI` methods work as expected.

## Installation

```bash
pip install agentrouter
```

## Basic Usage

```python
import agentrouter

client = agentrouter.Client(
    api_key="ar-your-agentrouter-key",      # AgentRouter API key
    provider_key="sk-your-openai-key",       # LLM provider API key
    base_url="http://localhost:8080/v1",     # AgentRouter proxy URL
)

response = client.chat.completions.create(
    model="gpt-4o",    # model ceiling — routing may use a cheaper model
    messages=[{"role": "user", "content": "What is 2+2?"}],
)
print(response.choices[0].message.content)
```

## Async Usage

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

## Pass-Through Mode

If you don't have an AgentRouter API key yet, pass the provider key directly:

```python
client = agentrouter.Client(
    api_key="sk-your-openai-key",           # Provider key directly
    base_url="http://localhost:8080/v1",
)
```

In dev mode (`AR_DEV_MODE=true`), this sends the provider key in the Authorization header and bypasses AgentRouter authentication.

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

## Using with LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o",
    openai_api_base="http://localhost:8080/v1",
    openai_api_key="sk-your-openai-key",
)
```

## API Reference

### `agentrouter.Client`

Subclass of `openai.OpenAI`. All OpenAI client methods are available.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `api_key` | `str` | AgentRouter key (`ar-...`) or provider key (`sk-...`) |
| `provider_key` | `str` | LLM provider API key (required with AR key) |
| `base_url` | `str` | AgentRouter URL (default: `http://localhost:8080/v1`) |
| `**kwargs` | | Passed to `openai.OpenAI` |

### `agentrouter.AsyncClient`

Async version. Subclass of `openai.AsyncOpenAI`. Same parameters as `Client`.
