"""Tests for src/ai/tools/file_counter.py."""

from __future__ import annotations

from pathlib import Path

from src.ai.tools.file_counter import FileCounterTool


class TestFileCounterTool:
    def setup_method(self):
        self.tool = FileCounterTool()

    def test_tool_properties(self):
        assert self.tool.name == "count_files"
        assert self.tool.is_destructive is False
        assert "path" in self.tool.parameters["properties"]

    def test_count_all_files(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        assert result.success is True
        assert result.data["total_files"] == 11  # All sample files
        assert result.data["total_folders"] == 0

    def test_count_by_extension(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files), extension="jpg")
        assert result.success is True
        assert result.data["matched_files"] == 2

    def test_count_recursive(self, nested_dirs: Path):
        result = self.tool.execute(path=str(nested_dirs), recursive=True)
        assert result.success is True
        assert result.data["total_files"] == 3
        assert result.data["total_folders"] >= 3

    def test_count_non_recursive(self, nested_dirs: Path):
        result = self.tool.execute(path=str(nested_dirs), recursive=False)
        assert result.success is True
        assert result.data["total_files"] == 1  # Only file1.txt at root

    def test_invalid_path(self):
        result = self.tool.execute(path="/nonexistent/path")
        assert result.success is False

    def test_type_breakdown(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        breakdown = result.data["type_breakdown"]
        assert "jpg" in breakdown
        assert breakdown["jpg"] == 2

    def test_to_openai_function(self):
        func = self.tool.to_openai_function()
        assert func["type"] == "function"
        assert func["function"]["name"] == "count_files"
        assert "parameters" in func["function"]
