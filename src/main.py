"""
OP(AI)UM — Application Entry Point

Launches the OP(AI)UM System Intelligence Tool.
Handles platform checks, logging setup, config loading,
authentication, and main window initialization.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    """
    Main entry point for OP(AI)UM.

    Returns:
        Exit code (0 for success).
    """
    # Ensure we're on Windows
    if sys.platform != "win32":
        print("ERROR: OP(AI)UM is designed for Windows only.")
        return 1

    # Set high DPI attributes before QApplication is created
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from src.config.config_manager import ConfigManager
    from src.config.constants import AppConstants
    from src.utils.logger import setup_logger
    from src.utils.platform_check import check_platform

    # Initialize logging first
    setup_logger("INFO")

    from loguru import logger

    logger.info(f"Starting {AppConstants.APP_NAME} v{AppConstants.APP_VERSION}")

    # Platform compatibility check
    platform_info = check_platform()
    if not platform_info.is_compatible:
        for issue in platform_info.issues:
            logger.error(issue)
        print(f"Platform check failed: {'; '.join(platform_info.issues)}")
        return 1

    # Ensure app directories exist
    AppConstants.ensure_dirs()

    # Load configuration
    config = ConfigManager()
    config.load()

    # Update log level from config if needed
    logger.info("Configuration loaded.")

    # Create Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName(AppConstants.APP_NAME)
    app.setOrganizationName(AppConstants.APP_ORG)
    app.setApplicationVersion(AppConstants.APP_VERSION)

    # Set application icon (for window and taskbar)
    icon = None
    # Try .ico first (better for Windows taskbar)
    if AppConstants.LOGO_ICO_PATH.exists():
        icon = QIcon(str(AppConstants.LOGO_ICO_PATH))
    elif AppConstants.LOGO_PATH.exists():
        icon = QIcon(str(AppConstants.LOGO_PATH))

    if icon:
        app.setWindowIcon(icon)

    # Set Windows taskbar icon explicitly
    if sys.platform == "win32":
        try:
            import ctypes

            # Set app user model ID for Windows taskbar
            myappid = f"{AppConstants.APP_ORG}.{AppConstants.APP_NAME}.{AppConstants.APP_VERSION}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logger.debug(f"Could not set Windows App ID: {e}")

    # Prevent multiple instances — if already running, ask the first instance to show itself
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(AppConstants.APP_NAME)
    if socket.waitForConnected(500):
        logger.warning("Another instance is already running. Signalling it to show.")
        socket.write(b"show")
        socket.waitForBytesWritten(1000)
        socket.close()
        return 0
    socket.close()

    server = QLocalServer()
    server.removeServer(AppConstants.APP_NAME)
    server.listen(AppConstants.APP_NAME)

    # Import the main app controller (deferred to avoid circular imports)
    from src.app import OpAIUMApp

    # Create and run the application
    opaium_app = OpAIUMApp(app, config)
    opaium_app.initialize()

    # When another instance connects, bring the existing window to front
    def _on_new_connection() -> None:
        client = server.nextPendingConnection()
        if client:
            client.waitForReadyRead(1000)
            opaium_app.raise_window()
            client.close()

    server.newConnection.connect(_on_new_connection)

    exit_code = app.exec()

    # Cleanup
    server.close()
    config.auto_save_if_dirty()
    logger.info(f"OP(AI)UM exiting with code {exit_code}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
