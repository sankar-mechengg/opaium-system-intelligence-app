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

For tools that modify files, return `True` from `is_destructive` **and implement `preview()`**. The executor
(`src/ai/tool_executor.py`) enforces the flow — the model cannot skip it:

1. `PathGuard` refuses protected locations (Windows, Program Files, drive roots, profile root, app data).
2. `preview(**arguments)` is called. If it returns `requires_approval=False` and `success=True` the call is
   treated as read-only (e.g. `file_content.read`) and runs immediately. If it fails, its message is returned
   to the model as an error.
3. Otherwise `preview_lines` are shown in the approval dialog. Only an explicit Approve runs `execute()`.

```python
@property
def is_destructive(self) -> bool:
    return True

def preview(self, **kwargs) -> ToolResult:
    # Show exactly what WILL happen without doing it — one line per affected item.
    return ToolResult(
        success=True,
        message="Will rename 5 files in Photos",   # first line becomes the dialog title
        requires_approval=True,
        preview=["Will rename 5 files:", "  old.txt  →  new.txt"],
    )
```

Path arguments must use one of the keys the guard scans: `directory`, `path`, `source`, `destination`,
`folder`, `target` (see `src/ai/safety.py::PATH_ARG_KEYS`).

## Registration

Add your tool to the `tool_factories` list in `FunctionRegistry.register_all_tools()`
(`src/ai/function_registry.py`). The tool instance is kept so the executor can call `preview()`.

```python
from src.ai.tools.my_tool import MyNewTool
tool_factories = [..., lambda: MyNewTool()]
```

The tool is automatically converted to OpenAI function-calling format. Add a friendly label and icon in
`src/ui/chat/tool_card.py` (`TOOL_LABELS`, `TOOL_ICONS`) so the chat shows it nicely.

## ToolResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Did it work? |
| `message` | str | Human-readable result |
| `data` | Any | Structured data payload |
| `operation` | OperationRecord | For undo journal (set `is_undoable` and an `operation_type` handled by `UndoManager`) |
| `requires_approval` | bool | Show approval dialog |
| `preview` | list[str] | Preview lines for dialog |
| `operation_id` | int | Filled in by the executor after journaling |

## Best Practices

1. Always validate paths with `self._validate_path()` or `self._validate_directory()`
2. Log execution with `self._log_execution(**kwargs)`
3. Handle `OSError` and `PermissionError` gracefully
4. Create `OperationRecord` for undoable operations
5. Keep `description` clear — GPT uses it for function selection
6. Use `PathUtils.format_size()` for human-readable sizes
