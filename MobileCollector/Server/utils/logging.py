"""Logging configuration using loguru."""

import sys
from loguru import logger


def setup_logging(log_file: str | None = None, level: str = "DEBUG"):
    """Setup loguru logging."""
    logger.remove()

    # Console output with colors
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # File output (if specified)
    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
        )

    return logger
