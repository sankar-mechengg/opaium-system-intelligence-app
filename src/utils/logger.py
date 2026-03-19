"""
OP(AI)UM — Logging Configuration

Sets up structured logging with loguru. Logs to both console and
rotating log files in AppData/OPAIUM/logs/.
"""

from __future__ import annotations

import sys

from loguru import logger

from src.config.constants import AppConstants


def setup_logger(log_level: str = "INFO") -> None:
    """
    Configure application-wide logging.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
    """
    # Remove default loguru handler
    logger.remove()

    # Console handler (colored, concise)
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # Ensure log directory exists
    AppConstants.ensure_dirs()

    # File handler (rotating, detailed)
    logger.add(
        str(AppConstants.LOG_DIR / "opaium_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        format=("{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"),
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,  # Thread-safe
    )

    # Error-only file handler for quick diagnostics
    logger.add(
        str(AppConstants.LOG_DIR / "errors.log"),
        level="ERROR",
        format=("{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}\n{exception}"),
        rotation="5 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
    )

    logger.info(f"OP(AI)UM Logger initialized. Level: {log_level}")
    logger.info(f"Log directory: {AppConstants.LOG_DIR}")
