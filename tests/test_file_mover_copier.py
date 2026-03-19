"""Tests for src/ai/tools/file_mover.py and file_copier.py."""

from __future__ import annotations

from pathlib import Path

from src.ai.tools.file_copier import FileCopierTool
from src.ai.tools.file_mover import FileMoverTool


class TestFileMoverTool:
    def setup_method(self):
        self.tool = FileMoverTool()

    def test_move_specific_files(self, sample_files: Path, tmp_path: Path):
        dest = tmp_path / "dest"
        result = self.tool.execute(
            source_directory=str(sample_files),
            destination_directory=str(dest),
            filenames=["readme.txt", "notes.md"],
        )
        assert result.success is True
        assert result.data["succeeded"] == 2
        assert (dest / "readme.txt").exists()
        assert (dest / "notes.md").exists()
        assert not (sample_files / "readme.txt").exists()

    def test_move_by_extension(self, sample_files: Path, tmp_path: Path):
        dest = tmp_path / "images"
        result = self.tool.execute(
            source_directory=str(sample_files),
            destination_directory=str(dest),
            extension="jpg",
        )
        assert result.success is True
        assert result.data["succeeded"] == 2

    def test_move_creates_destination(self, sample_files: Path, tmp_path: Path):
        dest = tmp_path / "new" / "nested" / "dir"
        result = self.tool.execute(
            source_directory=str(sample_files),
            destination_directory=str(dest),
            filenames=["readme.txt"],
            create_dest=True,
        )
        assert result.success is True
        assert dest.exists()

    def test_move_conflict_resolution(self, sample_files: Path, tmp_path: Path):
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "readme.txt").write_text("existing")

        result = self.tool.execute(
            source_directory=str(sample_files),
            destination_directory=str(dest),
            filenames=["readme.txt"],
        )
        assert result.success is True
        # Should create "readme (1).txt"
        assert (dest / "readme (1).txt").exists()

    def test_preview(self, sample_files: Path, tmp_path: Path):
        dest = tmp_path / "dest"
        result = self.tool.preview(
            source_directory=str(sample_files),
            destination_directory=str(dest),
            filenames=["readme.txt"],
        )
        assert result.requires_approval is True


class TestFileCopierTool:
    def setup_method(self):
        self.tool = FileCopierTool()

    def test_copy_keeps_original(self, sample_files: Path, tmp_path: Path):
        dest = tmp_path / "copies"
        result = self.tool.execute(
            source_directory=str(sample_files),
            destination_directory=str(dest),
            filenames=["readme.txt"],
        )
        assert result.success is True
        assert (dest / "readme.txt").exists()
        assert (sample_files / "readme.txt").exists()  # Original still there

    def test_copy_by_extension(self, sample_files: Path, tmp_path: Path):
        dest = tmp_path / "py_files"
        result = self.tool.execute(
            source_directory=str(sample_files),
            destination_directory=str(dest),
            extension="py",
        )
        assert result.success is True
        assert result.data["succeeded"] == 1
