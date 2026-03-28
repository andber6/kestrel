# Providers

Kestrel supports 4 LLM providers with automatic format translation. All requests and responses use the OpenAI Chat Completions format.

## Supported Providers

### OpenAI

- **Format**: Native (no translation needed)
- **Auth**: Bearer token
- **Models**: gpt-4o, gpt-4o-mini, o1, o3, o4
- **Features**: All OpenAI features supported (streaming, tools, JSON mode, vision, logprobs)
- **Adapter**: `providers/openai.py` (extends `OpenAICompatibleProvider`)

### Anthropic

- **Format**: Full translation (OpenAI ↔ Anthropic Messages API)
- **Auth**: `x-api-key` header
- **Models**: claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5
- **Translation details**:
  - System messages extracted to Anthropic's top-level `system` parameter
  - `tool_calls` → `tool_use` content blocks
  - `tool` role messages → `tool_result` content blocks (consecutive results merged)
  - Streaming: 6 Anthropic event types translated to OpenAI chunk format
  - `max_tokens` defaults to 4096 when not specified (required by Anthropic)
  - `finish_reason` mapping: `end_turn`→`stop`, `tool_use`→`tool_calls`, `max_tokens`→`length`
- **Adapter**: `providers/anthropic.py`

### Google Gemini

- **Format**: Full translation (OpenAI ↔ Gemini generateContent API)
- **Auth**: API key as query parameter
- **Models**: gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-pro, gemini-2.0-flash
- **Translation details**:
  - `messages` → `contents` with `parts` format
  - `assistant` role → `model` role
  - `tool_calls` → `functionCall` parts
  - `tool` results → `functionResponse` parts
  - Streaming: cumulative content converted to delta chunks
  - System messages → `systemInstruction`
  - `response_format: json_object` → `responseMimeType: application/json`
- **Adapter**: `providers/gemini.py`

### Groq

- **Format**: OpenAI-compatible (minor field stripping)
- **Auth**: Bearer token
- **Models**: llama-3.1-8b-instant, llama-3.1-70b-versatile, mixtral-8x7b, gemma
- **Stripped fields**: `logprobs`, `top_logprobs`, `logit_bias`
- **Downgraded**: `json_schema` response format → `json_object`
- **Adapter**: `providers/groq.py` (extends `OpenAICompatibleProvider`)

## Adding a New Provider

See [CONTRIBUTING.md](../CONTRIBUTING.md#adding-a-new-provider) for step-by-step instructions.

### Quick Overview

For **OpenAI-compatible APIs** (same request/response format):

1. Subclass `OpenAICompatibleProvider` from `providers/openai_compat.py`
2. Override `translate_request()` to strip unsupported fields
3. See `providers/groq.py` for an example (~40 lines)

For **non-OpenAI APIs** (different format):

1. Subclass `LLMProvider` from `providers/base.py`
2. Implement: `chat_completion()`, `chat_completion_stream()`, `translate_request()`, `translate_response()`
3. See `providers/anthropic.py` for a complete example

## Provider Health & Failover

Kestrel monitors provider health with background pings every 30 seconds. If a provider returns 429/5xx or times out, the request automatically fails over to an equivalent model on a different provider.

Failover equivalences:

| Primary | Fallback 1 | Fallback 2 |
|---------|-----------|-----------|
| gpt-4o | claude-sonnet-4-6 | gemini-1.5-pro |
| claude-sonnet-4-6 | gpt-4o | gemini-1.5-pro |
| gpt-4o-mini | claude-haiku-4-5 | gemini-1.5-flash |
| llama-3.1-8b-instant | gpt-4o-mini | gemini-1.5-flash |

Maximum 2 retry attempts per request.
