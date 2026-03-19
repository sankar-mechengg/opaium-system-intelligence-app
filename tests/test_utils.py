"""Tests for src/utils/path_utils.py and src/utils/time_utils.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from src.utils.path_utils import PathUtils
from src.utils.time_utils import TimeGroup, TimeUtils


class TestPathUtils:
    def test_format_size_bytes(self):
        assert PathUtils.format_size(0) == "0 B"
        assert PathUtils.format_size(512) == "512 B"

    def test_format_size_kb(self):
        assert PathUtils.format_size(1024) == "1.0 KB"
        assert PathUtils.format_size(1536) == "1.5 KB"

    def test_format_size_mb(self):
        assert PathUtils.format_size(1024 * 1024) == "1.0 MB"

    def test_format_size_gb(self):
        assert PathUtils.format_size(1024**3) == "1.0 GB"

    def test_get_folder_size(self, sample_files: Path):
        size = PathUtils.get_folder_size(str(sample_files))
        assert size > 0

    def test_get_folder_size_empty(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert PathUtils.get_folder_size(str(empty)) == 0

    def test_is_system_or_hidden_normal(self, sample_files: Path):
        txt = sample_files / "readme.txt"
        assert not PathUtils.is_system_or_hidden(str(txt))

    def test_safe_name(self):
        assert PathUtils.safe_name('file<>:"/\\|?*.txt') != ""
        safe = PathUtils.safe_name("normal_file.txt")
        assert safe == "normal_file.txt"


class TestTimeUtils:
    def test_format_relative_just_now(self):
        now = datetime.now()
        result = TimeUtils.format_relative(now)
        assert "just now" in result.lower() or "second" in result.lower() or "moment" in result.lower()

    def test_format_relative_minutes(self):
        dt = datetime.now() - timedelta(minutes=5)
        result = TimeUtils.format_relative(dt)
        assert "5" in result and "min" in result.lower()

    def test_format_relative_hours(self):
        dt = datetime.now() - timedelta(hours=3)
        result = TimeUtils.format_relative(dt)
        assert "3" in result and "hour" in result.lower()

    def test_format_relative_days(self):
        dt = datetime.now() - timedelta(days=2)
        result = TimeUtils.format_relative(dt)
        assert "2" in result and "day" in result.lower()

    def test_get_time_group_recent(self):
        dt = datetime.now() - timedelta(hours=6)
        assert TimeUtils.get_time_group(dt) == TimeGroup.LAST_2_DAYS

    def test_get_time_group_week(self):
        dt = datetime.now() - timedelta(days=4)
        assert TimeUtils.get_time_group(dt) == TimeGroup.LAST_WEEK

    def test_get_time_group_month(self):
        dt = datetime.now() - timedelta(days=15)
        assert TimeUtils.get_time_group(dt) == TimeGroup.LAST_MONTH

    def test_get_time_group_older(self):
        dt = datetime.now() - timedelta(days=60)
        assert TimeUtils.get_time_group(dt) == TimeGroup.OLDER

    def test_group_order(self):
        order = TimeUtils.group_order()
        assert len(order) == 4
        assert order[0] == TimeGroup.LAST_2_DAYS
        assert order[-1] == TimeGroup.OLDER

    def test_format_datetime(self):
        dt = datetime(2024, 6, 15, 14, 30, 0)
        result = TimeUtils.format_datetime(dt)
        assert "2024" in result
        assert "14:30" in result or "2:30" in result
