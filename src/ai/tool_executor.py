"""
OP(AI)UM — Tool Executor with Journal Recording

Wraps the FunctionRegistry to record operations to the undo journal
when tools return ToolResult with an operation field.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from src.ai.function_registry import FunctionRegistry
from src.ai.tools.base_tool import ToolResult
from src.core.models import OperationRecord
from src.undo.operation_journal import OperationJournal
from src.undo.operation_models import FileMapping, Operation, OperationType


class ToolExecutorWithJournal:
    """
    Tool executor that records operations to the journal.
    Wraps FunctionRegistry and intercepts results to record file operations.
    """

    def __init__(self, registry: FunctionRegistry, journal: OperationJournal) -> None:
        self._registry = registry
        self._journal = journal

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute tool and record operation to journal if applicable."""
        result = self._registry.execute_tool(name, arguments)

        if isinstance(result, ToolResult) and result.operation is not None:
            self._record_operation(result.operation)

        return result

    def _record_operation(self, record: OperationRecord) -> None:
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

            self._journal.record(operation)
            logger.debug(f"Recorded operation to journal: {record.operation_type}")

        except Exception as e:
            logger.error(f"Failed to record operation to journal: {e}")

    @staticmethod
    def _record_type_to_operation_type(record_type: str) -> OperationType:
        """Map OperationRecord type string to OperationType enum."""
        type_map = {
            "rename": OperationType.RENAME,
            "batch_rename": OperationType.BATCH_RENAME,
            "move": OperationType.MOVE,
            "batch_move": OperationType.BATCH_MOVE,
            "copy": OperationType.COPY,
            "batch_copy": OperationType.BATCH_COPY,
            "delete": OperationType.DELETE,
            "batch_delete": OperationType.BATCH_DELETE,
            "organize": OperationType.ORGANIZE,
            "flatten": OperationType.FLATTEN,
            "create_folder": OperationType.CREATE_FOLDER,
            "extension_change": OperationType.EXTENSION_CHANGE,
            "create_file": OperationType.CREATE_FILE,
            "write_file": OperationType.WRITE_FILE,
            "append_file": OperationType.APPEND_FILE,
        }
        return type_map.get(record_type, OperationType.RENAME)
