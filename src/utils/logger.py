"""
Logging configuration for the Date Night Reservation Agent.

Provides JSON-formatted logs as specified in PRD section 6.2.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in JSON format.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: Dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data

        return json.dumps(log_data)


def setup_logger(
    name: str,
    log_file: str = 'app.log',
    level: int = logging.INFO
) -> logging.Logger:
    """
    Set up a logger with JSON formatting.

    Args:
        name: Logger name (typically __name__)
        log_file: Log file name (saved in logs/ directory)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # File handler with JSON formatting
    log_path = Path(__file__).parent.parent.parent / 'logs' / log_file
    log_path.parent.mkdir(exist_ok=True)

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # Console handler with standard formatting
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def log_with_extra(logger: logging.Logger, level: int, message: str, **kwargs) -> None:
    """
    Log a message with extra data fields.

    Args:
        logger: Logger instance
        level: Log level (e.g., logging.INFO)
        message: Log message
        **kwargs: Extra fields to include in JSON log
    """
    extra = {'extra_data': kwargs}
    logger.log(level, message, extra=extra)
