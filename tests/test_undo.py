"""Tests for src/undo/ module."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.undo.operation_journal import OperationJournal
from src.undo.operation_models import FileMapping, Operation, OperationType
from src.undo.undo_manager import UndoManager


class TestOperationJournal:
    @pytest.fixture
    def journal(self, tmp_path: Path):
        db_path = tmp_path / "test_undo.db"
        j = OperationJournal(db_path=db_path)
        yield j
        j.close()

    def test_record_operation(self, journal: OperationJournal):
        op = Operation(
            operation_type=OperationType.RENAME,
            description="Renamed 3 files",
            file_mappings=[
                FileMapping(source="/a.txt", destination="/a_new.txt"),
                FileMapping(source="/b.txt", destination="/b_new.txt"),
                FileMapping(source="/c.txt", destination="/c_new.txt"),
            ],
            is_undoable=True,
        )
        op_id = journal.record(op)
        assert op_id > 0

    def test_get_recent(self, journal: OperationJournal):
        for i in range(5):
            op = Operation(
                operation_type=OperationType.RENAME,
                description=f"Operation {i}",
                file_mappings=[FileMapping(source=f"/file{i}.txt", destination=f"/out{i}.txt")],
                is_undoable=True,
            )
            journal.record(op)

        recent = journal.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_operation_by_id(self, journal: OperationJournal):
        op = Operation(
            operation_type=OperationType.MOVE,
            description="Moved files",
            file_mappings=[
                FileMapping(source="/old/f.txt", destination="/new/f.txt"),
            ],
            is_undoable=True,
        )
        op_id = journal.record(op)
        retrieved = journal.get_operation(op_id)
        assert retrieved is not None
        assert retrieved.operation_type == OperationType.MOVE

    def test_mark_undone(self, journal: OperationJournal):
        op = Operation(
            operation_type=OperationType.RENAME,
            description="Test",
            file_mappings=[FileMapping(source="/a.txt", destination="/b.txt")],
            is_undoable=True,
        )
        op_id = journal.record(op)
        journal.mark_undone(op_id)

        retrieved = journal.get_operation(op_id)
        assert retrieved is not None
        assert retrieved.is_undone is True


class TestUndoManager:
    @pytest.fixture
    def manager(self, tmp_path: Path):
        journal = OperationJournal(db_path=tmp_path / "undo.db")
        yield UndoManager(journal)
        journal.close()

    def test_undo_rename(self, tmp_path: Path, manager: UndoManager):
        new_path = tmp_path / "renamed.txt"
        new_path.write_text("content")
        old_path = tmp_path / "original.txt"

        op = Operation(
            operation_type=OperationType.RENAME,
            description="Test rename undo",
            file_mappings=[
                FileMapping(
                    source=str(old_path),
                    destination=str(new_path),
                    original_name="original.txt",
                    new_name="renamed.txt",
                ),
            ],
            is_undoable=True,
        )

        success, _msg = manager.undo_operation(op)
        assert success is True
        assert old_path.exists()
        assert not new_path.exists()

    def test_undo_move(self, tmp_path: Path, manager: UndoManager):
        src_dir = tmp_path / "src"
        dest_dir = tmp_path / "dest"
        src_dir.mkdir()
        dest_dir.mkdir()

        dest_file = dest_dir / "file.txt"
        dest_file.write_text("moved content")
        src_file = src_dir / "file.txt"

        op = Operation(
            operation_type=OperationType.MOVE,
            description="Test move undo",
            file_mappings=[
                FileMapping(source=str(src_file), destination=str(dest_file)),
            ],
            is_undoable=True,
        )

        success, _msg = manager.undo_operation(op)
        assert success is True
        assert src_file.exists()

    def test_undo_copy(self, tmp_path: Path, manager: UndoManager):
        copy_file = tmp_path / "copy.txt"
        copy_file.write_text("copied")

        op = Operation(
            operation_type=OperationType.COPY,
            description="Test copy undo",
            file_mappings=[
                FileMapping(source=str(tmp_path / "original.txt"), destination=str(copy_file)),
            ],
            is_undoable=True,
            metadata={"undo_action": "delete_copies"},
        )

        success, _msg = manager.undo_operation(op)
        assert success is True
        assert not copy_file.exists()

    def test_undo_non_undoable(self, manager: UndoManager):
        op = Operation(
            operation_type=OperationType.DELETE,
            description="Not undoable",
            file_mappings=[FileMapping(source="/deleted.txt", destination="")],
            is_undoable=False,
        )
        success, _msg = manager.undo_operation(op)
        assert success is False
