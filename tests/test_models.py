"""Tests for src/core/models.py."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.core.models import (
    RecentItem, FolderItem, FileItem, TrackingRecord,
    OperationRecord, ItemType,
)
from src.utils.time_utils import TimeGroup


class TestRecentItem:

    def test_create_folder_item(self):
        item = RecentItem(
            path="C:\\Users\\Test\\Documents",
            name="Documents",
            item_type=ItemType.FOLDER,
            accessed_at=datetime.now(),
            time_group=TimeGroup.LAST_2_DAYS,
        )
        assert item.is_folder is True
        assert item.is_file is False
        assert item.name == "Documents"

    def test_create_file_item(self):
        item = RecentItem(
            path="C:\\Users\\Test\\report.pdf",
            name="report.pdf",
            item_type=ItemType.FILE,
            accessed_at=datetime.now(),
            time_group=TimeGroup.LAST_WEEK,
            size_bytes=1024000,
            extension="pdf",
        )
        assert item.is_file is True
        assert item.extension == "pdf"
        assert item.size_bytes == 1024000

    def test_broken_item(self):
        item = RecentItem(
            path="C:\\nonexistent\\path",
            name="gone",
            item_type=ItemType.FOLDER,
            accessed_at=datetime.now(),
            time_group=TimeGroup.OLDER,
            exists=False,
            is_broken=True,
        )
        assert item.is_broken is True
        assert item.exists is False


class TestFileItem:

    def test_image_classification(self):
        item = FileItem(
            path="/test/photo.jpg",
            name="photo.jpg",
            size_bytes=5000,
            extension="jpg",
        )
        assert item.is_image is True
        assert item.is_document is False

    def test_document_classification(self):
        item = FileItem(
            path="/test/report.pdf",
            name="report.pdf",
            size_bytes=50000,
            extension="pdf",
        )
        assert item.is_document is True
        assert item.is_image is False

    def test_archive_classification(self):
        item = FileItem(
            path="/test/backup.zip",
            name="backup.zip",
            size_bytes=100000,
            extension="zip",
        )
        assert item.is_archive is True


class TestOperationRecord:

    def test_create_rename_operation(self):
        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="rename",
            description="Renamed 5 files",
            source_paths=["/old/a.txt", "/old/b.txt"],
            dest_paths=["/old/a_new.txt", "/old/b_new.txt"],
            is_undoable=True,
        )
        assert op.operation_type == "rename"
        assert op.is_undoable is True
        assert len(op.source_paths) == 2

    def test_non_undoable_operation(self):
        op = OperationRecord(
            timestamp=datetime.now(),
            operation_type="delete",
            description="Deleted 3 files",
            source_paths=["/a.txt"],
            is_undoable=False,
        )
        assert op.is_undoable is False
        assert op.is_undone is False
