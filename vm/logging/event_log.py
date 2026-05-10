"""
JINNI GRID — Worker-Side Structured Event Logger
worker/event_log.py

Writes structured events to a local SQLite DB on the worker machine.
Events are also forwarded to Mother via heartbeat/status reports.

Categories: SYSTEM, EXECUTION, STRATEGY, PIPELINE, ERROR
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class WorkerEventLog:
    """Per-worker persistent event log."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self._lock = threading.Lock()
        os.makedirs(DATA_DIR, exist_ok=True)
        self._db_path = os.path.join(DATA_DIR, f"events_{worker_id}.db")
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                deployment_id TEXT,
                strategy_id TEXT,
                symbol TEXT,
                message TEXT,
                data_json TEXT,
                level TEXT DEFAULT 'INFO'
            );
            CREATE INDEX IF NOT EXISTS idx_wevents_ts ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_wevents_cat ON events(category);
        """)
        conn.commit()
        conn.close()

    def log(self, category: str, event_type: str, message: str,
            deployment_id: str = None, strategy_id: str = None,
            symbol: str = None, data: dict = None, level: str = "INFO"):
        """Write a structured event."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    INSERT INTO events (timestamp, category, event_type,
                        deployment_id, strategy_id, symbol, message,
                        data_json, level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now, category, event_type, deployment_id, strategy_id,
                    symbol, message,
                    json.dumps(data, default=str) if data else None, level,
                ))
                conn.commit()
            finally:
                conn.close()

        # Also print for console visibility
        print(f"[EVENT:{category}] {event_type} | {message}")

    def get_recent(self, limit: int = 100, category: str = None) -> list:
        conn = self._get_conn()
        try:
            if category:
                rows = conn.execute(
                    "SELECT * FROM events WHERE category=? ORDER BY id DESC LIMIT ?",
                    (category, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()