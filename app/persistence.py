"""
JINNI GRID — SQLite Persistence Layer
app/persistence.py

Single database: data/jinni_grid.db
WAL mode for concurrent reads during writes.
All tables created on init if not exist.

Stores:
  - strategies (metadata, not source code — source stays on disk)
  - workers (last heartbeat, machine info, state)
  - deployments (config, state, error)
  - events (structured audit trail)
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "jinni_grid.db")

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Thread-local connection with WAL mode."""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def init_db():
    """Create all tables. Safe to call multiple times."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS strategies (
            strategy_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            class_name TEXT,
            name TEXT,
            description TEXT,
            version TEXT,
            min_lookback INTEGER DEFAULT 0,
            file_hash TEXT,
            file_path TEXT,
            parameters_json TEXT DEFAULT '{}',
            uploaded_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_valid INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            worker_name TEXT,
            host TEXT,
            reported_state TEXT DEFAULT 'offline',
            last_heartbeat_at TEXT,
            agent_version TEXT,
            mt5_state TEXT,
            account_id TEXT,
            broker TEXT,
            active_strategies_json TEXT DEFAULT '[]',
            open_positions_count INTEGER DEFAULT 0,
            floating_pnl REAL DEFAULT 0.0,
            errors_json TEXT DEFAULT '[]',
            total_ticks INTEGER DEFAULT 0,
            total_bars INTEGER DEFAULT 0,
            on_bar_calls INTEGER DEFAULT 0,
            signal_count INTEGER DEFAULT 0,
            last_bar_time TEXT,
            current_price REAL,
            first_seen_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS deployments (
            deployment_id TEXT PRIMARY KEY,
            strategy_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            tick_lookback_value INTEGER DEFAULT 30,
            tick_lookback_unit TEXT DEFAULT 'minutes',
            bar_size_points REAL NOT NULL,
            max_bars_in_memory INTEGER DEFAULT 500,
            lot_size REAL DEFAULT 0.01,
            strategy_parameters_json TEXT DEFAULT '{}',
            state TEXT DEFAULT 'queued',
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            category TEXT NOT NULL,
            event_type TEXT NOT NULL,
            worker_id TEXT,
            strategy_id TEXT,
            deployment_id TEXT,
            symbol TEXT,
            message TEXT,
            data_json TEXT,
            level TEXT DEFAULT 'INFO'
        );
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            deployment_id TEXT,
            strategy_id TEXT,
            worker_id TEXT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            entry_time TEXT,
            exit_time TEXT,
            exit_reason TEXT,
            sl_level REAL,
            tp_level REAL,
            lot_size REAL DEFAULT 0.01,
            ticket INTEGER,
            points_pnl REAL DEFAULT 0.0,
            profit REAL DEFAULT 0.0,
            bars_held INTEGER DEFAULT 0,
            status TEXT DEFAULT 'closed',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
        CREATE INDEX IF NOT EXISTS idx_trades_worker ON trades(worker_id);

        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
        CREATE INDEX IF NOT EXISTS idx_events_worker ON events(worker_id);
        CREATE INDEX IF NOT EXISTS idx_events_deployment ON events(deployment_id);

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS equity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            equity REAL DEFAULT 0.0,
            floating_pnl REAL DEFAULT 0.0,
            open_positions INTEGER DEFAULT 0,
            cumulative_pnl REAL DEFAULT 0.0
        );
        CREATE INDEX IF NOT EXISTS idx_equity_ts ON equity_snapshots(timestamp);
    """)
    conn.commit()
    # Migrations — add columns that may not exist in older DBs
    _migrations = [
        ("workers", "account_balance", "REAL DEFAULT 0.0"),
        ("workers", "account_equity", "REAL DEFAULT 0.0"),
    ]
    for table, col, col_type in _migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists


# =============================================================================
# Strategy Persistence
# =============================================================================

