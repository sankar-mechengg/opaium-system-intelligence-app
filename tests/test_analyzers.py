"""Tests for file_age_analyzer.py, large_file_finder.py, and type_summarizer.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ai.tools.file_age_analyzer import FileAgeAnalyzerTool
from src.ai.tools.large_file_finder import LargeFileFinderTool
from src.ai.tools.type_summarizer import TypeSummarizerTool


class TestFileAgeAnalyzerTool:

    def setup_method(self):
        self.tool = FileAgeAnalyzerTool()

    def test_find_old_files(self, old_files: Path):
        result = self.tool.execute(path=str(old_files), older_than_days=30)
        assert result.success is True
        assert result.data["count"] >= 3  # 90d, 365d, 730d files

    def test_no_old_files(self, old_files: Path):
        result = self.tool.execute(path=str(old_files), older_than_days=9999)
        assert result.data["count"] == 0

    def test_all_files_old(self, old_files: Path):
        result = self.tool.execute(path=str(old_files), older_than_days=0)
        assert result.data["count"] == 6  # All files

    def test_sorted_by_age(self, old_files: Path):
        result = self.tool.execute(path=str(old_files), older_than_days=0)
        files = result.data["files"]
        ages = [f["age_days"] for f in files]
        assert ages == sorted(ages, reverse=True)

    def test_format_age(self):
        assert "day" in FileAgeAnalyzerTool._format_age(5)
        assert "month" in FileAgeAnalyzerTool._format_age(60)
        assert "year" in FileAgeAnalyzerTool._format_age(400)


class TestLargeFileFinderTool:

    def setup_method(self):
        self.tool = LargeFileFinderTool()

    def test_find_large_files(self, sample_files: Path):
        # Files in sample range from ~14 bytes to ~4KB
        result = self.tool.execute(path=str(sample_files), min_size_mb=0.001)
        assert result.success is True
        assert result.data["count"] >= 3  # PDF, XLSX, ZIP are >1KB

    def test_no_large_files(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files), min_size_mb=100)
        assert result.data["count"] == 0

    def test_sorted_by_size(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files), min_size_mb=0)
        files = result.data["files"]
        sizes = [f["size_bytes"] for f in files]
        assert sizes == sorted(sizes, reverse=True)

    def test_top_n_limit(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files), min_size_mb=0, top_n=3)
        assert len(result.data["files"]) <= 3


class TestTypeSummarizerTool:

    def setup_method(self):
        self.tool = TypeSummarizerTool()

    def test_summarize_types(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        assert result.success is True
        types = result.data["types"]
        assert len(types) > 0

        ext_names = [t["extension"] for t in types]
        assert "jpg" in ext_names
        assert "txt" in ext_names

    def test_counts_correct(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        total = sum(t["count"] for t in result.data["types"])
        assert total == result.data["total_files"]

    def test_percentages_add_up(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        total_pct = sum(t["percentage"] for t in result.data["types"])
        assert abs(total_pct - 100.0) < 1.0  # Allow rounding error
