"""Tests for src/ai/tools/file_renamer.py."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.ai.tools.file_renamer import FileRenamerTool


class TestFileRenamerTool:

    def setup_method(self):
        self.tool = FileRenamerTool()

    def test_tool_is_destructive(self):
        assert self.tool.is_destructive is True

    def test_rename_single_file(self, sample_files: Path):
        result = self.tool.execute(
            directory=str(sample_files),
            renames=[{"old_name": "readme.txt", "new_name": "README.txt"}],
        )
        assert result.success is True
        assert result.data["succeeded"] == 1
        assert (sample_files / "README.txt").exists()
        assert not (sample_files / "readme.txt").exists()

    def test_rename_multiple_files(self, sample_files: Path):
        result = self.tool.execute(
            directory=str(sample_files),
            renames=[
                {"old_name": "readme.txt", "new_name": "info.txt"},
                {"old_name": "notes.md", "new_name": "notes_v2.md"},
            ],
        )
        assert result.success is True
        assert result.data["succeeded"] == 2

    def test_rename_nonexistent_file(self, sample_files: Path):
        result = self.tool.execute(
            directory=str(sample_files),
            renames=[{"old_name": "nonexistent.txt", "new_name": "new.txt"}],
        )
        assert result.data["succeeded"] == 0
        assert result.data["failed"] == 1

    def test_rename_conflict(self, sample_files: Path):
        result = self.tool.execute(
            directory=str(sample_files),
            renames=[{"old_name": "readme.txt", "new_name": "notes.md"}],
        )
        assert result.data["failed"] == 1  # notes.md already exists

    def test_preview(self, sample_files: Path):
        result = self.tool.preview(
            directory=str(sample_files),
            renames=[{"old_name": "readme.txt", "new_name": "README.txt"}],
        )
        assert result.requires_approval is True
        assert len(result.preview) > 0

    def test_operation_record(self, sample_files: Path):
        result = self.tool.execute(
            directory=str(sample_files),
            renames=[{"old_name": "readme.txt", "new_name": "renamed.txt"}],
        )
        assert result.operation is not None
        assert result.operation.operation_type == "rename"
        assert result.operation.is_undoable is True
