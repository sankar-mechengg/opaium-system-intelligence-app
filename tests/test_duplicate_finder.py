"""Tests for src/ai/tools/duplicate_finder.py."""

from __future__ import annotations

from pathlib import Path

from src.ai.tools.duplicate_finder import DuplicateFinderTool


class TestDuplicateFinderTool:
    def setup_method(self):
        self.tool = DuplicateFinderTool()

    def test_find_duplicates(self, duplicate_files: Path):
        result = self.tool.execute(path=str(duplicate_files))
        assert result.success is True
        groups = result.data["duplicate_groups"]
        assert len(groups) == 2  # Two groups of duplicates
        assert result.data["total_duplicates"] == 3  # 2 extra A + 1 extra B

    def test_no_duplicates(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        assert result.success is True
        # Sample files are all unique
        groups = result.data["duplicate_groups"]
        assert len(groups) == 0

    def test_wasted_space_calculation(self, duplicate_files: Path):
        result = self.tool.execute(path=str(duplicate_files))
        assert result.data["wasted_bytes"] > 0

    def test_filter_by_extension(self, duplicate_files: Path):
        result = self.tool.execute(path=str(duplicate_files), extension="txt")
        groups = result.data["duplicate_groups"]
        assert len(groups) == 1  # Only .txt duplicates

    def test_min_size_filter(self, duplicate_files: Path):
        result = self.tool.execute(path=str(duplicate_files), min_size_kb=0.001)
        assert result.success is True

    def test_invalid_path(self):
        result = self.tool.execute(path="/nonexistent")
        assert result.success is False
