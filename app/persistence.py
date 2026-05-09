"""
JINNI GRID — Database Persistence Layer
app/persistence.py

All raw data storage. Every monetary value rounded to 2 decimals at write time.
Trade UIDs are globally unique (deployment_id + trade_counter).
Timestamps stored as both Unix int AND ISO string for correct date grouping.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

_DB_PATH = None
_local = threading.local()

_DEFAULT_SETTINGS = {
    "refresh_interval": "5",
    "default_symbol": "XAUUSD",
    "default_bar_size": "100",
    "default_lot_size": "0.01",
    "debug_mode": "true",
    "worker_timeout_seconds": "90",
    "log_verbosity": "INFO",
}


# ── Connection ──────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn


def _r2(v):
    if v is None:
        return 0.0
    try:
        return round(float(v), 2)
    except (ValueError, TypeError):
        return 0.0


def _unix_to_iso(ts):
    """Convert Unix timestamp (int/float) to ISO 8601 UTC string."""
    if ts is None:
        return None
    try:
        v = int(ts)
        if v > 946684800:  # after year 2000
            return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        pass
    s = str(ts)
    if "T" in s or (len(s) >= 10 and s[4] == "-"):
        return s
    return None


def _unix_to_date(ts):
    """Convert Unix timestamp to YYYY-MM-DD."""
    if ts is None:
        return None
    try:
        v = int(ts)
        if v > 946684800:
            return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        pass
    s = str(ts)
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    return None


# ── Schema ──────────────────────────────────────────────────

def init_db(db_path: str = "jinni_grid.db"):
    global _DB_PATH
    _DB_PATH = db_path
    conn = _get_conn()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            worker_name TEXT,
            host TEXT,
            state TEXT DEFAULT 'unknown',
            mt5_state TEXT,
            broker TEXT,
            account_id TEXT,
            mt5_server TEXT,
            account_balance REAL DEFAULT 0.0,
            account_equity REAL DEFAULT 0.0,
            agent_version TEXT,
            last_heartbeat_at TEXT,
            data_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS strategies (
            strategy_id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            version TEXT,
            class_name TEXT,
            file_hash TEXT,
            file_content TEXT,
            min_lookback INTEGER DEFAULT 0,
            parameters_json TEXT,
            uploaded_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS deployments (
            deployment_id TEXT PRIMARY KEY,
            strategy_id TEXT,
            worker_id TEXT,
            symbol TEXT,
            state TEXT DEFAULT 'queued',
            tick_lookback_value INTEGER DEFAULT 30,
            tick_lookback_unit TEXT DEFAULT 'minutes',
            bar_size_points REAL DEFAULT 100,
            max_bars_in_memory INTEGER DEFAULT 500,
            lot_size REAL DEFAULT 0.01,
            strategy_parameters_json TEXT,
            last_error TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_uid TEXT UNIQUE,
            trade_id INTEGER,
            deployment_id TEXT,
            strategy_id TEXT,
            worker_id TEXT,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            exit_price REAL,
            entry_time_unix INTEGER,
            exit_time_unix INTEGER,
            entry_time TEXT,
            exit_time TEXT,
            entry_bar INTEGER,
            exit_bar INTEGER,
            bars_held INTEGER DEFAULT 0,
            lot_size REAL,
            ticket INTEGER,
            sl REAL,
            tp REAL,
            profit REAL DEFAULT 0.0,
            commission REAL DEFAULT 0.0,
            swap REAL DEFAULT 0.0,
            exit_reason TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS equity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            worker_id TEXT,
            balance REAL DEFAULT 0.0,
            equity REAL DEFAULT 0.0,
            floating_pnl REAL DEFAULT 0.0,
            open_positions INTEGER DEFAULT 0,
            cumulative_pnl REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            category TEXT,
            event_type TEXT,
            message TEXT,
            level TEXT DEFAULT 'INFO',
            worker_id TEXT,
            strategy_id TEXT,
            deployment_id TEXT,
            symbol TEXT,
            data_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)

    # Indexes
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_trades_worker ON trades(worker_id)",
        "CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id)",
        "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",
        "CREATE INDEX IF NOT EXISTS idx_trades_exit ON trades(exit_time)",
        "CREATE INDEX IF NOT EXISTS idx_trades_uid ON trades(trade_uid)",
        "CREATE INDEX IF NOT EXISTS idx_equity_ts ON equity_snapshots(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_events_cat ON events(category)",
    ]:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass

    # Migrations for older DBs
    _mig = [
        ("workers", "account_balance", "REAL DEFAULT 0.0"),
        ("workers", "account_equity", "REAL DEFAULT 0.0"),
        ("trades", "trade_uid", "TEXT"),
        ("trades", "commission", "REAL DEFAULT 0.0"),
        ("trades", "swap", "REAL DEFAULT 0.0"),
        ("trades", "entry_time", "TEXT"),
        ("trades", "exit_time", "TEXT"),
        ("trades", "entry_time_unix", "INTEGER"),
        ("trades", "exit_time_unix", "INTEGER"),
        ("equity_snapshots", "worker_id", "TEXT"),
    ]
    for table, col, col_type in _mig:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass

    # Seed defaults
    for k, v in _DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    print(f"[DB] Initialized: {db_path}")


# ── Workers ─────────────────────────────────────────────────

def save_worker(worker_id: str, data: dict):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO workers (worker_id, worker_name, host, state, mt5_state,
            broker, account_id, mt5_server, account_balance, account_equity,
            agent_version, last_heartbeat_at, data_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(worker_id) DO UPDATE SET
            worker_name=excluded.worker_name, host=excluded.host,
            state=excluded.state, mt5_state=excluded.mt5_state,
            broker=excluded.broker, account_id=excluded.account_id,
            mt5_server=excluded.mt5_server,
            account_balance=excluded.account_balance,
            account_equity=excluded.account_equity,
            agent_version=excluded.agent_version,
            last_heartbeat_at=excluded.last_heartbeat_at,
            data_json=excluded.data_json,
            updated_at=datetime('now')
    """, (
        worker_id,
        data.get("worker_name"),
        data.get("host"),
        data.get("reported_state", data.get("state", "online")),
        data.get("mt5_state"),
        data.get("broker"),
        data.get("account_id"),
        data.get("mt5_server"),
        _r2(data.get("account_balance")),
        _r2(data.get("account_equity")),
        data.get("agent_version"),
        data.get("last_heartbeat_at"),
        json.dumps({k: v for k, v in data.items()
                     if k not in ("_last_heartbeat_dt",)}, default=str),
    ))
    conn.commit()


