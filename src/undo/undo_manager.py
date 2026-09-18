"""
OP(AI)UM — Undo Manager

Orchestrates the reversal of AI-performed file operations.
Each operation type has its own undo logic:
- Rename → restore original name
- Move → move back to source
- Copy → send copied files to the Recycle Bin
- Delete → restore from the Recycle Bin (Shell COM)
- Organize / Flatten → move files back to original locations
- Create folder/file → remove what was created
- Write / Append → restore the content backup taken before the change
- Clean empty folders → recreate the removed folders
"""

from __future__ import annotations

import os
import shutil

from loguru import logger

from src.undo.backup_store import BackupStore
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

    @property
    def journal(self) -> OperationJournal:
        return self._journal

    def close(self) -> None:
        """Close the underlying journal database connection."""
        self._journal.close()

    def get_recent_operations(self, limit: int = 50) -> list[Operation]:
        """Get recent operations from the journal."""
        return self._journal.get_recent(limit=limit)

    def get_operation(self, op_id: int) -> Operation | None:
        return self._journal.get_operation(op_id)

    def can_undo(self) -> bool:
        """Check if there are any undoable operations."""
        return len(self._journal.get_undoable()) > 0

    def get_last_undoable(self) -> Operation | None:
        """Get the most recent undoable operation."""
        undoable = self._journal.get_undoable()
        return undoable[0] if undoable else None

    def undo_last(self) -> tuple[bool, str]:
        """Undo the most recent undoable operation."""
        operation = self.get_last_undoable()
        if operation is None:
            return False, "No operations to undo."
        return self.undo_operation(operation)

    def undo_by_id(self, op_id: int) -> tuple[bool, str]:
        operation = self._journal.get_operation(op_id)
        if operation is None:
            return False, "Operation not found."
        return self.undo_operation(operation)

    def undo_operation(self, operation: Operation) -> tuple[bool, str]:
        """Undo a specific operation. Returns (success, message)."""
        if operation.is_undone:
            return False, "This operation has already been undone."

        if not operation.is_undoable:
            reason = operation.error_message or "not reversible"
            return False, f"This operation cannot be undone: {reason}"

        logger.info(f"Undoing operation #{operation.id}: {operation.type_label}")

        try:
            op_type = operation.operation_type
            handler = {
                OperationType.RENAME: self._undo_rename,
                OperationType.BATCH_RENAME: self._undo_rename,
                OperationType.RENAME_FOLDER: self._undo_rename,
                OperationType.EXTENSION_CHANGE: self._undo_rename,
                OperationType.MOVE: self._undo_move,
                OperationType.BATCH_MOVE: self._undo_move,
                OperationType.MOVE_FOLDER: self._undo_move,
                OperationType.ORGANIZE: self._undo_organize,
                OperationType.FLATTEN: self._undo_flatten,
                OperationType.COPY: self._undo_copy,
                OperationType.BATCH_COPY: self._undo_copy,
                OperationType.COPY_FOLDER: self._undo_copy,
                OperationType.DELETE: self._undo_delete,
                OperationType.BATCH_DELETE: self._undo_delete,
                OperationType.DELETE_FOLDER: self._undo_delete,
                OperationType.CREATE_FOLDER: self._undo_create_folder,
                OperationType.CREATE_FILE: self._undo_create_file,
                OperationType.WRITE_FILE: self._undo_write,
                OperationType.APPEND_FILE: self._undo_write,
                OperationType.CLEAN_EMPTY: self._undo_clean_empty,
            }.get(op_type)

            if handler is None:
                return False, f"Undo not implemented for: {op_type.value}"

            success, message = handler(operation)

            if success and operation.id:
                self._journal.mark_undone(operation.id)

            return success, message

        except Exception as e:
            error_msg = f"Undo failed: {e}"
            logger.error(error_msg)
            if operation.id:
                self._journal.mark_not_undoable(operation.id, str(e))
            return False, error_msg

    # === Handlers ===

    def _undo_rename(self, op: Operation) -> tuple[bool, str]:
        """Undo rename: restore original names."""
        restored = 0
        errors = 0

        for mapping in op.file_mappings:
            current_path = mapping.destination
            original_path = mapping.source

            if not current_path or not os.path.exists(current_path):
                logger.warning(f"Cannot undo rename: {current_path} not found")
                errors += 1
                continue
            if os.path.exists(original_path):
                logger.warning(f"Cannot undo rename: {original_path} already exists")
                errors += 1
                continue

            try:
                os.rename(current_path, original_path)
                restored += 1
                logger.debug(f"Restored: {current_path} -> {original_path}")
            except OSError as e:
                logger.error(f"Failed to restore {current_path}: {e}")
                errors += 1

        return self._summarize(restored, errors, "Restored {n} original name(s)")

    def _undo_organize(self, op: Operation) -> tuple[bool, str]:
        """Undo organize: move files back and drop the category folders it created."""
        return self._undo_move(op, cleanup_destinations=True)

    def _undo_move(self, op: Operation, cleanup_destinations: bool = False) -> tuple[bool, str]:
        """Undo move: move files back to original locations."""
        restored = 0
        errors = 0

        for mapping in op.file_mappings:
            current_path = mapping.destination
            original_path = mapping.source

            if not current_path or not os.path.exists(current_path) or not original_path:
                errors += 1
                continue
            if os.path.exists(original_path):
                logger.warning(f"Cannot move back: {original_path} already exists")
                errors += 1
                continue

            try:
                os.makedirs(os.path.dirname(original_path), exist_ok=True)
                shutil.move(current_path, original_path)
                restored += 1
            except (OSError, shutil.Error) as e:
                logger.error(f"Failed to move back {current_path}: {e}")
                errors += 1

        if cleanup_destinations:
            self._remove_empty_parents(op)
        return self._summarize(restored, errors, "Moved {n} item(s) back to original location(s)")

    def _undo_flatten(self, op: Operation) -> tuple[bool, str]:
        """Undo flatten: recreate folder structure and move files back."""
        return self._undo_move(op)

    def _undo_copy(self, op: Operation) -> tuple[bool, str]:
        """Undo copy: send the copied files to the Recycle Bin."""
        deleted = 0
        errors = 0

        for mapping in op.file_mappings:
            copy_path = mapping.destination
            if not copy_path or not os.path.exists(copy_path):
                continue  # Already gone, not an error
            try:
                from send2trash import send2trash

                send2trash(copy_path)
                deleted += 1
            except Exception as e:
                logger.error(f"Failed to remove copy {copy_path}: {e}")
                errors += 1

        return self._summarize(deleted, errors, "Removed {n} copied item(s)", allow_zero=True)

    def _undo_delete(self, op: Operation) -> tuple[bool, str]:
        """Undo delete: restore from the Recycle Bin via Shell COM."""
        paths = [m.source for m in op.file_mappings if m.source]
        count = len(paths) or op.affected_count
        logger.info(f"Undo delete requested for {count} item(s).")

        from src.core.recycle_bin import RecycleBinManager

        restored, missing = RecycleBinManager.restore(paths)
        if restored == count and count > 0:
            return True, f"Restored {restored} item(s) from the Recycle Bin."
        if restored > 0:
            return True, f"Restored {restored} of {count} item(s). Not found in the Recycle Bin: {len(missing)}."
        return False, (
            f"Could not find the {count} item(s) in the Recycle Bin — they may have been restored or purged already."
        )

    def _undo_create_folder(self, op: Operation) -> tuple[bool, str]:
        """Undo folder creation: remove created folders (empty → rmdir, otherwise → Recycle Bin)."""
        removed = 0
        errors = 0
        for mapping in op.file_mappings:
            folder_path = mapping.destination or mapping.source
            if not folder_path or not os.path.isdir(folder_path):
                continue
            try:
                if not any(os.scandir(folder_path)):
                    os.rmdir(folder_path)
                else:
                    from send2trash import send2trash

                    send2trash(folder_path)
                removed += 1
            except Exception as e:
                logger.error(f"Failed to remove folder: {e}")
                errors += 1

        return self._summarize(removed, errors, "Removed {n} created folder(s)", allow_zero=True)

    def _undo_create_file(self, op: Operation) -> tuple[bool, str]:
        """Undo file creation: send the created file to the Recycle Bin."""
        removed = 0
        errors = 0
        for mapping in op.file_mappings:
            path = mapping.destination or mapping.source
            if not path or not os.path.isfile(path):
                continue
            try:
                from send2trash import send2trash

                send2trash(path)
                removed += 1
            except Exception as e:
                logger.error(f"Failed to remove file: {e}")
                errors += 1
        return self._summarize(removed, errors, "Removed {n} created file(s)", allow_zero=True)

    def _undo_write(self, op: Operation) -> tuple[bool, str]:
        """Undo write/append: restore the pre-change backup (or truncate an append)."""
        backup_path = op.metadata.get("backup_path")
        target = ""
        for mapping in op.file_mappings:
            target = mapping.destination or mapping.source
            if target:
                break
        if not target:
            return False, "Original file path unknown."

        if backup_path and BackupStore.restore(backup_path, target):
            return True, f"Restored previous content of {os.path.basename(target)}."

        prev_size = op.metadata.get("prev_size")
        if op.operation_type == OperationType.APPEND_FILE and isinstance(prev_size, int) and os.path.isfile(target):
            try:
                with open(target, "r+b") as f:
                    f.truncate(prev_size)
                return True, f"Removed appended content from {os.path.basename(target)}."
            except OSError as e:
                return False, f"Could not truncate file: {e}"

        return False, "No content backup is available for this change."

    def _undo_clean_empty(self, op: Operation) -> tuple[bool, str]:
        """Undo empty-folder cleanup: recreate the folders."""
        created = 0
        errors = 0
        for mapping in sorted(op.file_mappings, key=lambda m: len(m.source)):
            path = mapping.source or mapping.destination
            if not path:
                continue
            try:
                os.makedirs(path, exist_ok=True)
                created += 1
            except OSError as e:
                logger.error(f"Failed to recreate {path}: {e}")
                errors += 1
        return self._summarize(created, errors, "Recreated {n} folder(s)")

    # === Helpers ===

    @staticmethod
    def _summarize(ok: int, errors: int, template: str, allow_zero: bool = False) -> tuple[bool, str]:
        base = template.format(n=ok)
        if errors == 0:
            return (ok > 0 or allow_zero), base + "."
        if ok > 0:
            return True, f"{base}, {errors} failed."
        return False, f"Nothing could be restored ({errors} error(s))."

    @staticmethod
    def _remove_empty_parents(op: Operation) -> None:
        """After moving files back, remove now-empty destination folders created by organize."""
        dirs = {os.path.dirname(m.destination) for m in op.file_mappings if m.destination}
        for d in sorted(dirs, key=len, reverse=True):
            try:
                if d and os.path.isdir(d) and not any(os.scandir(d)):
                    os.rmdir(d)
            except OSError:
                continue

    def get_undo_history(self, limit: int = 50) -> list[Operation]:
        """Get recent operations for the history panel."""
        return self._journal.get_recent(limit=limit)
