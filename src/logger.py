"""
PL Capital Structured JSON Logger.

Writes one JSON object per line to logs/agent.log.
Uses Python's stdlib logging module — no external dependencies.

Functions
---------
log_query(question, tool_used, success, duration_ms)
log_error(context, error_msg)
log_cache_hit(key)
get_log_stats()  -> dict with counts from in-memory accumulators
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

# Ensure logs/ directory exists
_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / "agent.log"

# Configure a dedicated logger
_logger = logging.getLogger("pl_capital_agent")
_logger.setLevel(logging.DEBUG)

if not _logger.handlers:
    _handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False  # don't bubble to root logger / console

# In-memory counters (reset on process restart)
_stats = {
    "queries": 0,
    "errors": 0,
    "cache_hits": 0,
    "tool_usage": {},
}


def _write(record: dict) -> None:
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    _logger.info(json.dumps(record))


def log_query(
    question: str,
    tool_used: Optional[str],
    success: bool,
    duration_ms: float,
) -> None:
    """Log a completed agent query."""
    _stats["queries"] += 1
    if tool_used:
        _stats["tool_usage"][tool_used] = _stats["tool_usage"].get(tool_used, 0) + 1
    _write({
        "event": "query",
        "question": question[:200],          # truncate long questions
        "tool_used": tool_used,
        "success": success,
        "duration_ms": round(duration_ms, 1),
    })


def log_error(context: str, error_msg: str) -> None:
    """Log an error with its context."""
    _stats["errors"] += 1
    _write({
        "event": "error",
        "context": context,
        "error": error_msg[:500],
    })


def log_cache_hit(key: str) -> None:
    """Log a cache hit event."""
    _stats["cache_hits"] += 1
    _write({
        "event": "cache_hit",
        "key": key,
    })


def get_log_stats() -> dict:
    """Return in-memory usage statistics for this process lifetime."""
    return dict(_stats)