def get_all_workers_db() -> list:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM workers ORDER BY worker_id").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # Merge extra data from data_json
        if d.get("data_json"):
            try:
                extra = json.loads(d["data_json"])
                for k, v in extra.items():
                    if k not in d or d[k] is None:
                        d[k] = v
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


def get_worker_db(worker_id: str):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM workers WHERE worker_id=?",
                       (worker_id,)).fetchone()
    return dict(row) if row else None


# ── Strategies ──────────────────────────────────────────────

def save_strategy(strategy_id: str, data: dict):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO strategies (strategy_id, name, description, version,
            class_name, file_hash, file_content, min_lookback, parameters_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(strategy_id) DO UPDATE SET
            name=excluded.name, description=excluded.description,
            version=excluded.version, class_name=excluded.class_name,
            file_hash=excluded.file_hash, file_content=excluded.file_content,
            min_lookback=excluded.min_lookback,
            parameters_json=excluded.parameters_json
    """, (
        strategy_id,
        data.get("name", strategy_id),
        data.get("description", ""),
        data.get("version", "1.0"),
        data.get("class_name", ""),
        data.get("file_hash", ""),
        data.get("file_content", ""),
        data.get("min_lookback", 0),
        json.dumps(data.get("parameters", {})),
    ))
    conn.commit()


def get_all_strategies_db() -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM strategies ORDER BY uploaded_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_strategy_db(strategy_id: str):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM strategies WHERE strategy_id=?",
                       (strategy_id,)).fetchone()
    return dict(row) if row else None


# ── Deployments ─────────────────────────────────────────────

def save_deployment(deployment_id: str, data: dict):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO deployments (deployment_id, strategy_id, worker_id, symbol,
            state, tick_lookback_value, tick_lookback_unit, bar_size_points,
            max_bars_in_memory, lot_size, strategy_parameters_json, last_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(deployment_id) DO UPDATE SET
            state=excluded.state, last_error=excluded.last_error,
            updated_at=datetime('now')
    """, (
        deployment_id,
        data.get("strategy_id"),
        data.get("worker_id"),
        data.get("symbol"),
        data.get("state", "queued"),
        data.get("tick_lookback_value", 30),
        data.get("tick_lookback_unit", "minutes"),
        data.get("bar_size_points", 100),
        data.get("max_bars_in_memory", 500),
        data.get("lot_size", 0.01),
        json.dumps(data.get("strategy_parameters", {})),
        data.get("last_error"),
    ))
    conn.commit()


