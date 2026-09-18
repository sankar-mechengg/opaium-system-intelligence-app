"""
OP(AI)UM — Tool Executor with Safety Gate and Journal Recording

Wraps the FunctionRegistry and, for every tool call:
1. Refuses destructive operations aimed at protected system paths.
2. For destructive tools, builds the tool's real preview and blocks until the
   user approves it in the UI (unless approvals are disabled or the tool was
   trusted for the session).
3. Executes the tool.
4. Records the resulting operation in the undo journal and attaches the
   journal id to the result so the chat can offer a one-click Undo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from src.ai.function_registry import FunctionRegistry
from src.ai.safety import ApprovalBroker, ApprovalRequest, PathGuard
from src.ai.tools.base_tool import ToolResult
from src.core.models import OperationRecord
from src.undo.operation_journal import OperationJournal
from src.undo.operation_models import FileMapping, Operation, OperationType


class ToolExecutorWithJournal:
    """
    Tool executor that gates destructive calls and records operations.
    """

    def __init__(
        self,
        registry: FunctionRegistry,
        journal: OperationJournal,
        approval_broker: ApprovalBroker | None = None,
        confirm_destructive: bool = True,
    ) -> None:
        self._registry = registry
        self._journal = journal
        self._broker = approval_broker
        self._confirm_destructive = confirm_destructive
        self.last_operation_id: int | None = None

    # === Public API ===

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute tool with safety checks and record operation to journal if applicable."""
        tool_def = self._registry.get_tool(name)
        if tool_def is None:
            raise ValueError(f"Unknown tool: {name}")

        if tool_def.is_destructive:
            blocked = PathGuard.find_protected(arguments)
            if blocked:
                msg = (
                    "Refused: this operation targets a protected system location "
                    f"({', '.join(blocked)}). OP(AI)UM never modifies Windows, Program Files, "
                    "drive roots, the user profile root or its own data folder."
                )
                logger.warning(f"PathGuard blocked {name}: {blocked}")
                return ToolResult(success=False, message=msg, data={"blocked_paths": blocked})

            if self._needs_approval(name):
                verdict, reason = self._request_approval(name, arguments)
                if verdict == "preview_failed":
                    return ToolResult(success=False, message=reason)
                if verdict != "approved":
                    logger.info(f"User rejected {name}: {reason}")
                    return ToolResult(
                        success=False,
                        message=f"Cancelled by user. {reason}".strip(),
                        data={"cancelled": True},
                    )

        result = self._registry.execute_tool(name, arguments)

        if isinstance(result, ToolResult) and result.operation is not None:
            op_id = self._record_operation(result.operation)
            result.operation_id = op_id
            self.last_operation_id = op_id

        return result

    # === Approval ===

    def _needs_approval(self, name: str) -> bool:
        if not self._confirm_destructive:
            return False
        if self._broker is None:
            return True  # fail closed: no broker means we cannot ask, so refuse below
        return not self._broker.is_trusted(name)

    def _request_approval(self, name: str, arguments: dict[str, Any]) -> tuple[str, str]:
        """Returns (verdict, reason) where verdict is approved | rejected | preview_failed."""
        if self._broker is None or not self._broker.has_handler:
            return "rejected", "No approval channel is available."

        # Read-only sub-operations of destructive tools never need approval
        # (e.g. file_content.read); a failed preview is reported as a tool error.
        preview = self._build_preview(name, arguments)
        if preview is not None and not preview.requires_approval:
            if preview.success:
                return "approved", ""
            return "preview_failed", preview.message

        lines = list(preview.preview) if preview and preview.preview else []
        title = preview.message.split("\n", 1)[0] if preview and preview.message else f"Run {name}?"
        if not lines:
            lines = [f"{k}: {v}" for k, v in arguments.items()]

        req = ApprovalRequest(
            tool_name=name,
            arguments=arguments,
            title=title,
            preview_lines=lines,
            affected_count=self._estimate_count(lines),
        )
        approved = self._broker.request(req)
        if approved:
            return "approved", ""
        return "rejected", "The user did not approve the previewed changes."

    def _build_preview(self, name: str, arguments: dict[str, Any]) -> ToolResult | None:
        tool_def = self._registry.get_tool(name)
        if tool_def is None or tool_def.instance is None:
            return None
        try:
            return tool_def.instance.preview(**arguments)
        except TypeError as e:
            logger.debug(f"Preview signature mismatch for {name}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Preview failed for {name}: {e}")
            return None

    @staticmethod
    def _estimate_count(lines: list[str]) -> int:
        return sum(1 for ln in lines if ln.startswith("  ") and "..." not in ln)

    # === Journal ===

    def _record_operation(self, record: OperationRecord) -> int | None:
        """Convert OperationRecord to Operation and record in journal."""
        try:
            op_type = self._record_type_to_operation_type(record.operation_type)
            mappings = []

            for i in range(max(len(record.source_paths), len(record.dest_paths))):
                source = record.source_paths[i] if i < len(record.source_paths) else ""
                dest = record.dest_paths[i] if i < len(record.dest_paths) else ""
                orig = record.original_names[i] if i < len(record.original_names) else ""
                new_name = record.new_names[i] if i < len(record.new_names) else ""

                if not dest and source:
                    dest = source
                if not orig and source:
                    orig = Path(source).name
                if not new_name and dest:
                    new_name = Path(dest).name

                mappings.append(
                    FileMapping(
                        source=source,
                        destination=dest,
                        original_name=orig,
                        new_name=new_name,
                    )
                )

            if not mappings and record.dest_paths:
                for path in record.dest_paths:
                    mappings.append(
                        FileMapping(
                            source="",
                            destination=path,
                            original_name="",
                            new_name=Path(path).name,
                        )
                    )

            operation = Operation(
                timestamp=record.timestamp,
                operation_type=op_type,
                description=record.description,
                file_mappings=mappings,
                affected_count=len(mappings) or 1,
                is_undone=False,
                is_undoable=record.is_undoable,
                metadata=record.metadata or {},
            )

            op_id = self._journal.record(operation)
            logger.debug(f"Recorded operation #{op_id} to journal: {record.operation_type}")
            return op_id

        except Exception as e:
            logger.error(f"Failed to record operation to journal: {e}")
            return None

    @staticmethod
    def _record_type_to_operation_type(record_type: str) -> OperationType:
        """Map OperationRecord type string to OperationType enum."""
        type_map = {
            "rename": OperationType.RENAME,
            "batch_rename": OperationType.BATCH_RENAME,
            "regex_rename": OperationType.BATCH_RENAME,
            "rename_folder": OperationType.RENAME_FOLDER,
            "move": OperationType.MOVE,
            "batch_move": OperationType.BATCH_MOVE,
            "move_folder": OperationType.MOVE_FOLDER,
            "copy": OperationType.COPY,
            "batch_copy": OperationType.BATCH_COPY,
            "copy_folder": OperationType.COPY_FOLDER,
            "delete": OperationType.DELETE,
            "batch_delete": OperationType.BATCH_DELETE,
            "delete_folder": OperationType.DELETE_FOLDER,
            "organize": OperationType.ORGANIZE,
            "organize_date": OperationType.ORGANIZE,
            "flatten": OperationType.FLATTEN,
            "clean_empty": OperationType.CLEAN_EMPTY,
            "create_folder": OperationType.CREATE_FOLDER,
            "extension_change": OperationType.EXTENSION_CHANGE,
            "create_file": OperationType.CREATE_FILE,
            "write_file": OperationType.WRITE_FILE,
            "append_file": OperationType.APPEND_FILE,
            "empty_recycle_bin": OperationType.EMPTY_RECYCLE_BIN,
        }
        try:
            return type_map.get(record_type) or OperationType(record_type)
        except ValueError:
            logger.warning(f"Unknown operation record type '{record_type}', recording as generic.")
            return OperationType.OTHER
