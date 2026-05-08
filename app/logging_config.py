"""
JINNI GRID — Structured Logging Configuration
app/logging_config.py

Categories:
  jinni.system    — server lifecycle, config, startup/shutdown
  jinni.worker    — worker registry, heartbeat, commands
  jinni.execution — trade signals, order sends, fills, rejects
  jinni.strategy  — strategy upload, validation, loading
  jinni.error     — all errors (also logged to category logger)

Console: human-readable
Files: JSON-lines in data/logs/ (rotating, 10MB x 5 backups)
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs")

CATEGORIES = ["jinni.system", "jinni.worker", "jinni.execution", "jinni.strategy", "jinni.error"]


class JsonLineFormatter(logging.Formatter):
    """One JSON object per line — machine-parseable."""

    def format(self, record):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "event_data"):
            entry["data"] = record.event_data
        return json.dumps(entry, default=str)


class ReadableFormatter(logging.Formatter):
    """Console-friendly format."""

    def format(self, record):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        cat = record.name.replace("jinni.", "").upper()
        return f"[{ts}] [{cat}] {record.levelname[0]} | {record.getMessage()}"


def setup_logging(console_level=logging.INFO, file_level=logging.DEBUG):
    """Initialize all JINNI loggers. Call once at startup."""
    os.makedirs(LOG_DIR, exist_ok=True)

    # Console handler (shared)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(ReadableFormatter())

    for cat in CATEGORIES:
        logger = logging.getLogger(cat)
        logger.setLevel(file_level)
        logger.propagate = False

        # Remove existing handlers (safe for re-init)
        logger.handlers.clear()

        # File handler per category
        log_file = os.path.join(LOG_DIR, f"{cat.replace('.', '_')}.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(JsonLineFormatter())

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    # Also capture root-level warnings
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    if not root.handlers:
        root.addHandler(console_handler)

    logging.getLogger("jinni.system").info("Logging initialized")


def get_logger(category: str) -> logging.Logger:
    """Get a category logger. Category must be one of CATEGORIES."""
    name = category if category.startswith("jinni.") else f"jinni.{category}"
    return logging.getLogger(name)


def log_event(category: str, level: int, message: str, **data):
    """Log a structured event with optional data payload."""
    logger = get_logger(category)
    record = logger.makeRecord(
        logger.name, level, "(event)", 0, message, (), None,
    )
    if data:
        record.event_data = data
    logger.handle(record)