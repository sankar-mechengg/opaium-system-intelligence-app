"""Tests for src/undo/ module."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from src.core.models import OperationRecord
from src.undo.undo_journal import UndoJournal
from src.undo.undo_executor import UndoExecutor


class TestUndoJournal:

    @pytest.fixture
    def journal(self, tmp_path: Path):
        db_path = tmp_path / "test_undo.db"
        return UndoJournal(db_path=db_path)

    def test_record_operation(self, journal: UndoJournal):
        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="rename",
            description="Renamed 3 files",
            source_paths=["/a.txt", "/b.txt", "/c.txt"],
            dest_paths=["/a_new.txt", "/b_new.txt", "/c_new.txt"],
            is_undoable=True,
        )
        op_id = journal.record(op)
        assert op_id > 0

    def test_get_recent(self, journal: UndoJournal):
        for i in range(5):
            op = OperationRecord(
                timestamp=datetime.now(),
                operation_type="rename",
                description=f"Operation {i}",
                source_paths=[f"/file{i}.txt"],
                is_undoable=True,
            )
            journal.record(op)

        recent = journal.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_operation_by_id(self, journal: UndoJournal):
        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="move",
            description="Moved files",
            source_paths=["/old/f.txt"],
            dest_paths=["/new/f.txt"],
            is_undoable=True,
        )
        op_id = journal.record(op)
        retrieved = journal.get(op_id)
        assert retrieved is not None
        assert retrieved.operation_type == "move"

    def test_mark_undone(self, journal: UndoJournal):
        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="rename",
            description="Test",
            source_paths=["/a.txt"],
            is_undoable=True,
        )
        op_id = journal.record(op)
        journal.mark_undone(op_id)

        retrieved = journal.get(op_id)
        assert retrieved is not None
        assert retrieved.is_undone is True


class TestUndoExecutor:

    def test_undo_rename(self, tmp_path: Path):
        # Setup: create renamed files
        new_path = tmp_path / "renamed.txt"
        new_path.write_text("content")
        old_path = tmp_path / "original.txt"

        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="rename",
            description="Test rename undo",
            source_paths=[str(old_path)],
            dest_paths=[str(new_path)],
            original_names=["original.txt"],
            new_names=["renamed.txt"],
            is_undoable=True,
        )

        success = UndoExecutor.execute_undo(op)
        assert success is True
        assert old_path.exists()
        assert not new_path.exists()

    def test_undo_move(self, tmp_path: Path):
        # Setup: file was moved from src to dest
        src_dir = tmp_path / "src"
        dest_dir = tmp_path / "dest"
        src_dir.mkdir()
        dest_dir.mkdir()

        dest_file = dest_dir / "file.txt"
        dest_file.write_text("moved content")
        src_file = src_dir / "file.txt"

        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="move",
            description="Test move undo",
            source_paths=[str(src_file)],
            dest_paths=[str(dest_file)],
            is_undoable=True,
        )

        success = UndoExecutor.execute_undo(op)
        assert success is True
        assert src_file.exists()

    def test_undo_copy(self, tmp_path: Path):
        # Undo copy = delete the copies
        copy_file = tmp_path / "copy.txt"
        copy_file.write_text("copied")

        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="copy",
            description="Test copy undo",
            source_paths=[str(tmp_path / "original.txt")],
            dest_paths=[str(copy_file)],
            is_undoable=True,
            metadata={"undo_action": "delete_copies"},
        )

        success = UndoExecutor.execute_undo(op)
        assert success is True
        assert not copy_file.exists()

    def test_undo_non_undoable(self):
        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="delete",
            description="Not undoable",
            source_paths=["/deleted.txt"],
            is_undoable=False,
        )
        success = UndoExecutor.execute_undo(op)
        assert success is False
