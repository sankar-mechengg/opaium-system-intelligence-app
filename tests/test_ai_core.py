"""Tests for base_tool.py, function_registry.py, and conversation_manager.py."""

from __future__ import annotations

from typing import Any

from src.ai.conversation_manager import ConversationManager
from src.ai.function_registry import FunctionRegistry
from src.ai.tools.base_tool import BaseTool, ToolResult


class MockTool(BaseTool):
    """Test tool for unit tests."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text", "")
        return ToolResult(success=True, message=f"Mock: {text}", data={"echo": text})


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, message="OK")
        assert r.success is True
        assert "OK" in repr(r)

    def test_failure_result(self):
        r = ToolResult(success=False, message="Error")
        assert r.success is False
        assert "FAIL" in repr(r)

    def test_result_with_data(self):
        r = ToolResult(success=True, data={"count": 42})
        assert r.data["count"] == 42

    def test_result_with_preview(self):
        r = ToolResult(
            success=True,
            requires_approval=True,
            preview=["Line 1", "Line 2"],
        )
        assert r.requires_approval is True
        assert len(r.preview) == 2


class TestBaseTool:
    def test_mock_tool_properties(self):
        tool = MockTool()
        assert tool.name == "mock_tool"
        assert tool.is_destructive is False

    def test_mock_tool_execute(self):
        tool = MockTool()
        result = tool.execute(text="hello")
        assert result.success is True
        assert result.data["echo"] == "hello"

    def test_to_openai_function(self):
        tool = MockTool()
        func = tool.to_openai_function()
        assert func["type"] == "function"
        assert func["function"]["name"] == "mock_tool"
        assert "text" in func["function"]["parameters"]["properties"]

    def test_validate_path(self, tmp_path):
        tool = MockTool()
        assert tool._validate_path(str(tmp_path)) is True
        assert tool._validate_path("/nonexistent/path") is False

    def test_validate_directory(self, tmp_path):
        tool = MockTool()
        assert tool._validate_directory(str(tmp_path)) is True
        f = tmp_path / "file.txt"
        f.write_text("test")
        assert tool._validate_directory(str(f)) is False


class TestFunctionRegistry:
    def _register_mock(self, registry: FunctionRegistry) -> None:
        tool = MockTool()
        registry.register(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            handler=tool.execute,
        )

    def test_register_and_get(self):
        registry = FunctionRegistry()
        self._register_mock(registry)
        td = registry.get_tool("mock_tool")
        assert td is not None
        assert td.name == "mock_tool"

    def test_get_nonexistent(self):
        registry = FunctionRegistry()
        assert registry.get_tool("nonexistent") is None

    def test_get_all_schemas(self):
        registry = FunctionRegistry()
        self._register_mock(registry)
        schemas = registry.get_all_schemas()
        assert len(schemas) >= 1

    def test_get_openai_functions_shape(self):
        registry = FunctionRegistry()
        self._register_mock(registry)
        schemas = registry.get_all_schemas()
        assert schemas[0]["type"] == "function"

    def test_duplicate_registration(self):
        registry = FunctionRegistry()
        self._register_mock(registry)
        self._register_mock(registry)
        assert registry.tool_count == 1


class TestConversationManager:
    def test_add_and_get_messages(self):
        conv = ConversationManager()
        conv.set_system_prompt("You are a test assistant.")
        conv.add_user_message("Hello")
        conv.add_assistant_message("Hi there!")

        messages = conv.get_api_messages()
        assert len(messages) >= 3

    def test_system_message_exists(self):
        conv = ConversationManager()
        conv.set_system_prompt("System here.")
        messages = conv.get_api_messages()
        assert any(m["role"] == "system" for m in messages)

    def test_clear(self):
        conv = ConversationManager()
        conv.set_system_prompt("sys")
        conv.add_user_message("test")
        conv.clear()
        messages = conv.get_api_messages()
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

    def test_message_order(self):
        conv = ConversationManager()
        conv.set_system_prompt("s")
        conv.add_user_message("Q1")
        conv.add_assistant_message("A1")
        conv.add_user_message("Q2")

        messages = conv.get_api_messages()
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant", "user"]

    def test_token_estimation(self):
        conv = ConversationManager()
        for i in range(50):
            conv.add_user_message(f"Message {i} " * 50)
        messages = conv.get_api_messages()
        assert len(messages) < 55