def get_all_deployments_db() -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM deployments ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_deployment_db(deployment_id: str):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM deployments WHERE deployment_id=?",
                       (deployment_id,)).fetchone()
    return dict(row) if row else None


def update_deployment_state_db(deployment_id: str, state: str,
                                error: str = None):
    conn = _get_conn()
    conn.execute("""
        UPDATE deployments SET state=?, last_error=?, updated_at=datetime('now')
        WHERE deployment_id=?
    """, (state, error, deployment_id))
    conn.commit()


# ── Trades (THE CRITICAL FIX) ──────────────────────────────

def save_trade_db(data: dict) -> bool:
    """
    Save a closed trade. Uses trade_uid for global uniqueness.
    trade_uid = {deployment_id}_{worker_id}_{trade_id}
    This prevents overwrites between deployments.
    """
    conn = _get_conn()

    # Build globally unique trade ID
    dep_id = data.get("deployment_id", "none")
    wk_id = data.get("worker_id", "none")
    t_id = data.get("trade_id", 0)
    trade_uid = f"{dep_id}_{wk_id}_{t_id}"

    # Convert Unix timestamps to ISO strings for date grouping
    entry_ts = data.get("entry_time")
    exit_ts = data.get("exit_time")
    entry_iso = _unix_to_iso(entry_ts)
    exit_iso = _unix_to_iso(exit_ts)

    # Compute bars_held
    bars_held = data.get("bars_held")
    if bars_held is None or bars_held == 0:
        eb = int(data.get("entry_bar", 0) or 0)
        xb = int(data.get("exit_bar", 0) or 0)
        bars_held = max(0, xb - eb)

    try:
        conn.execute("""
            INSERT OR IGNORE INTO trades (
                trade_uid, trade_id, deployment_id, strategy_id, worker_id,
                symbol, direction, entry_price, exit_price,
                entry_time_unix, exit_time_unix, entry_time, exit_time,
                entry_bar, exit_bar, bars_held,
                lot_size, ticket, sl, tp,
                profit, commission, swap, exit_reason
            ) VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?, ?,?,?,?, ?,?,?,?)
        """, (
            trade_uid,
            t_id,
            dep_id,
            data.get("strategy_id"),
            wk_id,
            data.get("symbol"),
            data.get("direction"),
            _r2(data.get("entry_price")),
            _r2(data.get("exit_price")),
            int(entry_ts) if entry_ts and str(entry_ts).isdigit() else None,
            int(exit_ts) if exit_ts and str(exit_ts).isdigit() else None,
            entry_iso,
            exit_iso,
            data.get("entry_bar"),
            data.get("exit_bar"),
            bars_held,
            data.get("lot_size"),
            data.get("ticket"),
            data.get("sl"),
            data.get("tp"),
            _r2(data.get("profit")),
            _r2(data.get("commission")),
            _r2(data.get("swap")),
            data.get("exit_reason"),
        ))
        conn.commit()
        inserted = conn.execute(
            "SELECT changes()").fetchone()[0]
        if inserted == 0:
            print(f"[DB] Trade {trade_uid} already exists (skipped duplicate)")
        else:
            print(f"[DB] Trade {trade_uid} saved: profit={_r2(data.get('profit'))}")
        return True
    except Exception as e:
        print(f"[DB] save_trade_db FAILED: {e}")
        return False