def save_strategy(strategy_id: str, data: dict):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO strategies (strategy_id, filename, class_name, name, description,
            version, min_lookback, file_hash, file_path, parameters_json,
            uploaded_at, updated_at, is_valid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(strategy_id) DO UPDATE SET
            filename=excluded.filename, class_name=excluded.class_name,
            name=excluded.name, description=excluded.description,
            version=excluded.version, min_lookback=excluded.min_lookback,
            file_hash=excluded.file_hash, file_path=excluded.file_path,
            parameters_json=excluded.parameters_json,
            updated_at=excluded.updated_at, is_valid=excluded.is_valid
    """, (
        strategy_id, data.get("filename", ""), data.get("class_name", ""),
        data.get("name", ""), data.get("description", ""),
        data.get("version", ""), data.get("min_lookback", 0),
        data.get("file_hash", ""), data.get("file_path", ""),
        json.dumps(data.get("parameters", {})),
        data.get("uploaded_at", now), now,
        1 if data.get("is_valid", True) else 0,
    ))
    conn.commit()


def get_all_strategies_db() -> List[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM strategies WHERE is_valid = 1 ORDER BY uploaded_at DESC").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["parameters"] = json.loads(d.pop("parameters_json", "{}"))
        result.append(d)
    return result


def get_strategy_db(strategy_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM strategies WHERE strategy_id = ?", (strategy_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["parameters"] = json.loads(d.pop("parameters_json", "{}"))
    return d


def delete_strategy_db(strategy_id: str):
    conn = _get_conn()
    conn.execute("UPDATE strategies SET is_valid = 0, updated_at = ? WHERE strategy_id = ?",
                 (datetime.now(timezone.utc).isoformat(), strategy_id))
    conn.commit()


# =============================================================================
# Worker Persistence
# =============================================================================

def save_worker(worker_id: str, data: dict):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    existing = conn.execute("SELECT first_seen_at FROM workers WHERE worker_id = ?",
                            (worker_id,)).fetchone()
    first_seen = existing["first_seen_at"] if existing else now

    conn.execute("""
        INSERT INTO workers (worker_id, worker_name, host, reported_state,
            last_heartbeat_at, agent_version, mt5_state, account_id, broker,
            active_strategies_json, open_positions_count, floating_pnl,
            errors_json, total_ticks, total_bars, on_bar_calls, signal_count,
            last_bar_time, current_price, first_seen_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(worker_id) DO UPDATE SET
            worker_name=excluded.worker_name, host=excluded.host,
            reported_state=excluded.reported_state,
            last_heartbeat_at=excluded.last_heartbeat_at,
            agent_version=excluded.agent_version, mt5_state=excluded.mt5_state,
            account_id=excluded.account_id, broker=excluded.broker,
            active_strategies_json=excluded.active_strategies_json,
            open_positions_count=excluded.open_positions_count,
            floating_pnl=excluded.floating_pnl, errors_json=excluded.errors_json,
            total_ticks=excluded.total_ticks, total_bars=excluded.total_bars,
            on_bar_calls=excluded.on_bar_calls, signal_count=excluded.signal_count,
            last_bar_time=excluded.last_bar_time, current_price=excluded.current_price,
            updated_at=excluded.updated_at
    """, (
        worker_id, data.get("worker_name"), data.get("host"),
        data.get("state", "online"), data.get("last_heartbeat_at", now),
        data.get("agent_version"), data.get("mt5_state"),
        data.get("account_id"), data.get("broker"),
        json.dumps(data.get("active_strategies") or []),
        data.get("open_positions_count", 0),
        data.get("floating_pnl", 0.0),
        json.dumps(data.get("errors") or []),
        data.get("total_ticks", 0), data.get("total_bars", 0),
        data.get("on_bar_calls", 0), data.get("signal_count", 0),
        data.get("last_bar_time"), data.get("current_price"),
        first_seen, now,
    ))
    # Update account fields (may not exist in INSERT if schema is old)
    if data.get("account_balance") is not None or data.get("account_equity") is not None:
        try:
            conn.execute("""
                UPDATE workers SET account_balance=?, account_equity=?
                WHERE worker_id=?
            """, (
                data.get("account_balance", 0.0),
                data.get("account_equity", 0.0),
                worker_id,
            ))
        except sqlite3.OperationalError:
            pass
    conn.commit()


def get_all_workers_db() -> List[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM workers ORDER BY last_heartbeat_at DESC").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["active_strategies"] = json.loads(d.pop("active_strategies_json", "[]"))
        d["errors"] = json.loads(d.pop("errors_json", "[]"))
        result.append(d)
    return result


def get_worker_db(worker_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM workers WHERE worker_id = ?", (worker_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["active_strategies"] = json.loads(d.pop("active_strategies_json", "[]"))
    d["errors"] = json.loads(d.pop("errors_json", "[]"))
    return d


# =============================================================================
# Deployment Persistence
# =============================================================================

def save_deployment(deployment_id: str, data: dict):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO deployments (deployment_id, strategy_id, worker_id, symbol,
            tick_lookback_value, tick_lookback_unit, bar_size_points,
            max_bars_in_memory, lot_size, strategy_parameters_json,
            state, last_error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(deployment_id) DO UPDATE SET
            state=excluded.state, last_error=excluded.last_error,
            updated_at=excluded.updated_at
    """, (
        deployment_id, data["strategy_id"], data["worker_id"], data["symbol"],
        data.get("tick_lookback_value", 30), data.get("tick_lookback_unit", "minutes"),
        data["bar_size_points"], data.get("max_bars_in_memory", 500),
        data.get("lot_size", 0.01),
        json.dumps(data.get("strategy_parameters") or {}),
        data.get("state", "queued"), data.get("last_error"),
        data.get("created_at", now), now,
    ))
    conn.commit()


def update_deployment_state_db(deployment_id: str, state: str, error: str = None):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    if error is not None:
        conn.execute("UPDATE deployments SET state=?, last_error=?, updated_at=? WHERE deployment_id=?",
                     (state, error, now, deployment_id))
    else:
        if state == "running":
            conn.execute("UPDATE deployments SET state=?, last_error=NULL, updated_at=? WHERE deployment_id=?",
                         (state, now, deployment_id))
        else:
            conn.execute("UPDATE deployments SET state=?, updated_at=? WHERE deployment_id=?",
                         (state, now, deployment_id))
    conn.commit()


def get_all_deployments_db() -> List[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM deployments ORDER BY created_at DESC").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["strategy_parameters"] = json.loads(d.pop("strategy_parameters_json", "{}"))
        result.append(d)
    return result


def get_deployment_db(deployment_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM deployments WHERE deployment_id = ?", (deployment_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["strategy_parameters"] = json.loads(d.pop("strategy_parameters_json", "{}"))
    return d


# =============================================================================
# Event Log Persistence
# =============================================================================

def log_event_db(category: str, event_type: str, message: str,
                 worker_id: str = None, strategy_id: str = None,
                 deployment_id: str = None, symbol: str = None,
                 data: dict = None, level: str = "INFO"):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO events (timestamp, category, event_type, worker_id,
            strategy_id, deployment_id, symbol, message, data_json, level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now, category, event_type, worker_id, strategy_id,
        deployment_id, symbol, message,
        json.dumps(data, default=str) if data else None, level,
    ))
    conn.commit()


def get_events_db(limit: int = 100, category: str = None,
                  worker_id: str = None, deployment_id: str = None) -> List[dict]:
    conn = _get_conn()
    query = "SELECT * FROM events WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if worker_id:
        query += " AND worker_id = ?"
        params.append(worker_id)
    if deployment_id:
        query += " AND deployment_id = ?"
        params.append(deployment_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]

# =============================================================================
# Trade Persistence
# =============================================================================

def save_trade_db(data: dict):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO trades (trade_id, deployment_id, strategy_id, worker_id,
            symbol, direction, entry_price, exit_price, entry_time, exit_time,
            exit_reason, sl_level, tp_level, lot_size, ticket,
            points_pnl, profit, bars_held, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("trade_id"), data.get("deployment_id"), data.get("strategy_id"),
        data.get("worker_id"), data.get("symbol", ""), data.get("direction", ""),
        data.get("entry_price", 0), data.get("exit_price"),
        data.get("entry_time"), data.get("exit_time"),
        data.get("exit_reason"), data.get("sl_level"), data.get("tp_level"),
        data.get("lot_size", 0.01), data.get("ticket"),
        data.get("points_pnl", 0), data.get("profit", 0),
        data.get("bars_held", 0), data.get("status", "closed"), now,
    ))
    conn.commit()


def get_all_trades_db(limit: int = 500, strategy_id: str = None,
                      worker_id: str = None, symbol: str = None) -> List[dict]:
    conn = _get_conn()
    query = "SELECT * FROM trades WHERE 1=1"
    params: list = []
    if strategy_id:
        query += " AND strategy_id = ?"
        params.append(strategy_id)
    if worker_id:
        query += " AND worker_id = ?"
        params.append(worker_id)
    if symbol:
        query += " AND symbol = ?"
        params.append(symbol)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]

