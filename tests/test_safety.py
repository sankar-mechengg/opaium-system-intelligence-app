"""Tests for the AI safety layer: PathGuard, ApprovalBroker and the gated executor."""

from __future__ import annotations

import os
from pathlib import Path

from src.ai.function_registry import FunctionRegistry
from src.ai.safety import ApprovalBroker, ApprovalRequest, PathGuard
from src.ai.tool_executor import ToolExecutorWithJournal
from src.ai.tools.base_tool import ToolResult
from src.undo.operation_journal import OperationJournal
from src.undo.undo_manager import UndoManager


class TestPathGuard:
    def test_windows_dir_is_protected(self):
        windir = os.environ.get("WINDIR", r"C:\Windows")
        assert PathGuard.is_protected(windir) is True
        assert PathGuard.is_protected(os.path.join(windir, "System32")) is True

    def test_drive_root_is_protected(self):
        assert PathGuard.is_protected("C:\\") is True

    def test_user_profile_root_but_not_children(self, tmp_path: Path):
        profile = os.environ.get("USERPROFILE")
        if profile:
            assert PathGuard.is_protected(profile) is True
        assert PathGuard.is_protected(str(tmp_path)) is False

    def test_find_protected_scans_path_arguments(self, tmp_path: Path):
        hits = PathGuard.find_protected({"directory": "C:\\", "filenames": ["a"], "path": str(tmp_path)})
        assert hits == ["C:\\"]


class TestApprovalBroker:
    def test_no_handler_fails_closed(self):
        broker = ApprovalBroker()
        req = ApprovalRequest("delete_files", {}, "x", [])
        assert broker.request(req, timeout=0.1) is False

    def test_handler_approval_and_trust(self):
        broker = ApprovalBroker()
        broker.set_handler(lambda r: r.resolve(True, remember_for_session=True))
        req = ApprovalRequest("delete_files", {}, "x", [])
        assert broker.request(req) is True
        assert broker.is_trusted("delete_files") is True
        broker.clear_trust()
        assert broker.is_trusted("delete_files") is False

    def test_timeout_is_rejection(self):
        broker = ApprovalBroker()
        broker.set_handler(lambda r: None)  # never resolves
        req = ApprovalRequest("delete_files", {}, "x", [])
        assert broker.request(req, timeout=0.05) is False


class TestGatedExecutor:
    def _executor(self, tmp_path: Path, handler):  # type: ignore[no-untyped-def]
        registry = FunctionRegistry()
        registry.register_all_tools()
        journal = OperationJournal(db_path=tmp_path / "journal.db")
        broker = ApprovalBroker()
        broker.set_handler(handler)
        return ToolExecutorWithJournal(registry, journal, broker, confirm_destructive=True), journal

    def test_protected_path_refused_before_approval(self, tmp_path: Path):
        asked = []
        executor, journal = self._executor(tmp_path, lambda r: (asked.append(r), r.resolve(True)))
        result = executor.execute_tool("delete_files", {"directory": "C:\\"})
        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "protected" in result.message.lower()
        assert asked == []
        journal.close()

    def test_rejection_cancels_and_reports(self, tmp_path: Path):
        target = tmp_path / "a.txt"
        target.write_text("x")
        executor, journal = self._executor(tmp_path, lambda r: r.resolve(False))
        result = executor.execute_tool("delete_files", {"directory": str(tmp_path), "filenames": ["a.txt"]})
        assert result.success is False
        assert result.data == {"cancelled": True}
        assert target.exists()
        journal.close()

    def test_approved_rename_is_journaled_and_undoable(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("x")
        seen = []
        executor, journal = self._executor(tmp_path, lambda r: (seen.append(r), r.resolve(True)))
        result = executor.execute_tool(
            "rename_files",
            {"directory": str(tmp_path), "renames": [{"old_name": "a.txt", "new_name": "b.txt"}]},
        )
        assert result.success is True
        assert result.operation_id is not None
        assert seen[0].preview_lines  # a real preview was shown
        assert (tmp_path / "b.txt").exists()

        ok, _ = UndoManager(journal).undo_by_id(result.operation_id)
        assert ok is True
        assert (tmp_path / "a.txt").exists()
        journal.close()

    def test_read_only_subop_needs_no_approval(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("hello")
        asked = []
        executor, journal = self._executor(tmp_path, lambda r: (asked.append(r), r.resolve(True)))
        result = executor.execute_tool("file_content", {"operation": "read", "path": str(tmp_path / "a.txt")})
        assert result.success is True
        assert asked == []
        journal.close()

    def test_write_is_backed_up_and_undoable(self, tmp_path: Path, monkeypatch):
        from src.undo import backup_store

        monkeypatch.setattr(backup_store.AppConstants, "BACKUP_DIR", tmp_path / "backups")
        target = tmp_path / "a.txt"
        target.write_text("old")
        executor, journal = self._executor(tmp_path, lambda r: r.resolve(True))
        result = executor.execute_tool("file_content", {"operation": "write", "path": str(target), "content": "new"})
        assert result.success is True
        assert target.read_text() == "new"
        ok, _ = UndoManager(journal).undo_by_id(result.operation_id)
        assert ok is True
        assert target.read_text() == "old"
        journal.close()
