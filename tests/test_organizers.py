"""Tests for src/ai/tools/smart_organizer.py and date_organizer.py."""

from __future__ import annotations

from pathlib import Path

from src.ai.tools.date_organizer import DateOrganizerTool
from src.ai.tools.smart_organizer import SmartOrganizerTool


class TestSmartOrganizerTool:
    def setup_method(self):
        self.tool = SmartOrganizerTool()

    def test_organize_by_type(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        assert result.success is True

        # Check folders were created
        assert (sample_files / "Images").is_dir()
        assert (sample_files / "Documents").is_dir()
        assert (sample_files / "Code").is_dir()

    def test_organize_moves_files(self, sample_files: Path):
        self.tool.execute(path=str(sample_files))
        # JPGs should be in Images/
        assert (sample_files / "Images" / "photo1.jpg").exists()
        assert (sample_files / "Images" / "photo2.jpg").exists()
        # PDFs in Documents/
        assert (sample_files / "Documents" / "report.pdf").exists()

    def test_preview_shows_plan(self, sample_files: Path):
        result = self.tool.preview(path=str(sample_files))
        assert result.requires_approval is True
        assert len(result.preview) > 0
        # Should mention folder names
        preview_text = "\n".join(result.preview)
        assert "Images" in preview_text or "Documents" in preview_text

    def test_operation_is_undoable(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        assert result.operation is not None
        assert result.operation.is_undoable is True
        assert result.operation.operation_type == "organize"

    def test_empty_directory(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = self.tool.preview(path=str(empty))
        assert result.success is False

    def test_custom_mapping(self, sample_files: Path):
        custom = {"txt": "TextFiles", "md": "TextFiles"}
        result = self.tool.execute(path=str(sample_files), custom_mapping=custom)
        assert result.success is True
        assert (sample_files / "TextFiles").is_dir()


class TestDateOrganizerTool:
    def setup_method(self):
        self.tool = DateOrganizerTool()

    def test_organize_by_date(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files))
        assert result.success is True

        # Check that date folders exist (YYYY-MM format)
        subdirs = [d.name for d in sample_files.iterdir() if d.is_dir()]
        assert len(subdirs) > 0
        # Should match YYYY-MM pattern
        import re

        for d in subdirs:
            assert re.match(r"\d{4}-\d{2}", d), f"Unexpected folder: {d}"

    def test_year_only_format(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files), format="year")
        assert result.success is True
        subdirs = [d.name for d in sample_files.iterdir() if d.is_dir()]
        import re

        for d in subdirs:
            assert re.match(r"\d{4}$", d)

    def test_filter_by_extension(self, sample_files: Path):
        result = self.tool.execute(path=str(sample_files), extension="jpg")
        assert result.success is True
        # Only 2 jpg files should be moved
