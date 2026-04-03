"""Pydantic models for OpenAI Chat Completions API compatibility."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class FunctionDefinition(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None
    strict: bool | None = None


class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: FunctionDefinition


class TextContentPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageURL(BaseModel):
    url: str
    detail: Literal["auto", "low", "high"] | None = None


class ImageContentPart(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageURL


ContentPart = Annotated[TextContentPart | ImageContentPart, Field(discriminator="type")]


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "developer"]
    content: str | list[ContentPart] | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    model_config = ConfigDict(extra="allow")


class ResponseFormat(BaseModel):
    type: Literal["text", "json_object", "json_schema"] = "text"
    json_schema: dict[str, Any] | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str = Field(max_length=256)
    messages: list[ChatMessage] = Field(max_length=1024)
    temperature: float | None = None
    top_p: float | None = None
    n: int | None = Field(default=None, le=8)
    stream: bool | None = None
    stream_options: dict[str, Any] | None = None
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    logit_bias: dict[str, float] | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = Field(default=None, le=20)
    user: str | None = Field(default=None, max_length=256)
    tools: list[ToolDefinition] | None = Field(default=None, max_length=128)
    tool_choice: str | dict[str, Any] | None = None
    response_format: ResponseFormat | None = None
    seed: int | None = None

    # Forward unknown fields from newer OpenAI SDK versions
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Response models (non-streaming)
# ---------------------------------------------------------------------------


class ChoiceMessage(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    refusal: str | None = None

    model_config = ConfigDict(extra="allow")


class Choice(BaseModel):
    index: int
    message: ChoiceMessage
    finish_reason: str | None = None
    logprobs: dict[str, Any] | None = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    model_config = ConfigDict(extra="allow")


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    system_fingerprint: str | None = None

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Streaming response models
# ---------------------------------------------------------------------------


class DeltaMessage(BaseModel):
    role: str | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None

    model_config = ConfigDict(extra="allow")


class StreamChoice(BaseModel):
    index: int
    delta: DeltaMessage
    finish_reason: str | None = None
    logprobs: dict[str, Any] | None = None


class ChatCompletionChunk(BaseModel):
    """A single SSE chunk in a streaming chat completion response."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]
    system_fingerprint: str | None = None
    usage: Usage | None = None

    model_config = ConfigDict(extra="allow")
