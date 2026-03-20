"""
OP(AI)UM — Undo Manager

Orchestrates the reversal of AI-performed file operations.
Each operation type has its own undo logic:
- Rename → restore original name
- Move → move back to source
- Copy → delete copied files
- Delete → restore from Recycle Bin
- Organize → move files back to original locations
"""

from __future__ import annotations

import os
import shutil

from loguru import logger

from src.undo.operation_journal import OperationJournal
from src.undo.operation_models import Operation, OperationType


class UndoManager:
    """
    Manages undoing AI-performed file operations.

    Works with the OperationJournal to:
    1. Find the most recent undoable operation
    2. Execute the reverse operation
    3. Mark the operation as undone in the journal
    """

    def __init__(self, journal: OperationJournal) -> None:
        self._journal = journal

    def close(self) -> None:
        """Close the underlying journal database connection."""
        self._journal.close()

    def get_recent_operations(self, limit: int = 50) -> list[Operation]:
        """
        Get recent operations from the journal.

        Args:
            limit: Maximum number of operations to return.

        Returns:
            List of recent operations.
        """
        return self._journal.get_recent(limit=limit)

    def can_undo(self) -> bool:
        """Check if there are any undoable operations."""
        undoable = self._journal.get_undoable()
        return len(undoable) > 0

    def get_last_undoable(self) -> Operation | None:
        """Get the most recent undoable operation."""
        undoable = self._journal.get_undoable()
        return undoable[0] if undoable else None

    def undo_last(self) -> tuple[bool, str]:
        """
        Undo the most recent undoable operation.

        Returns:
            Tuple of (success, message).
        """
        operation = self.get_last_undoable()
        if operation is None:
            return False, "No operations to undo."
        return self.undo_operation(operation)

    def undo_operation(self, operation: Operation) -> tuple[bool, str]:
        """
        Undo a specific operation.

        Args:
            operation: The operation to undo.

        Returns:
            Tuple of (success, message).
        """
        if operation.is_undone:
            return False, "This operation has already been undone."

        if not operation.is_undoable:
            return False, f"This operation cannot be undone: {operation.error_message}"

        logger.info(f"Undoing operation #{operation.id}: {operation.type_label}")

        try:
            op_type = operation.operation_type
            success = False
            message = ""

            if op_type in (OperationType.RENAME, OperationType.BATCH_RENAME):
                success, message = self._undo_rename(operation)
            elif op_type in (OperationType.MOVE, OperationType.BATCH_MOVE):
                success, message = self._undo_move(operation)
            elif op_type in (OperationType.COPY, OperationType.BATCH_COPY):
                success, message = self._undo_copy(operation)
            elif op_type in (OperationType.DELETE, OperationType.BATCH_DELETE):
                success, message = self._undo_delete(operation)
            elif op_type == OperationType.ORGANIZE:
                success, message = self._undo_organize(operation)
            elif op_type == OperationType.FLATTEN:
                success, message = self._undo_flatten(operation)
            elif op_type == OperationType.CREATE_FOLDER:
                success, message = self._undo_create_folder(operation)
            elif op_type == OperationType.EXTENSION_CHANGE:
                success, message = self._undo_extension_change(operation)
            elif op_type == OperationType.CREATE_FILE:
                success, message = self._undo_create_file(operation)
            elif op_type in (OperationType.WRITE_FILE, OperationType.APPEND_FILE):
                return False, "Undo not supported for write/append (content not stored)."
            else:
                return False, f"Undo not implemented for: {op_type.value}"

            if success and operation.id:
                self._journal.mark_undone(operation.id)

            return success, message

        except Exception as e:
            error_msg = f"Undo failed: {e}"
            logger.error(error_msg)
            if operation.id:
                self._journal.mark_not_undoable(operation.id, str(e))
            return False, error_msg

    def _undo_rename(self, op: Operation) -> tuple[bool, str]:
        """Undo rename: restore original names."""
        restored = 0
        errors = 0

        for mapping in op.file_mappings:
            current_path = mapping.destination
            original_path = mapping.source

            if not os.path.exists(current_path):
                logger.warning(f"Cannot undo rename: {current_path} not found")
                errors += 1
                continue

            try:
                os.rename(current_path, original_path)
                restored += 1
                logger.debug(f"Restored: {current_path} -> {original_path}")
            except OSError as e:
                logger.error(f"Failed to restore {current_path}: {e}")
                errors += 1

        if errors == 0:
            return True, f"Restored {restored} original name(s)."
        elif restored > 0:
            return True, f"Restored {restored} name(s), {errors} failed."
        else:
            return False, f"Failed to restore any names ({errors} errors)."

    def _undo_move(self, op: Operation) -> tuple[bool, str]:
        """Undo move: move files back to original locations."""
        restored = 0
        errors = 0

        for mapping in op.file_mappings:
            current_path = mapping.destination
            original_path = mapping.source

            if not os.path.exists(current_path):
                errors += 1
                continue

            try:
                # Ensure parent directory exists
                os.makedirs(os.path.dirname(original_path), exist_ok=True)
                shutil.move(current_path, original_path)
                restored += 1
            except (OSError, shutil.Error) as e:
                logger.error(f"Failed to move back {current_path}: {e}")
                errors += 1

        if errors == 0:
            return True, f"Moved {restored} item(s) back to original location(s)."
        elif restored > 0:
            return True, f"Moved {restored} item(s) back, {errors} failed."
        else:
            return False, f"Failed to restore any items ({errors} errors)."

    def _undo_copy(self, op: Operation) -> tuple[bool, str]:
        """Undo copy: delete the copied files."""
        deleted = 0
        errors = 0

        for mapping in op.file_mappings:
            copy_path = mapping.destination

            if not os.path.exists(copy_path):
                continue  # Already gone, not an error

            try:
                from send2trash import send2trash

                send2trash(copy_path)
                deleted += 1
            except Exception:
                # Fallback to direct delete
                try:
                    if os.path.isdir(copy_path):
                        shutil.rmtree(copy_path)
                    else:
                        os.remove(copy_path)
                    deleted += 1
                except OSError as e:
                    logger.error(f"Failed to delete copy {copy_path}: {e}")
                    errors += 1

        return True, f"Removed {deleted} copied item(s)."

    def _undo_delete(self, op: Operation) -> tuple[bool, str]:
        """
        Undo delete: attempt to restore from Recycle Bin.

        Note: Programmatic restore from Recycle Bin is limited on Windows.
        We use send2trash for deletion, so items should be in the bin.
        """
        # Restoring from Recycle Bin programmatically is complex
        # and requires COM Shell automation. For now, we guide the user.
        count = op.affected_count
        paths = [m.source for m in op.file_mappings]

        logger.info(f"Undo delete requested for {count} items.")

        # Try COM-based restore
        try:
            restored = self._restore_from_recycle_bin(paths)
            if restored > 0:
                return True, f"Restored {restored} of {count} item(s) from Recycle Bin."
        except Exception as e:
            logger.debug(f"COM restore failed: {e}")

        return False, (
            f"Could not automatically restore {count} item(s). Please check the Recycle Bin manually to restore them."
        )

    def _restore_from_recycle_bin(self, original_paths: list[str]) -> int:
        """Attempt to restore files from Recycle Bin via COM."""
        restored = 0
        try:
            import pythoncom
            from win32com.shell import shell, shellcon

            pythoncom.CoInitialize()
            try:
                desktop = shell.SHGetDesktopFolder()
                pidl = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_BITBUCKET)
                recycle_bin = desktop.BindToObject(pidl, None, shell.IID_IShellFolder)

                # Enumerate and find matching items
                enum = recycle_bin.EnumObjects(0, shellcon.SHCONTF_FOLDERS | shellcon.SHCONTF_NONFOLDERS)
                if enum is None:
                    return 0

                # Note: Full implementation would match by original path
                # and invoke the "restore" verb. This is a simplified version.
                logger.debug("Recycle Bin restore via COM is partially implemented.")

            finally:
                pythoncom.CoUninitialize()

        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Recycle Bin restore error: {e}")

        return restored

    def _undo_organize(self, op: Operation) -> tuple[bool, str]:
        """Undo smart organize: move files back to original locations."""
        return self._undo_move(op)

    def _undo_flatten(self, op: Operation) -> tuple[bool, str]:
        """Undo flatten: recreate folder structure and move files back."""
        restored = 0
        errors = 0

        for mapping in op.file_mappings:
            current_path = mapping.destination
            original_path = mapping.source

            if not os.path.exists(current_path):
                errors += 1
                continue

            try:
                os.makedirs(os.path.dirname(original_path), exist_ok=True)
                shutil.move(current_path, original_path)
                restored += 1
            except (OSError, shutil.Error) as e:
                logger.error(f"Failed to restore structure: {e}")
                errors += 1

        if restored > 0:
            return True, f"Restored folder structure for {restored} item(s)."
        return False, f"Failed to restore folder structure ({errors} errors)."

    def _undo_create_folder(self, op: Operation) -> tuple[bool, str]:
        """Undo folder creation: remove created folders (if empty)."""
        removed = 0
        for mapping in op.file_mappings:
            folder_path = mapping.destination or mapping.source
            if os.path.isdir(folder_path):
                try:
                    entries = list(os.scandir(folder_path))
                    if not entries:
                        os.rmdir(folder_path)
                        removed += 1
                    else:
                        logger.warning(f"Cannot remove non-empty folder: {folder_path}")
                except OSError as e:
                    logger.error(f"Failed to remove folder: {e}")

        return removed > 0, f"Removed {removed} created folder(s)."

    def _undo_extension_change(self, op: Operation) -> tuple[bool, str]:
        """Undo extension change: restore original extensions."""
        return self._undo_rename(op)

    def _undo_create_file(self, op: Operation) -> tuple[bool, str]:
        """Undo file creation: delete the created file."""
        removed = 0
        for mapping in op.file_mappings:
            path = mapping.destination or mapping.source
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    removed += 1
                except OSError as e:
                    logger.error(f"Failed to remove file: {e}")
        return removed > 0, f"Removed {removed} created file(s)."

    def get_undo_history(self, limit: int = 50) -> list[Operation]:
        """Get recent operations for the history panel."""
        return self._journal.get_recent(limit=limit)
