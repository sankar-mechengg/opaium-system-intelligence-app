"""Tests for empty_folder_cleaner.py and folder_flattener.py."""

from __future__ import annotations

from pathlib import Path

from src.ai.tools.empty_folder_cleaner import EmptyFolderCleanerTool
from src.ai.tools.folder_flattener import FolderFlattenerTool


class TestEmptyFolderCleanerTool:
    def setup_method(self):
        self.tool = EmptyFolderCleanerTool()

    def test_find_empty_folders(self, nested_dirs: Path):
        result = self.tool.execute(path=str(nested_dirs), dry_run=True)
        assert result.success is True
        assert result.data["count"] == 3  # sub2, sub3/sub3a, sub3 (all empty dirs)

    def test_remove_empty_folders(self, nested_dirs: Path):
        result = self.tool.execute(path=str(nested_dirs), dry_run=False)
        assert result.success is True
        assert not (nested_dirs / "sub2").exists()

    def test_no_empty_folders(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files), dry_run=True)
        assert result.data["count"] == 0

    def test_preview_mode(self, nested_dirs: Path):
        result = self.tool.preview(path=str(nested_dirs))
        assert result.requires_approval is True
        assert result.data["count"] >= 3


class TestFolderFlattenerTool:
    def setup_method(self):
        self.tool = FolderFlattenerTool()

    def test_flatten_nested(self, nested_dirs: Path):
        result = self.tool.execute(path=str(nested_dirs))
        assert result.success is True

        # All files should be at root level now
        root_files = [f.name for f in nested_dirs.iterdir() if f.is_file()]
        assert "file1.txt" in root_files
        assert "file2.txt" in root_files
        assert "file3.txt" in root_files

    def test_flatten_conflict_resolution(self, tmp_path: Path):
        root = tmp_path / "flat_test"
        root.mkdir()
        (root / "file.txt").write_text("root")
        sub = root / "sub"
        sub.mkdir()
        (sub / "file.txt").write_text("sub")

        result = self.tool.execute(path=str(root))
        assert result.success is True

        root_files = [f.name for f in root.iterdir() if f.is_file()]
        assert "file.txt" in root_files
        assert "file (1).txt" in root_files

    def test_preview(self, nested_dirs: Path):
        result = self.tool.preview(path=str(nested_dirs))
        assert result.requires_approval is True
        assert len(result.preview) > 0

    def test_remove_empty_after_flatten(self, nested_dirs: Path):
        self.tool.execute(path=str(nested_dirs), remove_empty=True)
        # Empty dirs should be removed
        subdirs = [d for d in nested_dirs.iterdir() if d.is_dir()]
        # Most subdirs should be gone (empty after flatten)
        assert len(subdirs) <= 1  # May keep dirs that couldn't be removed
