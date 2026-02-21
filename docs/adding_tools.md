# OP(AI)UM — Adding New AI Tools

## Quick Start

To add a new AI tool, create a file in `src/ai/tools/` inheriting from `BaseTool`:

```python
from src.ai.tools.base_tool import BaseTool, ToolResult

class MyNewTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "What this tool does (sent to GPT for function calling)"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target path"},
            },
            "required": ["path"],
        }

    def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        # ... your logic ...
        return ToolResult(success=True, message="Done", data={})
```

## Making It Destructive

For tools that modify files:

```python
@property
def is_destructive(self) -> bool:
    return True

def preview(self, **kwargs) -> ToolResult:
    # Show what WILL happen without doing it
    return ToolResult(
        success=True,
        requires_approval=True,
        preview=["Will rename 5 files", "  old.txt → new.txt"],
    )
```

## Registration

Add your tool to `src/ai/function_registry.py` in the `_register_default_tools()` method:

```python
from src.ai.tools.my_tool import MyNewTool
self.register(MyNewTool())
```

The tool is automatically converted to OpenAI function calling format.

## ToolResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Did it work? |
| `message` | str | Human-readable result |
| `data` | Any | Structured data payload |
| `operation` | OperationRecord | For undo journal |
| `requires_approval` | bool | Show approval dialog |
| `preview` | list[str] | Preview lines for dialog |

## Best Practices

1. Always validate paths with `self._validate_path()` or `self._validate_directory()`
2. Log execution with `self._log_execution(**kwargs)`
3. Handle `OSError` and `PermissionError` gracefully
4. Create `OperationRecord` for undoable operations
5. Keep `description` clear — GPT uses it for function selection
6. Use `PathUtils.format_size()` for human-readable sizes
