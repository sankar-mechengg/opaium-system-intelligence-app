"""
OP(AI)UM — Thread Pool Workers

Qt-based worker classes for running long operations
(file scanning, API calls, etc.) off the main UI thread.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from loguru import logger


class WorkerSignals(QObject):
    """Signals emitted by background workers."""

    started = Signal()
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int, int)  # current, total


class Worker(QRunnable):
    """
    Generic background worker that runs a callable in the thread pool.

    Usage:
        worker = Worker(my_function, arg1, arg2, kwarg1=value)
        worker.signals.result.connect(handle_result)
        worker.signals.error.connect(handle_error)
        ThreadPoolManager.run(worker)
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Execute the worker function."""
        try:
            self.signals.started.emit()
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            logger.error(f"Worker error in {self.fn.__name__}: {e}")
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class ProgressWorker(QRunnable):
    """
    Worker that supports progress reporting.

    The callable receives a `progress_callback(current, total)` as
    its first argument.

    Usage:
        def scan_files(progress_callback, folder_path):
            for i, f in enumerate(files):
                progress_callback(i, len(files))
                process(f)
            return results

        worker = ProgressWorker(scan_files, "/path/to/folder")
        worker.signals.progress.connect(update_progress_bar)
        ThreadPoolManager.run(worker)
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Execute with progress callback injected."""
        try:
            self.signals.started.emit()

            def progress_callback(current: int, total: int) -> None:
                self.signals.progress.emit(current, total)

            result = self.fn(progress_callback, *self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            logger.error(f"ProgressWorker error in {self.fn.__name__}: {e}")
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class ThreadPoolManager:
    """
    Centralized thread pool management.
    Wraps QThreadPool for easy task submission.
    """

    _pool: Optional[QThreadPool] = None

    @classmethod
    def pool(cls) -> QThreadPool:
        """Get the global thread pool."""
        if cls._pool is None:
            cls._pool = QThreadPool.globalInstance()
            cls._pool.setMaxThreadCount(8)
            logger.debug(
                f"Thread pool initialized. Max threads: {cls._pool.maxThreadCount()}"
            )
        return cls._pool

    @classmethod
    def run(cls, worker: QRunnable) -> None:
        """Submit a worker to the thread pool."""
        cls.pool().start(worker)

    @classmethod
    def active_thread_count(cls) -> int:
        """Get the number of active threads."""
        return cls.pool().activeThreadCount()

    @classmethod
    def wait_for_done(cls, timeout_ms: int = -1) -> bool:
        """Wait for all workers to complete."""
        return cls.pool().waitForDone(timeout_ms)