def get_all_trades_db(limit: int = 10000, strategy_id: str = None,
                       worker_id: str = None, symbol: str = None) -> list:
    conn = _get_conn()
    query = "SELECT * FROM trades"
    params = []
    wheres = []
    if strategy_id:
        wheres.append("strategy_id = ?")
        params.append(strategy_id)
    if worker_id:
        wheres.append("worker_id = ?")
        params.append(worker_id)
    if symbol:
        wheres.append("symbol = ?")
        params.append(symbol)
    if wheres:
        query += " WHERE " + " AND ".join(wheres)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # Ensure exit_time is always an ISO string for portfolio computation
        if not d.get("exit_time") and d.get("exit_time_unix"):
            d["exit_time"] = _unix_to_iso(d["exit_time_unix"])
        if not d.get("entry_time") and d.get("entry_time_unix"):
            d["entry_time"] = _unix_to_iso(d["entry_time_unix"])
        result.append(d)
    return result


# ── Equity Snapshots ────────────────────────────────────────

def save_equity_snapshot_db(balance: float = 0, equity: float = 0,
                             floating_pnl: float = 0, open_positions: int = 0,
                             cumulative_pnl: float = 0,
                             worker_id: str = None):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO equity_snapshots (timestamp, worker_id, balance, equity,
            floating_pnl, open_positions, cumulative_pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (now, worker_id, _r2(balance), _r2(equity),
          _r2(floating_pnl), open_positions, _r2(cumulative_pnl)))
    conn.commit()


