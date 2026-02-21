"""
OP(AI)UM — OpenAI Client

Wrapper around the OpenAI API for:
1. GPT-5-2 chat completions with function calling
2. Speech transcription (gpt-4o-transcribe / whisper-1)
"""

from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger
from src.config.config_manager import ConfigManager


class OpenAIClient:
    """OpenAI API client for chat completions and transcription."""

    def __init__(self, config: ConfigManager) -> None:
        self._config = config
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI
            api_key = self._config.get_api_key()
            if not api_key:
                raise ValueError("OpenAI API key not configured. Add it in Settings.")
            self._client = OpenAI(
                api_key=api_key,
                timeout=self._config.settings.ai.request_timeout,
            )
        return self._client

    def reset_client(self) -> None:
        self._client = None

    @property
    def model(self) -> str:
        return self._config.settings.ai.ai_model

    @property
    def transcription_model(self) -> str:
        return self._config.settings.ai.transcription_model

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send a chat completion request with optional function calling."""
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            logger.debug(f"Chat: model={self.model}, msgs={len(messages)}, tools={len(tools or [])}")
            response = client.chat.completions.create(**kwargs)

            result: dict[str, Any] = {
                "message": {
                    "role": response.choices[0].message.role,
                    "content": response.choices[0].message.content,
                    "tool_calls": None,
                },
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                "finish_reason": response.choices[0].finish_reason,
            }

            if response.choices[0].message.tool_calls:
                result["message"]["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response.choices[0].message.tool_calls
                ]

            logger.debug(f"Response: finish={result['finish_reason']}, tokens={result['usage']['total_tokens']}")
            return result

        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            raise

    def chat_with_tool_loop(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Any,
        max_rounds: int = 5,
    ) -> dict[str, Any]:
        """
        Chat completion with automatic tool execution loop.
        Sends request, executes tool calls, feeds results back, repeats
        until final text response or max rounds.
        """
        current_messages = list(messages)
        response: dict[str, Any] = {}

        for round_num in range(max_rounds):
            response = self.chat_completion(current_messages, tools=tools, tool_choice="auto")
            tool_calls = response["message"].get("tool_calls")

            if not tool_calls:
                return response

            # Add assistant message with tool calls
            current_messages.append({
                "role": "assistant",
                "content": response["message"]["content"],
                "tool_calls": tool_calls,
            })

            # Execute each tool
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}

                logger.info(f"Tool call [{round_num + 1}]: {func_name}")
                try:
                    result = tool_executor.execute_tool(func_name, func_args)
                    result_str = json.dumps(result) if not isinstance(result, str) else result
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
                    logger.error(f"Tool error: {func_name} -> {e}")

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

        logger.warning(f"Max tool rounds ({max_rounds}) reached.")
        return response

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

    def is_configured(self) -> bool:
        return bool(self._config.get_api_key())

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = self.chat_completion([{"role": "user", "content": "Say OK"}], max_tokens=5, temperature=0)
            return True, f"Connected. Model: {self.model}"
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {e}"
