"""
Shared utilities — logging helpers and custom exception types.

Merges:
  - app/utils/logging_config.py
  - app/utils/exceptions.py
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    return logger


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def extract_text_content(content: object) -> str:
    """Flatten a LangChain message `content` field into plain text.

    Gemini 3 models return `content` as a list of blocks
    (`[{"type": "text", "text": "..."}]`) instead of a plain string, so every
    consumer has to normalise before concatenating or calling `.strip()`.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return "" if content is None else str(content)

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class HandbookException(Exception):
    """Base exception for Student Handbook errors."""
    pass


class HandbookNotFoundException(HandbookException):
    """Exception raised when a requested handbook section is not found."""

    def __init__(self, message: str = "Handbook section not found") -> None:
        self.message = message
        super().__init__(self.message)


class AIModelException(HandbookException):
    """Exception raised for errors during AI model inference."""

    def __init__(self, message: str = "Error communicating with the AI model") -> None:
        self.message = message
        super().__init__(self.message)
