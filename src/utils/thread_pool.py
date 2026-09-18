"""
OP(AI)UM — Thread Pool Workers

Qt-based worker classes for running long operations
(file scanning, API calls, etc.) off the main UI thread.

Rules that keep this crash-free with PySide6:
- Connect worker signals to *bound methods* of main-thread QObjects. Lambdas
  or partials that capture a QObject are not delivered reliably across
  threads and can crash Qt when the sender is destroyed.
- The signal-carrier object of every worker lives on the main thread and is
  kept alive by ThreadPoolManager until `finished` has been processed there,
  so queued `result` deliveries never target a freed object.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


def _safe_emit(signal: Any, *args: Any) -> None:
    """Emit unless the receiver side was torn down (app shutting down)."""
    with contextlib.suppress(RuntimeError):
        signal.emit(*args)


class WorkerSignals(QObject):
    """Signals emitted by background workers."""

    started = Signal()
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int, int)  # current, total


class _WorkerKeeper(QObject):
    """Main-thread owner of every in-flight worker (and its signal carrier)."""

    def __init__(self) -> None:
        super().__init__()
        self._live: dict[int, QRunnable] = {}

    def hold(self, worker: QRunnable) -> None:
        signals: WorkerSignals = worker.signals  # type: ignore[attr-defined]
        signals.setParent(self)
        self._live[id(signals)] = worker
        signals.finished.connect(self._on_finished)

    def _on_finished(self) -> None:
        signals = self.sender()
        if signals is None:
            return
        # `finished` is queued after `result`/`error`, so those were delivered already.
        self._live.pop(id(signals), None)
        signals.deleteLater()

    @property
    def active(self) -> int:
        return len(self._live)


class Worker(QRunnable):
    """
    Generic background worker that runs a callable in the thread pool.

    Usage:
        worker = Worker(my_function, arg1, arg2, kwarg1=value)
        worker.signals.result.connect(self.handle_result)   # bound method!
        worker.signals.error.connect(self.handle_error)
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
            _safe_emit(self.signals.started)
            result = self.fn(*self.args, **self.kwargs)
            _safe_emit(self.signals.result, result)
        except Exception as e:
            logger.error(f"Worker error in {getattr(self.fn, '__name__', 'worker')}: {e}")
            _safe_emit(self.signals.error, str(e))
        finally:
            _safe_emit(self.signals.finished)


class ProgressWorker(QRunnable):
    """
    Worker that supports progress reporting.

    The callable receives a `progress_callback(current, total)` as
    its first argument.
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
            _safe_emit(self.signals.started)

            def progress_callback(current: int, total: int) -> None:
                _safe_emit(self.signals.progress, current, total)

            result = self.fn(progress_callback, *self.args, **self.kwargs)
            _safe_emit(self.signals.result, result)
        except Exception as e:
            logger.error(f"ProgressWorker error in {getattr(self.fn, '__name__', 'worker')}: {e}")
            _safe_emit(self.signals.error, str(e))
        finally:
            _safe_emit(self.signals.finished)


class ThreadPoolManager:
    """
    Centralized thread pool management.
    Wraps QThreadPool for easy task submission.
    """

    _pool: QThreadPool | None = None
    _keeper: _WorkerKeeper | None = None

    @classmethod
    def pool(cls) -> QThreadPool:
        """Get the global thread pool."""
        if cls._pool is None:
            cls._pool = QThreadPool.globalInstance()
            cls._pool.setMaxThreadCount(max(4, min(8, cls._pool.maxThreadCount())))
            logger.debug(f"Thread pool initialized. Max threads: {cls._pool.maxThreadCount()}")
        return cls._pool

    @classmethod
    def keeper(cls) -> _WorkerKeeper:
        if cls._keeper is None:
            cls._keeper = _WorkerKeeper()
        return cls._keeper

    @classmethod
    def run(cls, worker: QRunnable) -> None:
        """Submit a worker to the thread pool (call from the main thread)."""
        if hasattr(worker, "signals"):
            cls.keeper().hold(worker)
        cls.pool().start(worker)

    @classmethod
    def active_thread_count(cls) -> int:
        """Get the number of active threads."""
        return cls.pool().activeThreadCount()

    @classmethod
    def wait_for_done(cls, timeout_ms: int = -1) -> bool:
        """Wait for all workers to complete."""
        return cls.pool().waitForDone(timeout_ms)