def get_equity_snapshots_db(limit: int = 2000,
                             worker_id: str = None) -> list:
    conn = _get_conn()
    if worker_id:
        rows = conn.execute(
            "SELECT * FROM equity_snapshots WHERE worker_id=? "
            "ORDER BY id DESC LIMIT ?", (worker_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM equity_snapshots ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    result = [dict(r) for r in rows]
    result.reverse()
    return result


def clear_equity_snapshots_db():
    conn = _get_conn()
    conn.execute("DELETE FROM equity_snapshots")
    conn.commit()


# ── Events ──────────────────────────────────────────────────

def log_event_db(category: str, event_type: str, message: str,
                  worker_id: str = None, strategy_id: str = None,
                  deployment_id: str = None, symbol: str = None,
                  data: dict = None, level: str = "INFO"):
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()
    data_json = json.dumps(data, default=str) if data else None
    try:
        conn.execute("""
            INSERT INTO events (timestamp, category, event_type, message, level,
                worker_id, strategy_id, deployment_id, symbol, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now, category, event_type, message, level,
              worker_id, strategy_id, deployment_id, symbol, data_json))
        conn.commit()
    except Exception as e:
        print(f"[DB] log_event error: {e}")


def get_events_db(limit: int = 200, category: str = None,
                   worker_id: str = None,
                   deployment_id: str = None) -> list:
    conn = _get_conn()
    query = "SELECT * FROM events"
    params = []
    wheres = []
    if category:
        wheres.append("category = ?")
        params.append(category)
    if worker_id:
        wheres.append("worker_id = ?")
        params.append(worker_id)
    if deployment_id:
        wheres.append("deployment_id = ?")
        params.append(deployment_id)
    if wheres:
        query += " WHERE " + " AND ".join(wheres)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Settings ────────────────────────────────────────────────

def get_setting(key: str):
    conn = _get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?",
                       (key,)).fetchone()
    return row[0] if row else None


def get_all_settings() -> dict:
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r[0]: r[1] for r in rows}


def save_setting(key: str, value: str):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()


def save_settings_bulk(settings: dict):
    conn = _get_conn()
    for k, v in settings.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (k, str(v))
        )
    conn.commit()


# ── Admin / Delete ──────────────────────────────────────────

def delete_all_trades_db() -> int:
    conn = _get_conn()
    c = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.execute("DELETE FROM trades")
    conn.commit()
    return c


def delete_trades_by_strategy_db(strategy_id: str) -> int:
    conn = _get_conn()
    c = conn.execute("SELECT COUNT(*) FROM trades WHERE strategy_id=?",
                     (strategy_id,)).fetchone()[0]
    conn.execute("DELETE FROM trades WHERE strategy_id=?", (strategy_id,))
    conn.commit()
    return c


def delete_trades_by_worker_db(worker_id: str) -> int:
    conn = _get_conn()
    c = conn.execute("SELECT COUNT(*) FROM trades WHERE worker_id=?",
                     (worker_id,)).fetchone()[0]
    conn.execute("DELETE FROM trades WHERE worker_id=?", (worker_id,))
    conn.commit()
    return c


def delete_strategy_full_db(strategy_id: str) -> dict:
    conn = _get_conn()
    dep_c = conn.execute(
        "SELECT COUNT(*) FROM deployments WHERE strategy_id=?",
        (strategy_id,)
    ).fetchone()[0]
    conn.execute("DELETE FROM deployments WHERE strategy_id=?",
                 (strategy_id,))
    trade_c = conn.execute(
        "SELECT COUNT(*) FROM trades WHERE strategy_id=?",
        (strategy_id,)
    ).fetchone()[0]
    conn.execute("DELETE FROM trades WHERE strategy_id=?", (strategy_id,))
    conn.execute("DELETE FROM strategies WHERE strategy_id=?",
                 (strategy_id,))
    conn.commit()
    # Delete files
    try:
        import glob
        for p in glob.glob(f"strategies/*{strategy_id}*"):
            os.remove(p)
    except Exception:
        pass
    return {"ok": True, "strategy_id": strategy_id,
            "deployments_deleted": dep_c, "trades_deleted": trade_c}


def remove_worker_db(worker_id: str) -> dict:
    conn = _get_conn()
    conn.execute("DELETE FROM workers WHERE worker_id=?", (worker_id,))
    conn.commit()
    return {"ok": True, "worker_id": worker_id}


def remove_stale_workers_db(threshold_seconds: int = 300) -> int:
    conn = _get_conn()
    cutoff = datetime.now(timezone.utc)
    rows = conn.execute("SELECT worker_id, last_heartbeat_at FROM workers"
                        ).fetchall()
    removed = 0
    for r in rows:
        hb = r[1]
        if not hb:
            continue
        try:
            last = datetime.fromisoformat(hb)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (cutoff - last).total_seconds() > threshold_seconds:
                conn.execute("DELETE FROM workers WHERE worker_id=?",
                             (r[0],))
                removed += 1
        except (ValueError, TypeError):
            pass
    conn.commit()
    return removed


def clear_events_db() -> int:
    conn = _get_conn()
    c = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.execute("DELETE FROM events")
    conn.commit()
    return c


def get_system_stats_db() -> dict:
    conn = _get_conn()
    stats = {}
    for table in ["strategies", "workers", "deployments", "trades",
                   "events", "equity_snapshots", "settings"]:
        try:
            c = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[f"{table}_count"] = c
        except Exception:
            stats[f"{table}_count"] = 0
    # Active deployments
    try:
        stats["active_deployments"] = conn.execute(
            "SELECT COUNT(*) FROM deployments WHERE state='running'"
        ).fetchone()[0]
    except Exception:
        stats["active_deployments"] = 0
    # DB size
    try:
        stats["db_size_bytes"] = os.path.getsize(_DB_PATH)
    except Exception:
        stats["db_size_bytes"] = 0
    return stats


def full_system_reset_db() -> dict:
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
    conn.commit()
    try:
        import glob
        for p in glob.glob("strategies/*.py"):
            os.remove(p)
    except Exception:
        pass
    return counts