"""
OP(AI)UM — Application Entry Point

Launches the OP(AI)UM System Intelligence Tool.
Handles platform checks, logging, config loading, single-instance
enforcement, crash reporting and main window initialization.

Command line:
    --minimized     start hidden in the tray (used by "Start with Windows")
    --log-level X   DEBUG / INFO / WARNING / ERROR
"""

from __future__ import annotations

import contextlib
import os
import sys
import traceback
from types import TracebackType


def _parse_args(argv: list[str]) -> dict[str, object]:
    opts: dict[str, object] = {"minimized": False, "log_level": os.environ.get("OPAIUM_LOG_LEVEL", "INFO")}
    it = iter(argv)
    for arg in it:
        if arg == "--minimized":
            opts["minimized"] = True
        elif arg == "--log-level":
            opts["log_level"] = next(it, "INFO")
    return opts


def _install_crash_handler() -> None:
    """Log uncaught exceptions and show a friendly dialog instead of dying silently."""
    from loguru import logger

    def handle(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        logger.critical(f"Unhandled exception:\n{text}")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            from src.config.constants import AppConstants

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "OP(AI)UM ran into a problem",
                    f"{exc_type.__name__}: {exc}\n\nDetails were written to:\n{AppConstants.LOG_DIR}",
                )
        except Exception:
            pass

    sys.excepthook = handle


def main() -> int:
    """Main entry point for OP(AI)UM. Returns the exit code."""
    if sys.platform != "win32":
        print("ERROR: OP(AI)UM is designed for Windows only.")
        return 1

    opts = _parse_args(sys.argv[1:])

    # Development convenience: load .env from the project root (never in frozen builds)
    if not getattr(sys, "frozen", False):
        try:
            from dotenv import load_dotenv

            load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
            opts["log_level"] = os.environ.get("OPAIUM_LOG_LEVEL", str(opts["log_level"]))
        except Exception:
            pass

    # High-DPI: let Qt scale crisply on mixed-DPI setups
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication

    from src.config.config_manager import ConfigManager
    from src.config.constants import AppConstants
    from src.utils.logger import setup_logger
    from src.utils.platform_check import check_platform

    setup_logger(str(opts["log_level"]))
    _install_crash_handler()

    from loguru import logger

    logger.info(f"Starting {AppConstants.APP_NAME} v{AppConstants.APP_VERSION}")

    platform_info = check_platform()
    if not platform_info.is_compatible:
        for issue in platform_info.issues:
            logger.error(issue)
        print(f"Platform check failed: {'; '.join(platform_info.issues)}")
        return 1

    AppConstants.ensure_dirs()

    config = ConfigManager()
    config.load()
    logger.info("Configuration loaded.")

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(AppConstants.APP_NAME)
    app.setApplicationDisplayName(AppConstants.APP_NAME)
    app.setOrganizationName(AppConstants.APP_ORG)
    app.setApplicationVersion(AppConstants.APP_VERSION)
    app.setStyle("Fusion")  # consistent base for the QSS design system
    app.setQuitOnLastWindowClosed(False)  # tray keeps us alive

    icon_path = AppConstants.LOGO_ICO_PATH if AppConstants.LOGO_ICO_PATH.exists() else AppConstants.LOGO_PATH
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Windows taskbar grouping / icon
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"{AppConstants.APP_ORG}.OPAIUM.{AppConstants.APP_VERSION}"
        )
    except Exception as e:
        logger.debug(f"Could not set Windows App ID: {e}")

    # Single instance — hand off to the running copy
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    server_name = "OPAIUM-single-instance"
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(400):
        logger.warning("Another instance is already running. Signalling it to show.")
        socket.write(b"show")
        socket.waitForBytesWritten(1000)
        socket.close()
        return 0
    socket.close()

    server = QLocalServer()
    QLocalServer.removeServer(server_name)
    if not server.listen(server_name):
        logger.warning(f"Single-instance server could not start: {server.errorString()}")

    from src.app import OpAIUMApp

    opaium_app = OpAIUMApp(app, config, start_minimized=bool(opts["minimized"]))
    opaium_app.initialize()

    def _on_new_connection() -> None:
        client = server.nextPendingConnection()
        if client:
            client.waitForReadyRead(500)
            opaium_app.raise_window()
            client.close()

    server.newConnection.connect(_on_new_connection)

    exit_code = app.exec()

    server.close()
    with contextlib.suppress(Exception):
        config.auto_save_if_dirty()
    logger.info(f"OP(AI)UM exiting with code {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
