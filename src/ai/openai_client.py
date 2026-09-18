"""
OP(AI)UM — OpenAI Client

Wrapper around the OpenAI Chat Completions API (and any OpenAI-compatible
endpoint such as Ollama, LM Studio, OpenRouter or Groq via a custom base URL) for:
1. Chat completions with function calling — streaming and non-streaming
2. An automatic tool-execution loop with live callbacks
3. Speech transcription (gpt-4o-transcribe / whisper-1)
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from typing import Any

from loguru import logger

from src.config.config_manager import ConfigManager

# Models that only accept the default sampling temperature (reasoning family).
_NO_TEMPERATURE_PREFIXES = ("gpt-5", "o1", "o3", "o4")

TextCallback = Callable[[str], None]
ToolStartCallback = Callable[[str, dict[str, Any]], None]
ToolEndCallback = Callable[[str, dict[str, Any], Any], None]
CancelCheck = Callable[[], bool]


class OpenAIClient:
    """OpenAI API client for chat completions and transcription."""

    def __init__(self, config: ConfigManager) -> None:
        self._config = config
        self._client: Any | None = None

    # === Client lifecycle ===

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            api_key = self._config.get_api_key()
            base_url = (self._config.settings.ai.api_base_url or "").strip() or None
            if not api_key:
                if base_url:
                    # Local OpenAI-compatible servers usually ignore the key but the SDK requires one.
                    api_key = "opaium-local"
                else:
                    raise ValueError("OpenAI API key not configured. Add it in Settings.")
            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self._config.settings.ai.request_timeout,
                max_retries=2,
            )
        return self._client

    def reset_client(self) -> None:
        self._client = None

    @property
    def model(self) -> str:
        return self._config.settings.ai.ai_model

    @property
    def transcription_model(self) -> str:
        value = self._config.settings.ai.transcription_model
        return str(value.value) if hasattr(value, "value") else str(value)

    @property
    def base_url(self) -> str:
        return (self._config.settings.ai.api_base_url or "").strip()

    @property
    def is_custom_endpoint(self) -> bool:
        return bool(self.base_url)

    def is_configured(self) -> bool:
        return bool(self._config.get_api_key()) or self.is_custom_endpoint

    @staticmethod
    def supports_temperature(model: str) -> bool:
        m = (model or "").lower()
        return not any(m.startswith(p) for p in _NO_TEMPERATURE_PREFIXES)

    def _build_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        tool_choice: str,
        temperature: float | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if temperature is not None and self.supports_temperature(self.model):
            kwargs["temperature"] = temperature
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return kwargs

    # === Single completion ===

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        temperature: float | None = 0.3,
        max_tokens: int = 4096,
        on_text_delta: TextCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> dict[str, Any]:
        """
        Send a chat completion request with optional function calling.

        When `on_text_delta` is provided the request is streamed and text
        chunks are pushed to the callback as they arrive.
        """
        client = self._get_client()
        kwargs = self._build_kwargs(messages, tools, tool_choice, temperature, max_tokens)

        try:
            logger.debug(f"Chat: model={self.model}, msgs={len(messages)}, tools={len(tools or [])}")
            if on_text_delta is not None:
                return self._stream_completion(client, kwargs, on_text_delta, should_cancel)
            return self._blocking_completion(client, kwargs)
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            raise

    def _blocking_completion(self, client: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        result: dict[str, Any] = {
            "message": {
                "role": choice.message.role,
                "content": choice.message.content,
                "tool_calls": None,
            },
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            "finish_reason": choice.finish_reason,
        }
        if choice.message.tool_calls:
            result["message"]["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.message.tool_calls
            ]
        logger.debug(f"Response: finish={result['finish_reason']}, tokens={result['usage']['total_tokens']}")
        return result

    def _stream_completion(
        self,
        client: Any,
        kwargs: dict[str, Any],
        on_text_delta: TextCallback,
        should_cancel: CancelCheck | None,
    ) -> dict[str, Any]:
        """Stream a completion, re-assembling text and tool-call deltas."""
        stream = client.chat.completions.create(stream=True, stream_options={"include_usage": True}, **kwargs)

        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        cancelled = False

        for chunk in stream:
            if should_cancel is not None and should_cancel():
                cancelled = True
                break

            if getattr(chunk, "usage", None):
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens or 0,
                    "completion_tokens": chunk.usage.completion_tokens or 0,
                    "total_tokens": chunk.usage.total_tokens or 0,
                }

            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if delta is None:
                continue

            if delta.content:
                content_parts.append(delta.content)
                on_text_delta(delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index if tc.index is not None else 0
                    entry = tool_calls.setdefault(
                        idx,
                        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                    )
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.type:
                        entry["type"] = tc.type
                    if tc.function:
                        if tc.function.name:
                            entry["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            entry["function"]["arguments"] += tc.function.arguments

        with contextlib.suppress(Exception):
            stream.close()

        ordered_calls = [tool_calls[i] for i in sorted(tool_calls)] if tool_calls else None
        if cancelled:
            ordered_calls = None
            finish_reason = "cancelled"

        result: dict[str, Any] = {
            "message": {
                "role": "assistant",
                "content": "".join(content_parts) or None,
                "tool_calls": ordered_calls,
            },
            "usage": usage,
            "finish_reason": finish_reason,
        }
        logger.debug(f"Streamed response: finish={finish_reason}, tool_calls={len(ordered_calls or [])}")
        return result

    # === Tool loop ===

    def chat_with_tool_loop(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Any,
        max_rounds: int = 5,
        stream: bool = False,
        on_text_delta: TextCallback | None = None,
        on_tool_start: ToolStartCallback | None = None,
        on_tool_end: ToolEndCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> dict[str, Any]:
        """
        Chat completion with automatic tool execution loop.

        Sends the request, executes tool calls, feeds results back and repeats
        until a final text response or `max_rounds`. Returns a dict with:
            message     — the final assistant message
            transcript  — every message generated during the loop (assistant
                          tool-call messages + tool results + final message), in
                          order, ready to be appended to conversation memory
            usage       — token usage of the last call
            cancelled   — True when the user stopped generation
        """
        current_messages = list(messages)
        transcript: list[dict[str, Any]] = []
        response: dict[str, Any] = {}
        delta_cb = on_text_delta if stream else None

        for round_num in range(max_rounds):
            if should_cancel is not None and should_cancel():
                return self._cancelled_response(transcript)

            response = self.chat_completion(
                current_messages,
                tools=tools,
                tool_choice="auto",
                on_text_delta=delta_cb,
                should_cancel=should_cancel,
            )
            if response.get("finish_reason") == "cancelled":
                return self._cancelled_response(transcript, response["message"].get("content"))

            tool_calls = response["message"].get("tool_calls")
            if not tool_calls:
                final = {"role": "assistant", "content": response["message"].get("content") or ""}
                transcript.append(final)
                response["transcript"] = transcript
                response["cancelled"] = False
                return response

            assistant_msg = {
                "role": "assistant",
                "content": response["message"].get("content"),
                "tool_calls": tool_calls,
            }
            current_messages.append(assistant_msg)
            transcript.append(assistant_msg)

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"] or "{}")
                    if not isinstance(func_args, dict):
                        func_args = {}
                except json.JSONDecodeError:
                    func_args = {}

                logger.info(f"Tool call [{round_num + 1}]: {func_name}")
                if on_tool_start is not None:
                    on_tool_start(func_name, func_args)

                result_obj: Any = None
                try:
                    result_obj = tool_executor.execute_tool(func_name, func_args)
                    if hasattr(result_obj, "to_dict"):
                        result_str = json.dumps(result_obj.to_dict(), default=str)
                    elif isinstance(result_obj, str):
                        result_str = result_obj
                    else:
                        result_str = json.dumps(result_obj, default=str)
                except Exception as e:
                    result_str = json.dumps({"success": False, "error": str(e)})
                    logger.error(f"Tool error: {func_name} -> {e}")

                if on_tool_end is not None:
                    on_tool_end(func_name, func_args, result_obj if result_obj is not None else result_str)

                tool_msg = {"role": "tool", "tool_call_id": tc["id"], "content": result_str}
                current_messages.append(tool_msg)
                transcript.append(tool_msg)

        logger.warning(f"Max tool rounds ({max_rounds}) reached.")
        try:
            current_messages.append(
                {
                    "role": "user",
                    "content": "You reached the tool-call limit for this turn. Summarize what you did and what remains.",
                }
            )
            response = self.chat_completion(current_messages, tools=None, on_text_delta=delta_cb)
        except Exception as e:
            logger.error(f"Final summary call failed: {e}")
            if not response.get("message", {}).get("content"):
                response = {
                    "message": {
                        "content": "I completed several operations but reached the processing limit. Please check the results.",
                        "tool_calls": None,
                    },
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "finish_reason": "length",
                }
        transcript.append({"role": "assistant", "content": response["message"].get("content") or ""})
        response["transcript"] = transcript
        response["cancelled"] = False
        return response

    @staticmethod
    def _cancelled_response(transcript: list[dict[str, Any]], partial: str | None = None) -> dict[str, Any]:
        text = (partial or "").strip()
        if text:
            transcript.append({"role": "assistant", "content": text})
        return {
            "message": {"content": text, "tool_calls": None},
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "finish_reason": "cancelled",
            "transcript": transcript,
            "cancelled": True,
        }

    # === Transcription ===

    def transcribe_audio(self, audio_file_path: str, language: str = "en") -> str:
        """Transcribe audio file using configured transcription model."""
        client = self._get_client()
        try:
            with open(audio_file_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model=self.transcription_model,
                    file=audio_file,
                    language=language,
                    response_format="text",
                )
                text = str(response).strip()
                logger.debug(f"Transcribed: {text[:100]}...")
                return text
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

    # === Diagnostics ===

    def test_connection(self) -> tuple[bool, str]:
        try:
            self.chat_completion(
                [{"role": "user", "content": "Reply with the single word OK."}],
                max_tokens=16,
                temperature=0,
            )
            where = self.base_url or "api.openai.com"
            return True, f"Connected to {where} — model {self.model}"
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {e}"

    def list_models(self) -> list[str]:
        """Best-effort model listing (works on OpenAI and most compatible servers)."""
        try:
            client = self._get_client()
            models = client.models.list()
            ids = sorted({m.id for m in models.data if getattr(m, "id", None)})
            return ids
        except Exception as e:
            logger.debug(f"Model listing failed: {e}")
            return []
