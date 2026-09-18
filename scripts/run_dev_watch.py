"""
OP(AI)UM — Development Runner with Auto-Restart

Watches for file changes and automatically restarts the application.
Perfect for rapid development and testing.

Usage: python scripts/run_dev_watch.py
"""

import hashlib
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["OPAIUM_ENV"] = "development"
os.environ["OPAIUM_LOG_LEVEL"] = "DEBUG"


class AppRestartHandler(FileSystemEventHandler):
    """Handles file change events and restarts the app with proper debouncing."""

    def __init__(self):
        self.process = None
        self._debounce_timer = None
        self._lock = threading.Lock()
        self._file_hashes: dict[str, str] = {}
        self._startup_grace_period = True
        self._startup_time = 0.0
        self._startup_grace_seconds = 5.0

        self.ignored_patterns = {
            "__pycache__",
            ".pyc",
            ".pyo",
            ".git",
            ".venv",
            ".db",
            ".db-journal",
            ".db-wal",
            ".log",
            ".enc",
            "node_modules",
            ".pytest_cache",
            ".mypy_cache",
            ".tmp",
            ".bak",
            "~",
            ".swp",
            ".swo",
        }

    def _hash_file(self, path: str) -> str | None:
        """Get MD5 hash of a file's contents to detect real changes."""
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except (OSError, PermissionError):
            return None

    def _has_content_changed(self, path: str) -> bool:
        """Check if file content actually changed (not just access time)."""
        new_hash = self._hash_file(path)
        if new_hash is None:
            return False

        old_hash = self._file_hashes.get(path)
        self._file_hashes[path] = new_hash

        if old_hash is None:
            return False

        return old_hash != new_hash

    def should_ignore(self, path: str) -> bool:
        """Check if file should be ignored."""
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in self.ignored_patterns)

    def on_modified(self, event):
        """Handle file modification with debouncing and content verification."""
        if event.is_directory:
            return

        if self.should_ignore(event.src_path):
            return

        if not (event.src_path.endswith(".py") or event.src_path.endswith(".qss")):
            return

        # Skip changes during startup grace period (imports trigger false events)
        if self._startup_grace_period:
            elapsed = time.time() - self._startup_time
            if elapsed < self._startup_grace_seconds:
                return
            self._startup_grace_period = False

        # Verify the file content actually changed (not just access time)
        if not self._has_content_changed(event.src_path):
            return

        rel_path = Path(event.src_path).relative_to(ROOT)
        self._schedule_restart(str(rel_path))

    def _schedule_restart(self, changed_file: str):
        """Debounce restarts: wait 2 seconds after last change before restarting."""
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                2.0,
                self._do_restart,
                args=[changed_file],
            )
            self._debounce_timer.start()

    def _do_restart(self, changed_file: str):
        """Actually perform the restart."""
        print(f"\n{'=' * 60}")
        print(f"  File changed: {changed_file}")
        print("  Restarting application...")
        print(f"{'=' * 60}\n")
        self.restart_app()

    def start_app(self):
        """Start the application process."""
        self._startup_grace_period = True
        self._startup_time = time.time()

        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "run_dev.py")],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        threading.Thread(target=self._stream_output, daemon=True).start()

    def _stream_output(self):
        """Stream subprocess output to console."""
        if self.process and self.process.stdout:
            for line in iter(self.process.stdout.readline, ""):
                if line:
                    print(line, end="")

    def restart_app(self):
        """Stop and restart the application."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

        time.sleep(0.5)
        self.start_app()

    def stop(self):
        """Stop the application and cancel pending restarts."""
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def snapshot_source_files(self):
        """Take initial hashes of all source files to establish baseline."""
        for pattern in ["src/**/*.py", "assets/**/*.qss"]:
            for filepath in ROOT.glob(pattern):
                path_str = str(filepath)
                if not self.should_ignore(path_str):
                    h = self._hash_file(path_str)
                    if h:
                        self._file_hashes[path_str] = h


def main():
    print("=" * 60)
    print("  OP(AI)UM - Development Mode with Auto-Restart")
    print("=" * 60)
    print(f"  Root: {ROOT}")
    print(f"  Python: {sys.version.split()[0]}")
    print()
    print("  Watching for changes...")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        from watchdog.observers import Observer
    except ImportError:
        print("[ERROR] Missing 'watchdog' package!")
        print("   Run: pip install watchdog")
        sys.exit(1)

    handler = AppRestartHandler()

    # Snapshot all source files before starting (baseline hashes)
    handler.snapshot_source_files()

    observer = Observer()
    observer.schedule(handler, str(ROOT / "src"), recursive=True)
    observer.schedule(handler, str(ROOT / "assets"), recursive=True)
    observer.start()

    handler.start_app()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        observer.stop()
        handler.stop()
        observer.join()
        print("Stopped.\n")


if __name__ == "__main__":
    main()
