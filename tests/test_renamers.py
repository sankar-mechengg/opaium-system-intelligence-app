"""Tests for regex_renamer.py and extension_changer.py."""

from __future__ import annotations

from pathlib import Path

from src.ai.tools.extension_changer import ExtensionChangerTool
from src.ai.tools.regex_renamer import RegexRenamerTool


class TestRegexRenamerTool:
    def setup_method(self):
        self.tool = RegexRenamerTool()

    def test_simple_regex_rename(self, sample_files: Path):
        # Add prefix to .txt files
        result = self.tool.execute(
            directory=str(sample_files),
            pattern=r"^(.+)\.txt$",
            replacement=r"prefixed_\1.txt",
            extension="txt",
        )
        assert result.success is True
        assert (sample_files / "prefixed_readme.txt").exists()

    def test_remove_pattern(self, tmp_path: Path):
        d = tmp_path / "regex_test"
        d.mkdir()
        (d / "photo_001.jpg").write_bytes(b"img")
        (d / "photo_002.jpg").write_bytes(b"img")
        (d / "photo_003.jpg").write_bytes(b"img")

        result = self.tool.execute(
            directory=str(d),
            pattern=r"photo_(\d+)",
            replacement=r"img_\1",
        )
        assert result.success is True
        assert result.data["succeeded"] == 3
        assert (d / "img_001.jpg").exists()

    def test_invalid_regex(self, sample_files: Path):
        result = self.tool.execute(
            directory=str(sample_files),
            pattern=r"[invalid",
            replacement="new",
        )
        assert result.success is False
        assert "Invalid regex" in result.message

    def test_no_matches(self, sample_files: Path):
        result = self.tool.execute(
            directory=str(sample_files),
            pattern=r"^ZZZZZ",
            replacement="new",
        )
        assert result.success is False

    def test_preview(self, sample_files: Path):
        result = self.tool.preview(
            directory=str(sample_files),
            pattern=r"^(.+)\.txt$",
            replacement=r"renamed_\1.txt",
        )
        assert result.requires_approval is True


class TestExtensionChangerTool:
    def setup_method(self):
        self.tool = ExtensionChangerTool()

    def test_change_extension(self, tmp_path: Path):
        d = tmp_path / "ext_test"
        d.mkdir()
        (d / "file1.jpeg").write_bytes(b"img")
        (d / "file2.jpeg").write_bytes(b"img")
        (d / "file3.png").write_bytes(b"img")

        result = self.tool.execute(directory=str(d), from_ext="jpeg", to_ext="jpg")
        assert result.success is True
        assert result.operation is not None
        assert len(result.operation.source_paths) == 2
        assert (d / "file1.jpg").exists()
        assert (d / "file2.jpg").exists()
        assert (d / "file3.png").exists()  # Unchanged

    def test_preview(self, tmp_path: Path):
        d = tmp_path / "ext_preview"
        d.mkdir()
        (d / "a.htm").write_text("<html>")
        (d / "b.htm").write_text("<html>")

        result = self.tool.preview(directory=str(d), from_ext="htm", to_ext="html")
        assert result.requires_approval is True
        assert "2" in result.message

    def test_no_matching_files(self, sample_files: Path):
        result = self.tool.execute(
            directory=str(sample_files),
            from_ext="zzz",
            to_ext="abc",
        )
        assert result.success is False

    def test_operation_undoable(self, tmp_path: Path):
        d = tmp_path / "ext_undo"
        d.mkdir()
        (d / "file.jpeg").write_bytes(b"x")

        result = self.tool.execute(directory=str(d), from_ext="jpeg", to_ext="jpg")
        assert result.operation is not None
        assert result.operation.is_undoable is True
