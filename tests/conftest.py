"""
OP(AI)UM — Shared Pytest Fixtures

Provides temporary directories, mock configurations, and
sample file structures for all tests.
"""

from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a clean temporary directory."""
    return tmp_path


@pytest.fixture
def sample_files(tmp_path: Path) -> Path:
    """Create a directory with sample files of various types."""
    d = tmp_path / "sample"
    d.mkdir()

    # Text files
    (d / "readme.txt").write_text("Hello World")
    (d / "notes.md").write_text("# Notes\n\nSome notes here.")
    (d / "data.csv").write_text("name,value\nfoo,1\nbar,2")

    # Fake images (just content, not real images)
    (d / "photo1.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 1024)
    (d / "photo2.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 2048)
    (d / "icon.png").write_bytes(b"\x89PNG" + b"\x00" * 512)

    # Documents
    (d / "report.pdf").write_bytes(b"%PDF-1.4" + b"\x00" * 4096)
    (d / "sheet.xlsx").write_bytes(b"PK" + b"\x00" * 3072)

    # Code
    (d / "script.py").write_text("print('hello')\n")
    (d / "app.js").write_text("console.log('hello');\n")

    # Archives
    (d / "backup.zip").write_bytes(b"PK\x03\x04" + b"\x00" * 2048)

    return d


@pytest.fixture
def nested_dirs(tmp_path: Path) -> Path:
    """Create a nested directory structure."""
    root = tmp_path / "nested"
    root.mkdir()

    # Create structure:
    # nested/
    #   file1.txt
    #   sub1/
    #     file2.txt
    #     sub1a/
    #       file3.txt
    #   sub2/
    #     (empty)
    #   sub3/
    #     sub3a/
    #       (empty)

    (root / "file1.txt").write_text("root file")
    (root / "sub1").mkdir()
    (root / "sub1" / "file2.txt").write_text("sub1 file")
    (root / "sub1" / "sub1a").mkdir()
    (root / "sub1" / "sub1a" / "file3.txt").write_text("deep file")
    (root / "sub2").mkdir()  # Empty
    (root / "sub3").mkdir()
    (root / "sub3" / "sub3a").mkdir()  # Nested empty

    return root


@pytest.fixture
def duplicate_files(tmp_path: Path) -> Path:
    """Create files with duplicates (same content)."""
    d = tmp_path / "dupes"
    d.mkdir()

    content_a = b"This is content A" * 100
    content_b = b"This is content B" * 200

    (d / "original_a.txt").write_bytes(content_a)
    (d / "copy_a.txt").write_bytes(content_a)
    (d / "another_a.txt").write_bytes(content_a)

    (d / "original_b.dat").write_bytes(content_b)
    (d / "copy_b.dat").write_bytes(content_b)

    (d / "unique.txt").write_bytes(b"unique content")

    return d


@pytest.fixture
def old_files(tmp_path: Path) -> Path:
    """Create files with old modification times."""
    d = tmp_path / "old"
    d.mkdir()

    now = datetime.now()

    for i, age_days in enumerate([1, 7, 30, 90, 365, 730]):
        f = d / f"file_{age_days}d.txt"
        f.write_text(f"File aged {age_days} days")
        mtime = (now - timedelta(days=age_days)).timestamp()
        os.utime(f, (mtime, mtime))

    return d


@pytest.fixture
def mock_config_data() -> dict:
    """Return a mock configuration dictionary."""
    return {
        "appearance": {
            "theme": "dark",
            "card_width": 160,
            "card_height": 140,
            "show_hidden_folders": False,
        },
        "ai": {
            "model": "gpt-4.1-mini",
            "speech_model": "whisper-1",
            "max_tokens": 2048,
            "temperature": 0.3,
        },
        "refresh": {
            "auto_refresh_enabled": True,
            "auto_refresh_interval_min": 5,
        },
        "startup": {
            "start_with_windows": False,
            "start_minimized": False,
            "minimize_to_tray": False,
            "close_to_tray": False,
        },
        "undo": {
            "max_history": 100,
            "purge_after_days": 7,
        },
    }