# =============================================================================
# Settings Persistence
# =============================================================================

_DEFAULT_SETTINGS = {
    "refresh_interval": "5",
    "default_symbol": "XAUUSD",
    "default_bar_size": "100",
    "default_lot_size": "0.01",
    "debug_mode": "true",
    "worker_timeout_seconds": "90",
    "log_verbosity": "INFO",
}


def get_setting(key: str, default: str = None) -> Optional[str]:
    conn = _get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row["value"]
    return default if default is not None else _DEFAULT_SETTINGS.get(key)


def get_all_settings() -> dict:
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    result = dict(_DEFAULT_SETTINGS)
    for r in rows:
        result[r["key"]] = r["value"]
    return result


def save_setting(key: str, value: str):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """, (key, str(value), now))
    conn.commit()


def save_settings_bulk(settings: dict):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    for key, value in settings.items():
        conn.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (key, str(value), now))
    conn.commit()


# =============================================================================
# Equity Snapshots
# =============================================================================

def save_equity_snapshot_db(balance: float, equity: float,
                            floating_pnl: float = 0.0,
                            open_positions: int = 0,
                            cumulative_pnl: float = 0.0):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO equity_snapshots (timestamp, balance, equity, floating_pnl,
            open_positions, cumulative_pnl)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (now, balance, equity, floating_pnl, open_positions, cumulative_pnl))
    conn.commit()


def get_equity_snapshots_db(limit: int = 2000) -> List[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM equity_snapshots ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def clear_equity_snapshots_db():
    conn = _get_conn()
    conn.execute("DELETE FROM equity_snapshots")
    conn.commit()


# =============================================================================
# Admin Functions
# =============================================================================

def delete_all_trades_db():
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) as c FROM trades").fetchone()["c"]
    conn.execute("DELETE FROM trades")
    conn.commit()
    return count


def delete_trades_by_strategy_db(strategy_id: str) -> int:
    conn = _get_conn()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM trades WHERE strategy_id = ?", (strategy_id,)
    ).fetchone()["c"]
    conn.execute("DELETE FROM trades WHERE strategy_id = ?", (strategy_id,))
    conn.commit()
    return count


def delete_trades_by_worker_db(worker_id: str) -> int:
    conn = _get_conn()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM trades WHERE worker_id = ?", (worker_id,)
    ).fetchone()["c"]
    conn.execute("DELETE FROM trades WHERE worker_id = ?", (worker_id,))
    conn.commit()
    return count


def full_system_reset_db() -> dict:
    """Factory reset — delete ALL data including strategies."""
    conn = _get_conn()
    counts = {}
    for table in ["trades", "events", "deployments", "equity_snapshots",
                   "workers", "strategies"]:
        try:
            c = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            conn.execute(f"DELETE FROM {table}")
            counts[f"{table}_deleted"] = c
        except Exception:
            counts[f"{table}_deleted"] = 0
    # Keep settings — don't delete
    conn.commit()

    # Delete strategy files from disk
    try:
        import glob, os
        for path in glob.glob("strategies/*.py"):
            os.remove(path)
    except Exception:
        pass

    return counts


def remove_worker_db(worker_id: str) -> dict:
    conn = _get_conn()
    conn.execute("DELETE FROM workers WHERE worker_id = ?", (worker_id,))
    dep_count = conn.execute(
        "SELECT COUNT(*) as c FROM deployments WHERE worker_id = ?", (worker_id,)
    ).fetchone()["c"]
    conn.execute(
        "UPDATE deployments SET state='stopped', last_error='worker removed' "
        "WHERE worker_id = ? AND state NOT IN ('stopped','failed')",
        (worker_id,)
    )
    conn.commit()
    return {"worker_id": worker_id, "deployments_stopped": dep_count}


def remove_stale_workers_db(threshold_seconds: int = 300) -> int:
    """Remove workers not seen for longer than threshold."""
    conn = _get_conn()
    now = datetime.now(timezone.utc)
    rows = conn.execute("SELECT worker_id, last_heartbeat_at FROM workers").fetchall()
    removed = 0
    for r in rows:
        try:
            last = datetime.fromisoformat(r["last_heartbeat_at"])
            if (now - last).total_seconds() > threshold_seconds:
                conn.execute("DELETE FROM workers WHERE worker_id = ?", (r["worker_id"],))
                removed += 1
        except (TypeError, ValueError):
            conn.execute("DELETE FROM workers WHERE worker_id = ?", (r["worker_id"],))
            removed += 1
    conn.commit()
    return removed


def clear_events_db() -> int:
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
    conn.execute("DELETE FROM events")
    conn.commit()
    return count


def get_system_stats_db() -> dict:
    conn = _get_conn()
    stats = {}
    for table in ("strategies", "workers", "deployments", "events", "trades",
                   "settings", "equity_snapshots"):
        try:
            row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            stats[f"{table}_count"] = row["c"]
        except Exception:
            stats[f"{table}_count"] = 0

    db_size = 0
    if os.path.exists(DB_PATH):
        db_size = os.path.getsize(DB_PATH)
    stats["db_size_bytes"] = db_size
    stats["db_size_mb"] = round(db_size / (1024 * 1024), 2)
    stats["db_path"] = DB_PATH

    active = conn.execute(
        "SELECT COUNT(*) as c FROM deployments WHERE state NOT IN ('stopped','failed')"
    ).fetchone()["c"]
    stats["active_deployments"] = active

    return stats


def full_system_reset_db() -> dict:
    """Nuclear option — clear everything."""
    conn = _get_conn()
    counts = {}
    for table in ("trades", "events", "deployments", "equity_snapshots"):
        row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
        counts[table] = row["c"]
        conn.execute(f"DELETE FROM {table}")
    conn.execute("UPDATE workers SET reported_state='offline'")
    conn.commit()
    return counts