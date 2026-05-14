# Repository Snapshot - Part 4 of 4

- Total files indexed: `27`
- Files in this chunk: `7`
## Full Project Tree

```text
app/__init__.py
app/config.py
app/logging_config.py
app/persistence.py
app/routes/__init__.py
app/routes/mainRoutes.py
app/services/__init__.py
app/services/mainServices.py
app/services/strategy_registry.py
config.yaml
main.py
README.md
requirements.txt
ui/css/style.css
ui/index.html
ui/js/main.js
ui/js/workerDetailRenderer.js
vm/config.yaml
vm/core/strategy_worker.py
vm/logging/event_log.py
vm/README.md
vm/requirements.txt
vm/trading/execution.py
vm/trading/indicators.py
vm/trading/mt5_history.py
vm/trading/portfolio.py
vm/worker_agent.py
```

## Files In This Chunk - Part 4

```text
app/persistence.py
ui/js/workerDetailRenderer.js
vm/logging/event_log.py
vm/README.md
vm/trading/indicators.py
vm/trading/mt5_history.py
vm/trading/portfolio.py
```

## File Contents


---

## FILE: `app/persistence.py`

- Relative path: `app/persistence.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/persistence.py`
- Size bytes: `27118`
- SHA256: `ed250499267854275500277608cdb27b74558fdd6cfb86640801e4879b19c8ca`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
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
        "CREATE INDEX IF NOT EXISTS idx_trades_ticket ON trades(ticket)",
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
    Save a closed trade. Uses MT5 position ticket as the unique ID
    (globally unique per MT5 account, never reused).

    Uniqueness: trade_uid = {worker_id}_{mt5_ticket}
    Fallback:   trade_uid = {deployment_id}_{worker_id}_{trade_id}_{exit_time}
    """
    conn = _get_conn()

    # Build globally unique trade ID
    mt5_ticket = data.get("mt5_ticket") or data.get("ticket")
    wk_id = data.get("worker_id", "none")
    dep_id = data.get("deployment_id", "none")
    t_id = data.get("trade_id", 0)
    exit_ts = data.get("exit_time", "0")

    if mt5_ticket:
        # Best case: MT5 ticket is globally unique per account
        trade_uid = f"{wk_id}_{mt5_ticket}"
    else:
        # Fallback: include exit_time to prevent restart collisions
        trade_uid = f"{dep_id}_{wk_id}_{t_id}_{exit_ts}"

    # Convert timestamps
    entry_ts = data.get("entry_time")
    exit_ts_raw = data.get("exit_time")
    entry_iso = _unix_to_iso(entry_ts)
    exit_iso = _unix_to_iso(exit_ts_raw)

    # Bars held
    bars_held = data.get("bars_held")
    if bars_held is None or bars_held == 0:
        eb = int(data.get("entry_bar", 0) or 0)
        xb = int(data.get("exit_bar", 0) or 0)
        bars_held = max(0, xb - eb)

    # Use net_pnl if available (MT5 source), else fall back to profit
    profit = data.get("net_pnl") or data.get("profit") or 0

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
            int(exit_ts_raw) if exit_ts_raw and str(exit_ts_raw).isdigit() else None,
            entry_iso,
            exit_iso,
            data.get("entry_bar"),
            data.get("exit_bar"),
            bars_held,
            data.get("lot_size"),
            mt5_ticket or data.get("ticket"),
            data.get("sl"),
            data.get("tp"),
            _r2(profit),
            _r2(data.get("commission")),
            _r2(data.get("swap")),
            data.get("exit_reason"),
        ))
        conn.commit()
        changes = conn.execute("SELECT changes()").fetchone()[0]
        if changes == 0:
            print(f"[DB] Trade {trade_uid} already exists (skipped duplicate)")
        else:
            src = "MT5" if data.get("mt5_source") else "EST"
            print(f"[DB] Trade SAVED [{src}]: uid={trade_uid} "
                  f"{data.get('direction','')} {data.get('symbol','')} "
                  f"profit={_r2(profit)} reason={data.get('exit_reason','')}")
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
```

---

## FILE: `ui/js/workerDetailRenderer.js`

- Relative path: `ui/js/workerDetailRenderer.js`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/js/workerDetailRenderer.js`
- Size bytes: `41768`
- SHA256: `08588cb5c5cb16d35d9d08077ad0980f2e922f904e9d74508f16b8d9885db6d4`
- Guessed MIME type: `text/javascript`
- Guessed encoding: `unknown`

```javascript
/* workerDetailRenderer.js */

var WorkerDetailRenderer = (function () {
  'use strict';

  var _currentWorker = null;
  var _refreshInterval = null;
  var _runtimeConfig = {};
  var _parameterValues = {};
  var _parameterDefaults = {};
  var _activityLog = [];

  // Backend-loaded data
  var _strategies = [];
  var _selectedStrategyId = null;
  var _selectedStrategy = null;
  var _deployments = [];

  /* ── Helpers ──────────────────────────────────────────────── */

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">\u2014</span>';
    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '')
      return '<span class="value-null">' + (fallback || '\u2014') + '</span>';
    return String(val);
  }

  function _stateColor(state) {
    var map = { online: 'green', running: 'green', idle: 'blue', warning: 'amber', stale: 'orange', error: 'red', offline: 'gray' };
    return map[state] || 'gray';
  }

  function _stateLabel(state) {
    if (!state) return 'Unknown';
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

  function _formatPnl(val) {
    if (val === null || val === undefined) return '<span class="value-null">\u2014</span>';
    var sign = val >= 0 ? '+' : '';
    return sign + '$' + val.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function _timeNow() {
    var d = new Date();
    return String(d.getHours()).padStart(2, '0') + ':' +
           String(d.getMinutes()).padStart(2, '0') + ':' +
           String(d.getSeconds()).padStart(2, '0');
  }

  function _getModifiedCount() {
    var count = 0;
    for (var k in _parameterValues) {
      if (_parameterValues[k] !== _parameterDefaults[k]) count++;
    }
    return count;
  }

  function _deployStateClass(state) {
    if (!state) return 'unknown';
    if (state === 'running') return 'online';
    if (state === 'failed') return 'error';
    if (state === 'stopped') return 'offline';
    if (state.indexOf('loading') !== -1 || state.indexOf('fetching') !== -1 ||
        state.indexOf('generating') !== -1 || state.indexOf('warming') !== -1) return 'warning';
    return 'stale';
  }

  /* ── State Init ──────────────────────────────────────────── */

  function _initState() {
    _activityLog = [];
    _strategies = [];
    _selectedStrategyId = null;
    _selectedStrategy = null;
    _deployments = [];

    var defaults = DeploymentConfig.runtimeDefaults;
    _runtimeConfig = {};
    for (var k in defaults) _runtimeConfig[k] = defaults[k];

    _parameterValues = {};
    _parameterDefaults = {};
  }

  /* ── Activity Log ────────────────────────────────────────── */

  function _addActivity(text) {
    _activityLog.unshift({ time: _timeNow(), text: text });
    if (_activityLog.length > 30) _activityLog.length = 30;
    _renderTimeline();
  }

  function _renderTimeline() {
    var el = document.getElementById('wd-timeline');
    if (!el) return;
    if (_activityLog.length === 0) {
      el.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No activity yet.</div>';
      return;
    }
    var html = '';
    _activityLog.forEach(function (entry) {
      html += '<div class="wd-timeline-item">' +
        '<span class="wd-timeline-time">' + entry.time + '</span>' +
        '<span class="wd-timeline-dot"></span>' +
        '<span class="wd-timeline-text">' + entry.text + '</span></div>';
    });
    el.innerHTML = html;
  }

  /* ── Status Cards ────────────────────────────────────────── */

  function _renderStatusCards() {
    var w = _currentWorker;
    var state = w.state || 'unknown';
    var strats = (w.active_strategies && w.active_strategies.length > 0)
      ? w.active_strategies.join(', ') : 'None';

    /* ── MT5 info ────────────────────────────────────── */
    var mt5Val = _nullVal(w.mt5_state, 'Not Connected');
    var mt5Color = '';
    if (w.mt5_state === 'connected') {
      mt5Val = '<span style="color:var(--success);">Connected</span>';
    } else if (w.mt5_state === 'disconnected') {
      mt5Val = '<span style="color:var(--danger);">Disconnected</span>';
    }

    var brokerAcct = '';
    if (w.broker || w.account_id) {
      brokerAcct = (w.broker || '?') + ' / ' + (w.account_id || '?');
    } else {
      brokerAcct = '<span class="value-null">\u2014</span>';
    }

    /* ── Pipeline stats ──────────────────────────────── */
    var ticks = w.total_ticks || 0;
    var bars = w.total_bars || 0;
    var signals = w.signal_count || 0;
    var onBarCalls = w.on_bar_calls || 0;

    var barsInMem = w.current_bars_in_memory || 0;
    var barsText = _fmtNum(bars) + ' gen\u2019d' + (barsInMem > 0 ? ' (' + barsInMem + ' mem)' : '');
    var pipelineVal =
      '<span style="color:var(--accent);">' + _fmtNum(ticks) + '</span> ticks \u2192 ' +
      '<span style="color:var(--warning);">' + barsText + '</span> bars \u2192 ' +
      '<span style="color:var(--success);">' + signals + '</span> signals';

    /* ── Current price ───────────────────────────────── */
    var priceVal = (w.current_price !== null && w.current_price !== undefined)
      ? '<span class="mono">' + w.current_price.toFixed(2) + '</span>'
      : '<span class="value-null">\u2014</span>';

    /* ── PnL ─────────────────────────────────────────── */
    var pnl = _formatPnl(w.floating_pnl);
    var pnlStyle = '';
    if (w.floating_pnl !== null && w.floating_pnl !== undefined) {
      pnlStyle = w.floating_pnl >= 0 ? 'color:var(--success)' : 'color:var(--danger)';
    }

    var cards = [
      { label: 'Connection',       value: '<div class="status-indicator"><span class="wd-status-dot-sm ' + _stateColor(state) + '"></span>' + _stateLabel(state) + '</div>' },
      { label: 'MT5',              value: mt5Val },
      { label: 'Broker / Account', value: brokerAcct },
      { label: 'Active Strategy',  value: strats },
      { label: 'Pipeline',         value: pipelineVal },
      { label: 'Current Price',    value: priceVal },
      { label: 'Equity',           value: '<span style="' + pnlStyle + '">' + pnl + '</span>' },
      { label: 'Last Heartbeat',   value: _formatAge(w.heartbeat_age_seconds) },
    ];

    var html = '';
    cards.forEach(function (c) {
      html += '<div class="wd-status-card"><span class="status-label">' + c.label + '</span><span class="status-value">' + c.value + '</span></div>';
    });
    return html;
  }

  function _fmtNum(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }

  /* ── Checklist ───────────────────────────────────────────── */

  function _renderChecklist() {
    var w = _currentWorker;
    var onlineStates = ['online', 'running', 'idle'];
    var isOnline = onlineStates.indexOf(w.state) !== -1;
    var hasSid = !!_selectedStrategyId;
    var hasSym = !!_runtimeConfig.symbol && /^[A-Z0-9._]{1,30}$/.test((_runtimeConfig.symbol || '').trim().toUpperCase());
    var tlOk = _runtimeConfig.tick_lookback_value > 0;
    var bsOk = _runtimeConfig.bar_size_points > 0;
    var mbOk = _runtimeConfig.max_bars_memory > 0;

    var items = [
      { pass: isOnline, text: 'Worker connected', type: isOnline ? 'pass' : 'fail' },
      { pass: hasSid, text: 'Strategy selected' + (hasSid ? ' (' + _selectedStrategyId + ')' : ''), type: hasSid ? 'pass' : 'fail' },
      { pass: hasSym, text: 'Symbol selected', type: hasSym ? 'pass' : 'fail' },
      { pass: tlOk, text: 'Tick lookback configured', type: tlOk ? 'pass' : 'fail' },
      { pass: bsOk, text: 'Bar size points configured', type: bsOk ? 'pass' : 'fail' },
      { pass: mbOk, text: 'Max bars memory configured', type: mbOk ? 'pass' : 'fail' },
      { pass: true, text: 'Parameters configured', type: 'pass' },
    ];

    var iconMap = { pass: 'fa-check', fail: 'fa-xmark', warn: 'fa-exclamation', info: 'fa-info' };
    var html = '';
    items.forEach(function (item) {
      var textClass = item.type === 'pass' ? 'wd-check-text pass' : 'wd-check-text';
      html += '<div class="wd-check-item">' +
        '<span class="wd-check-icon ' + item.type + '"><i class="fa-solid ' + iconMap[item.type] + '"></i></span>' +
        '<span class="' + textClass + '">' + item.text + '</span></div>';
    });
    return html;
  }

  function _updateChecklist() {
    var el = document.getElementById('wd-checklist');
    if (el) el.innerHTML = _renderChecklist();
  }

  /* ── Build Strategy Selector ─────────────────────────────── */

  function _renderStrategySelector() {
    if (_strategies.length === 0) {
      return '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">' +
        '<i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>' +
        'No strategies registered. Go to Strategies page to upload one.</div>';
    }

    var html = '<div class="wd-form-grid" style="grid-template-columns:1fr;">' +
      '<div class="wd-form-group"><label class="wd-form-label">Select Strategy</label>' +
      '<select class="wd-form-select" id="wd-strategy-select">';
    html += '<option value="">-- Choose a strategy --</option>';
    _strategies.forEach(function (s) {
      var disabled = s.validation_status !== 'validated' ? ' disabled' : '';
      var label = (s.strategy_name || s.strategy_id) + ' v' + (s.version || '?');
      if (s.validation_status !== 'validated') label += ' (invalid)';
      var selected = (_selectedStrategyId === s.strategy_id) ? ' selected' : '';
      html += '<option value="' + s.strategy_id + '"' + disabled + selected + '>' + label + '</option>';
    });
    html += '</select></div></div>';

    // Metadata preview
    html += '<div id="wd-strat-meta"></div>';
    return html;
  }

  function _renderStrategyMeta() {
    var el = document.getElementById('wd-strat-meta');
    if (!el) return;
    if (!_selectedStrategy) { el.innerHTML = ''; return; }

    var s = _selectedStrategy;
    el.innerHTML = '<div class="wd-metadata" style="margin-top:12px;"><div class="wd-metadata-grid">' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">ID</span><span class="wd-metadata-value">' + s.strategy_id + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Name</span><span class="wd-metadata-value">' + (s.strategy_name || s.strategy_id) + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Version</span><span class="wd-metadata-value">' + (s.version || '\u2014') + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Parameters</span><span class="wd-metadata-value">' + (s.parameter_count || 0) + '</span></div>' +
      (s.description ? '<div class="wd-metadata-item" style="grid-column:1/-1;"><span class="wd-metadata-label">Description</span><span class="wd-metadata-value" style="font-family:Inter,sans-serif;">' + s.description + '</span></div>' : '') +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Status</span><span class="wd-metadata-value" style="color:var(--success);">' + (s.validation_status || 'unknown') + '</span></div>' +
      '</div></div>';
  }

  /* ── Build Strategy Parameters ───────────────────────────── */

  function _renderParams() {
    if (!_selectedStrategy || !_selectedStrategy.parameters ||
        Object.keys(_selectedStrategy.parameters).length === 0) {
      return '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">' +
        'No editable parameters exposed by this strategy.</div>';
    }

    var schema = _selectedStrategy.parameters;
    var html = '';

    Object.keys(schema).forEach(function (key) {
      var spec = schema[key];
      if (typeof spec !== 'object') return;

      var ptype = spec.type || 'number';
      var label = spec.label || key;
      var desc = spec.help || '';
      var defVal = spec.default !== undefined ? spec.default : '';
      var val = _parameterValues.hasOwnProperty(key) ? _parameterValues[key] : defVal;
      var isModified = val !== defVal;
      var modClass = isModified ? ' modified' : '';
      var typeBadge = ptype === 'boolean' ? 'bool' : (ptype === 'number' ? (String(defVal).indexOf('.') !== -1 ? 'float' : 'int') : 'string');
      var input = '';

      if (ptype === 'boolean') {
        input = '<input type="checkbox" class="wd-toggle wd-param-input-ctrl" data-key="' + key + '"' +
          (val ? ' checked' : '') + ' />';
      } else if (ptype === 'select' && spec.options) {
        input = '<select class="wd-param-input wd-param-input-ctrl" data-key="' + key + '" style="width:120px;text-align:left;">';
        spec.options.forEach(function (opt) {
          var optVal = typeof opt === 'object' ? opt.value : opt;
          var optLabel = typeof opt === 'object' ? (opt.label || opt.value) : opt;
          input += '<option value="' + optVal + '"' + (String(optVal) === String(val) ? ' selected' : '') + '>' + optLabel + '</option>';
        });
        input += '</select>';
      } else if (ptype === 'string' || ptype === 'text') {
        input = '<input type="text" class="wd-param-input wd-param-input-ctrl" data-key="' + key + '" value="' + (val || '') + '" style="width:120px;text-align:left;" />';
      } else {
        var attrs = 'type="number" class="wd-param-input wd-param-input-ctrl" data-key="' + key + '" value="' + val + '"';
        if (spec.min !== undefined && spec.min !== null) attrs += ' min="' + spec.min + '"';
        if (spec.max !== undefined && spec.max !== null) attrs += ' max="' + spec.max + '"';
        if (spec.step !== undefined && spec.step !== null) attrs += ' step="' + spec.step + '"';
        input = '<input ' + attrs + ' />';
      }

      html += '<div class="wd-param-row' + modClass + '" data-key="' + key + '">' +
        '<div class="wd-param-info">' +
          '<div class="wd-param-name">' + label +
            '<span class="wd-param-type-badge type-' + typeBadge + '">' + typeBadge + '</span></div>' +
          '<div class="wd-param-desc">' + desc + '</div>' +
        '</div>' +
        '<div class="wd-param-controls">' +
          input +
          '<button class="wd-param-reset" data-key="' + key + '" title="Reset to default"><i class="fa-solid fa-rotate-left"></i></button>' +
        '</div></div>';
    });

    return html;
  }

  /* ── Build Runtime Config ────────────────────────────────── */

  function _renderRuntimeConfig() {
    var rc = _runtimeConfig;
    var tlUnits = DeploymentConfig.tickLookbackUnits;

    var tlUnitOpts = tlUnits.map(function (u) {
      var label = u.charAt(0).toUpperCase() + u.slice(1);
      return '<option value="' + u + '"' + (rc.tick_lookback_unit === u ? ' selected' : '') + '>' + label + '</option>';
    }).join('');

    return '<div class="wd-form-grid">' +

      /* ── Symbol (free-text input) ─────────────────────── */
      '<div class="wd-form-group">' +
        '<label class="wd-form-label">Symbol</label>' +
        '<input type="text" class="wd-form-input rc-input" id="wd-symbol-input" data-key="symbol"' +
          ' value="' + (rc.symbol || '') + '" placeholder="e.g. EURUSD, XAUUSD, BTCUSD"' +
          ' autocomplete="off" spellcheck="false" />' +
        '<div class="wd-symbol-hint">Letters, numbers, dots, underscores only — auto-uppercased</div>' +
        '<div class="wd-field-error" id="wd-symbol-error"><i class="fa-solid fa-circle-xmark"></i><span></span></div>' +
      '</div>' +

      /* ── Lot Size ─────────────────────────────────────── */
      '<div class="wd-form-group">' +
        '<label class="wd-form-label">Lot Size</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="lot_size" value="' + rc.lot_size + '" step="0.01" min="0.01" />' +
      '</div>' +

      /* ── History Lookback (merged value + unit) ───────── */
      '<div class="wd-form-group" style="grid-column:1/-1;">' +
        '<label class="wd-form-label">History Lookback</label>' +
        '<div class="wd-inline-row">' +
          '<input type="number" class="wd-form-input rc-input" data-key="tick_lookback_value" value="' + rc.tick_lookback_value + '" step="1" min="1" placeholder="Amount" />' +
          '<select class="wd-form-select rc-input" data-key="tick_lookback_unit">' + tlUnitOpts + '</select>' +
        '</div>' +
      '</div>' +

      /* ── Bar Size Points ──────────────────────────────── */
      '<div class="wd-form-group">' +
        '<label class="wd-form-label">Bar Size Points</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="bar_size_points" value="' + rc.bar_size_points + '" step="1" min="1" />' +
      '</div>' +

      /* ── Max Bars in Memory ───────────────────────────── */
      '<div class="wd-form-group">' +
        '<label class="wd-form-label">Max Bars in Memory</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="max_bars_memory" value="' + rc.max_bars_memory + '" step="10" min="10" />' +
      '</div>' +

    '</div>';
  }

  /* ── Deployments Panel ───────────────────────────────────── */

  function _renderDeployments() {
    if (_deployments.length === 0) {
      return '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">' +
        'No deployments for this worker.</div>';
    }

    var html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    _deployments.forEach(function (d) {
      var stateClass = _deployStateClass(d.state);
      var updated = d.updated_at ? d.updated_at.replace('T', ' ').substring(0, 19) : '\u2014';
      html += '<div style="background:var(--bg-secondary);border-radius:6px;padding:10px 14px;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;">' +
          '<span class="mono" style="font-size:12px;color:var(--accent);">' + d.deployment_id + '</span>' +
          '<span class="state-pill ' + stateClass + '">' + d.state.toUpperCase().replace(/_/g, ' ') + '</span>' +
        '</div>' +
        '<div style="display:flex;gap:16px;margin-top:6px;font-size:11px;color:var(--text-muted);">' +
          '<span>Strategy: <strong class="mono">' + (d.strategy_name || d.strategy_id) + '</strong></span>' +
          '<span>Symbol: <strong class="mono">' + d.symbol + '</strong></span>' +
          '<span>Bars: <strong class="mono">' + d.bar_size_points + 'pt / ' + d.max_bars_in_memory + '</strong></span>' +
        '</div>' +
        '<div style="display:flex;gap:16px;margin-top:4px;font-size:10.5px;color:var(--text-muted);">' +
          '<span>Updated: ' + updated + '</span>' +
          (d.last_error ? '<span style="color:var(--danger);">Error: ' + d.last_error + '</span>' : '') +
        '</div>';

      // Stop button for active deployments
      var activeStates = ['queued','sent_to_worker','acknowledged_by_worker','loading_strategy','fetching_ticks','generating_initial_bars','warming_up','running'];
      if (activeStates.indexOf(d.state) !== -1) {
        html += '<button class="wd-btn wd-btn-ghost dep-stop-btn" data-depid="' + d.deployment_id + '" style="margin-top:8px;font-size:10.5px;">' +
          '<i class="fa-solid fa-stop"></i> Stop</button>';
      }
      html += '</div>';
    });
    html += '</div>';
    return html;
  }

  /* ── Build Full Page ─────────────────────────────────────── */

  function _buildPage() {
    var w = _currentWorker;
    var state = w.state || 'unknown';
    var name = w.worker_name || w.worker_id;
    var ip = w.host || '\u2014';

    var html = '<div class="worker-detail">';

    // Header
    html += '<div class="wd-header">' +
      '<div class="wd-header-left">' +
        '<button class="wd-back-btn" id="wd-back-btn"><i class="fa-solid fa-arrow-left"></i> Back to Fleet</button>' +
        '<div class="wd-header-info">' +
          '<h2>' + name + '</h2>' +
          '<div class="wd-header-meta">' +
            '<span>' + w.worker_id + '</span><span class="meta-sep">\u00B7</span>' +
            '<span>' + ip + '</span>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="wd-header-right">' +
        '<span class="state-pill ' + state + '" id="wd-state-pill">' + _stateLabel(state) + '</span>' +
        '<button class="wd-refresh-btn" id="wd-refresh-btn"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button>' +
        '<button class="wd-emergency-btn" id="wd-emergency-btn"><i class="fa-solid fa-circle-stop"></i> Emergency Stop</button>' +
      '</div></div>';

    // Status Cards
    html += '<div class="wd-status-grid" id="wd-status-grid">' + _renderStatusCards() + '</div>';

    // Content
    html += '<div class="wd-content">';

    // Main Column
    html += '<div class="wd-main-col">';

    // Strategy Selector
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Strategy Selection<span class="panel-badge">BACKEND</span></div>' +
      '<div class="wd-panel-body" id="wd-strat-selector-body">' +
        '<div class="loading-state" style="min-height:60px;"><div class="spinner"></div><p>Loading strategies\u2026</p></div>' +
      '</div></div>';

    // Runtime Config
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Runtime Configuration</div>' +
      '<div class="wd-panel-body" id="wd-runtime-body">' + _renderRuntimeConfig() + '</div></div>';

    // Strategy Parameters
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Strategy Parameters<span class="panel-badge" id="wd-param-count">0 PARAMS</span></div>' +
      '<div class="wd-panel-body"><div class="wd-params-list" id="wd-params-list">' +
        '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">Select a strategy to see parameters.</div>' +
      '</div></div></div>';

    html += '</div>'; // main-col

    // Side Column
    html += '<div class="wd-side-col">';

    // Deployment Readiness
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Deployment Readiness</div>' +
      '<div class="wd-panel-body"><div class="wd-checklist" id="wd-checklist">' + _renderChecklist() + '</div></div></div>';

    // Deployments
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Deployments<span class="panel-badge" id="wd-dep-count">0</span></div>' +
      '<div class="wd-panel-body" id="wd-deployments-body">' +
        '<div class="loading-state" style="min-height:60px;"><div class="spinner"></div><p>Loading\u2026</p></div>' +
      '</div></div>';

    // Activity Timeline
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Activity<span class="panel-badge mock">LOCAL UI</span></div>' +
      '<div class="wd-panel-body"><div class="wd-timeline" id="wd-timeline"></div></div></div>';

    html += '</div>'; // side-col
    html += '</div>'; // wd-content

    // Action Bar
    html += '<div class="wd-panel">' +
      '<div class="wd-action-bar">' +
        '<div class="wd-action-bar-left">' +
          '<button class="wd-btn wd-btn-ghost" id="wd-reset-changes"><i class="fa-solid fa-rotate-left"></i> Reset</button>' +
        '</div>' +
        '<div class="wd-action-bar-right">' +
          '<button class="wd-btn wd-btn-primary deploy" id="wd-deploy"><i class="fa-solid fa-rocket"></i> Deploy to Worker</button>' +
        '</div>' +
      '</div></div>';

    html += '</div>'; // worker-detail
    return html;
  }

  /* ── Attach Events ───────────────────────────────────────── */

  function _attachEvents() {
    document.getElementById('wd-back-btn').addEventListener('click', function () {
      App.navigateTo('fleet');
    });

    document.getElementById('wd-refresh-btn').addEventListener('click', function () {
      _refreshAll();
      _addActivity('Refreshed');
    });

    document.getElementById('wd-emergency-btn').addEventListener('click', function () {
      ModalManager.show({
        title: 'Emergency Stop',
        type: 'danger',
        bodyHtml: '<p>This will send stop commands for all active deployments on this worker.</p>' +
          '<div class="modal-warning"><i class="fa-solid fa-triangle-exclamation"></i>' +
          '<span>All open positions will remain unmanaged. Use with extreme caution.</span></div>',
        confirmText: 'Stop All',
        onConfirm: function () {
          _deployments.forEach(function (d) {
            var activeStates = ['queued','sent_to_worker','acknowledged_by_worker','loading_strategy','fetching_ticks','generating_initial_bars','warming_up','running'];
            if (activeStates.indexOf(d.state) !== -1) {
              ApiClient.stopDeployment(d.deployment_id).catch(function () {});
            }
          });
          ToastManager.show('Emergency stop sent.', 'warning');
          _addActivity('Emergency stop sent');
          setTimeout(_fetchDeployments, 2000);
        }
      });
    });

    _attachRuntimeEvents();

    document.getElementById('wd-deploy').addEventListener('click', _handleDeploy);

    document.getElementById('wd-reset-changes').addEventListener('click', function () {
      var defaults = DeploymentConfig.runtimeDefaults;
      _runtimeConfig = {};
      for (var k in defaults) _runtimeConfig[k] = defaults[k];
      document.getElementById('wd-runtime-body').innerHTML = _renderRuntimeConfig();
      _attachRuntimeEvents();
      _selectedStrategyId = null;
      _selectedStrategy = null;
      _parameterValues = {};
      _parameterDefaults = {};
      _loadStrategies();
      _updateChecklist();
      ToastManager.show('Reset to defaults.', 'info');
      _addActivity('Reset to defaults');
    });
  }

  function _attachRuntimeEvents() {
    document.querySelectorAll('.rc-input').forEach(function (input) {
      var key = input.getAttribute('data-key');

      /* ── Symbol gets special handling ──────────────── */
      if (key === 'symbol') {
        input.addEventListener('input', function () {
          input.value = input.value.toUpperCase().replace(/\s/g, '');
          _runtimeConfig.symbol = input.value;
          _validateSymbolInput();
          _updateChecklist();
        });
        input.addEventListener('blur', function () {
          input.value = input.value.trim().toUpperCase();
          _runtimeConfig.symbol = input.value;
          _validateSymbolInput();
          _updateChecklist();
        });
        return;
      }

      /* ── All other inputs ──────────────────────────── */
      input.addEventListener('change', function () {
        _runtimeConfig[key] = input.type === 'number' ? parseFloat(input.value) : input.value;
        _updateChecklist();
        _addActivity('Config: ' + key + ' updated');
      });
    });
  }

  function _validateSymbolInput() {
    var input = document.getElementById('wd-symbol-input');
    var errEl = document.getElementById('wd-symbol-error');
    if (!input || !errEl) return true;

    var val = (input.value || '').trim();
    var errSpan = errEl.querySelector('span');

    if (!val) {
      input.classList.remove('input-error');
      errEl.classList.remove('visible');
      return false;
    }

    if (!/^[A-Z0-9._]{1,30}$/.test(val)) {
      input.classList.add('input-error');
      errSpan.textContent = 'Only letters, numbers, dots, underscores allowed';
      errEl.classList.add('visible');
      return false;
    }

    input.classList.remove('input-error');
    errEl.classList.remove('visible');
    return true;
  }

  function _attachParamEvents() {
    document.querySelectorAll('.wd-param-input-ctrl').forEach(function (input) {
      var key = input.getAttribute('data-key');
      var handler = function () {
        var val;
        if (input.type === 'checkbox') val = input.checked;
        else if (input.tagName === 'SELECT' || input.type === 'text') val = input.value;
        else val = parseFloat(input.value);
        _parameterValues[key] = val;
        var row = document.querySelector('.wd-param-row[data-key="' + key + '"]');
        if (row) {
          if (val !== _parameterDefaults[key]) row.classList.add('modified');
          else row.classList.remove('modified');
        }
      };
      input.addEventListener(input.type === 'checkbox' ? 'change' : 'input', handler);
    });
    document.querySelectorAll('.wd-param-reset').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var key = btn.getAttribute('data-key');
        var defVal = _parameterDefaults[key];
        _parameterValues[key] = defVal;
        var input = document.querySelector('.wd-param-input-ctrl[data-key="' + key + '"]');
        if (input) {
          if (input.type === 'checkbox') input.checked = defVal;
          else input.value = defVal;
        }
        var row = document.querySelector('.wd-param-row[data-key="' + key + '"]');
        if (row) row.classList.remove('modified');
      });
    });
  }

  function _attachDeploymentStopEvents() {
    document.querySelectorAll('.dep-stop-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var depId = btn.getAttribute('data-depid');
        ApiClient.stopDeployment(depId).then(function () {
          ToastManager.show('Stop sent for ' + depId, 'info');
          _addActivity('Stop sent: ' + depId);
          setTimeout(_fetchDeployments, 2000);
        }).catch(function (err) {
          ToastManager.show('Stop failed: ' + err.message, 'error');
        });
      });
    });
  }

  /* ── Strategy Loading ────────────────────────────────────── */

  function _loadStrategies() {
    var el = document.getElementById('wd-strat-selector-body');
    if (!el) return;

    ApiClient.getStrategies().then(function (data) {
      _strategies = data.strategies || [];
      el.innerHTML = _renderStrategySelector();

      var sel = document.getElementById('wd-strategy-select');
      if (sel) {
        sel.addEventListener('change', function () {
          var sid = sel.value;
          if (!sid) {
            _selectedStrategyId = null;
            _selectedStrategy = null;
            _parameterValues = {};
            _parameterDefaults = {};
            _renderStrategyMeta();
            document.getElementById('wd-params-list').innerHTML =
              '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">Select a strategy to see parameters.</div>';
            document.getElementById('wd-param-count').textContent = '0 PARAMS';
            _updateChecklist();
            return;
          }
          _selectedStrategyId = sid;
          // Find in loaded list
          for (var i = 0; i < _strategies.length; i++) {
            if (_strategies[i].strategy_id === sid) {
              _selectedStrategy = _strategies[i];
              break;
            }
          }
          // If list didn't include full parameters, fetch detail
          if (_selectedStrategy && (!_selectedStrategy.parameters || Object.keys(_selectedStrategy.parameters).length === 0)) {
            ApiClient.getStrategy(sid).then(function (data) {
              if (data.ok && data.strategy) {
                var detail = data.strategy;
                if (detail.parameters && typeof detail.parameters === 'object') {
                  _selectedStrategy.parameters = detail.parameters;
                  _selectedStrategy.parameter_count = Object.keys(detail.parameters).length;
                }
              }
              _renderStrategyMeta();
              _loadParamsFromSchema();
              _updateChecklist();
              _addActivity('Strategy selected: ' + sid);
            }).catch(function () {
              _renderStrategyMeta();
              _loadParamsFromSchema();
              _updateChecklist();
            });
          } else {
            _renderStrategyMeta();
            _loadParamsFromSchema();
            _updateChecklist();
            _addActivity('Strategy selected: ' + sid);
          }
        });
      }
    }).catch(function () {
      el.innerHTML = '<div style="font-size:12px;color:var(--danger);padding:8px 0;">' +
        'Failed to load strategies from backend.</div>';
    });
  }

  function _loadParamsFromSchema() {
    _parameterValues = {};
    _parameterDefaults = {};

    if (_selectedStrategy && _selectedStrategy.parameters) {
      var schema = _selectedStrategy.parameters;
      Object.keys(schema).forEach(function (key) {
        var spec = schema[key];
        if (typeof spec === 'object' && spec.default !== undefined) {
          _parameterValues[key] = spec.default;
          _parameterDefaults[key] = spec.default;
        }
      });
    }

    var el = document.getElementById('wd-params-list');
    if (el) {
      el.innerHTML = _renderParams();
      _attachParamEvents();
    }

    var countEl = document.getElementById('wd-param-count');
    if (countEl) countEl.textContent = Object.keys(_parameterValues).length + ' PARAMS';
  }

  /* ── Deployments Loading ─────────────────────────────────── */

  function _fetchDeployments() {
    var el = document.getElementById('wd-deployments-body');
    if (!el) return;

    ApiClient.getDeployments().then(function (data) {
      var all = data.deployments || [];
      var wid = _currentWorker.worker_id;
      _deployments = all.filter(function (d) { return d.worker_id === wid; });
      _deployments.sort(function (a, b) {
        return (b.updated_at || '').localeCompare(a.updated_at || '');
      });

      var countEl = document.getElementById('wd-dep-count');
      if (countEl) countEl.textContent = _deployments.length;

      el.innerHTML = _renderDeployments();
      _attachDeploymentStopEvents();
    }).catch(function () {
      el.innerHTML = '<div style="font-size:12px;color:var(--danger);padding:8px 0;">Failed to load deployments.</div>';
    });
  }

  /* ── Deploy Handler ──────────────────────────────────────── */

  function _handleDeploy() {
    if (!_selectedStrategyId) {
      ToastManager.show('Select a strategy first.', 'warning');
      return;
    }

    /* ── Symbol validation ───────────────────────────── */
    var symbolVal = (_runtimeConfig.symbol || '').trim().toUpperCase();
    _runtimeConfig.symbol = symbolVal;
    var symInput = document.getElementById('wd-symbol-input');
    if (symInput) symInput.value = symbolVal;

    if (!symbolVal) {
      ToastManager.show('Enter a symbol.', 'warning');
      if (symInput) symInput.focus();
      return;
    }
    if (!/^[A-Z0-9._]{1,30}$/.test(symbolVal)) {
      ToastManager.show('Invalid symbol — letters, numbers, dots, underscores only.', 'warning');
      _validateSymbolInput();
      if (symInput) symInput.focus();
      return;
    }

    if (!_runtimeConfig.bar_size_points || _runtimeConfig.bar_size_points <= 0) {
      ToastManager.show('Bar Size Points must be > 0.', 'warning');
      return;
    }

    var w = _currentWorker;
    var name = w.worker_name || w.worker_id;
    var modCount = _getModifiedCount();
    var tlDisplay = _runtimeConfig.tick_lookback_value + ' ' + _runtimeConfig.tick_lookback_unit;
    var stratName = _selectedStrategy ? (_selectedStrategy.strategy_name || _selectedStrategyId) : _selectedStrategyId;

    var bodyHtml =
      '<p>Deploy strategy to <strong>' + name + '</strong>?</p>' +
      '<div class="modal-summary">' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Worker</span><span class="modal-summary-value">' + name + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Strategy</span><span class="modal-summary-value">' + stratName + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Symbol</span><span class="modal-summary-value">' + _runtimeConfig.symbol + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Tick Lookback</span><span class="modal-summary-value">' + tlDisplay + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Bar Size Points</span><span class="modal-summary-value">' + _runtimeConfig.bar_size_points + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Max Bars in Memory</span><span class="modal-summary-value">' + _runtimeConfig.max_bars_memory + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Lot Size</span><span class="modal-summary-value">' + _runtimeConfig.lot_size + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Modified Params</span><span class="modal-summary-value">' + modCount + '</span></div>' +
      '</div>';

    ModalManager.show({
      title: 'Deploy Strategy',
      bodyHtml: bodyHtml,
      confirmText: 'Deploy',
      onConfirm: function () {
        var payload = {
          strategy_id: _selectedStrategyId,
          worker_id: w.worker_id,
          symbol: _runtimeConfig.symbol,
          tick_lookback_value: _runtimeConfig.tick_lookback_value,
          tick_lookback_unit: _runtimeConfig.tick_lookback_unit,
          bar_size_points: _runtimeConfig.bar_size_points,
          max_bars_in_memory: _runtimeConfig.max_bars_memory,
          lot_size: _runtimeConfig.lot_size,
          strategy_parameters: _parameterValues,
        };

        _addActivity('Deploying ' + stratName + ' to ' + name + '\u2026');

        ApiClient.createDeployment(payload).then(function (data) {
          ToastManager.show('Deployment created: ' + data.deployment_id, 'success');
          _addActivity('Deployment created: ' + data.deployment_id);
          setTimeout(_fetchDeployments, 2000);
        }).catch(function (err) {
          ToastManager.show('Deployment failed: ' + err.message, 'error');
          _addActivity('Deployment failed: ' + err.message);
        });
      }
    });
  }

  /* ── Refresh ─────────────────────────────────────────────── */

  function _refreshAll() {
    _refreshWorkerStatus();
    _fetchDeployments();
  }

  function _refreshWorkerStatus() {
    if (!_currentWorker) return;
    ApiClient.getFleetWorkers().then(function (data) {
      var workers = data.workers || [];
      var wid = _currentWorker.worker_id;
      for (var i = 0; i < workers.length; i++) {
        if (workers[i].worker_id === wid) {
          _currentWorker = workers[i];
          var grid = document.getElementById('wd-status-grid');
          if (grid) grid.innerHTML = _renderStatusCards();
          var pill = document.getElementById('wd-state-pill');
          if (pill) {
            var st = _currentWorker.state || 'unknown';
            pill.className = 'state-pill ' + st;
            pill.textContent = _stateLabel(st);
          }
          _updateChecklist();
          return;
        }
      }
    }).catch(function () {});
  }

  /* ── Public ──────────────────────────────────────────────── */

  function render(workerData) {
    _currentWorker = workerData;
    _initState();

    document.getElementById('main-content').innerHTML = _buildPage();
    _attachEvents();

    _addActivity('Worker detail opened: ' + (workerData.worker_name || workerData.worker_id));

    // Load backend data
    _loadStrategies();
    _fetchDeployments();

    _refreshInterval = setInterval(_refreshAll, 5000);
  }

  function destroy() {
    if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; }
    _currentWorker = null;
  }

  return { render: render, destroy: destroy };
})();
```

---

## FILE: `vm/logging/event_log.py`

- Relative path: `vm/logging/event_log.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/vm/logging/event_log.py`
- Size bytes: `3457`
- SHA256: `df8ec517a77b4d6762a2911bb760f6b2873b1f23a3029a0ad1eac449f9e7bf3d`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
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
```

---

## FILE: `vm/README.md`

- Relative path: `vm/README.md`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/vm/README.md`
- Size bytes: `1215`
- SHA256: `28ead786e4eb10d807621099ef8cec7fec39d645e950a3b2dd1180cea90184c1`
- Guessed MIME type: `text/markdown`
- Guessed encoding: `unknown`

````markdown
# JINNI Grid — Worker Agent

## What It Does

Sends periodic heartbeat POST requests to the JINNI Grid Mother Server.
The Mother Server uses these heartbeats to track worker status in the Fleet dashboard.

## Prerequisites

- Python 3.10+
- `requests` and `pyyaml` packages

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Edit `config.yaml`:
   - Set `worker_id` to a unique ID for this worker
   - Set `worker_name` to a human-readable name
   - Set `mother_server.url` to your Mother Server's IP and port
   - Adjust `heartbeat.interval_seconds` if needed

3. Run the agent:
   ```bash
   python worker_agent.py
   ```

## Config Reference

```yaml
worker:
  worker_id: "vm-worker-01"      # Unique worker identifier
  worker_name: "Worker 01"       # Display name

mother_server:
  url: "http://192.168.1.100:5100"  # Mother Server address

heartbeat:
  interval_seconds: 5            # Seconds between heartbeats

agent:
  version: "0.1.0"               # Agent version reported to Mother Server
```

## What It Does NOT Do

- No MT5 connectivity
- No trading execution
- No strategy deployment
- No broker/account detection

Those features come in future phases.
````

---

## FILE: `vm/trading/indicators.py`

- Relative path: `vm/trading/indicators.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/vm/trading/indicators.py`
- Size bytes: `7085`
- SHA256: `91b2f5f74c0354d5f48ec8887a79fa64817afc12718014bf054de243b480eac7`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID — Indicator Engine
worker/indicators.py

Ported from JINNI ZERO backtester shared.py / engine_core.py.
Supports: SMA, EMA, WMA, HMA precomputation on range bar series.
Populates ctx.indicators (current bar values) and ctx.ind_series (full series).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


# =============================================================================
# Core MA Functions (matching JINNI ZERO backtester exactly)
# =============================================================================

def precompute_sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    window_sum = sum(values[:period])
    result[period - 1] = window_sum / period
    for i in range(period, n):
        window_sum += values[i] - values[i - period]
        result[i] = window_sum / period
    return result


def precompute_ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    # Seed with SMA
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    k = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        val = values[i] * k + prev * (1 - k)
        result[i] = val
        prev = val
    return result


def precompute_wma(values: List[float], period: int) -> List[Optional[float]]:
    """Weighted Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    denom = period * (period + 1) / 2.0
    for i in range(period - 1, n):
        w_sum = 0.0
        for j in range(period):
            w_sum += values[i - period + 1 + j] * (j + 1)
        result[i] = w_sum / denom
    return result


def precompute_hma(values: List[float], period: int) -> List[Optional[float]]:
    """
    Hull Moving Average — full series.
    HMA(n) = WMA( 2*WMA(n/2) - WMA(n), sqrt(n) )
    """
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result

    half = max(int(period / 2), 1)
    sqrt_p = max(int(math.sqrt(period)), 1)

    wma_half = precompute_wma(values, half)
    wma_full = precompute_wma(values, period)

    # Build diff series: 2*WMA(half) - WMA(full)
    diff = []
    diff_start = None
    for i in range(n):
        if wma_half[i] is not None and wma_full[i] is not None:
            diff.append(2.0 * wma_half[i] - wma_full[i])
            if diff_start is None:
                diff_start = i
        else:
            diff.append(0.0)

    if diff_start is None:
        return result

    # Only use valid portion of diff
    valid_diff = diff[diff_start:]
    hma_of_diff = precompute_wma(valid_diff, sqrt_p)

    for i, val in enumerate(hma_of_diff):
        target_idx = diff_start + i
        if target_idx < n:
            result[target_idx] = val

    return result


def precompute_ma(values: List[float], kind: str, period: int) -> List[Optional[float]]:
    """
    Dispatch to the correct MA precompute function.
    Matches JINNI ZERO backtester shared.py exactly.
    """
    kind_upper = kind.upper()
    if kind_upper == "SMA":
        return precompute_sma(values, period)
    elif kind_upper == "EMA":
        return precompute_ema(values, period)
    elif kind_upper == "WMA":
        return precompute_wma(values, period)
    elif kind_upper == "HMA":
        return precompute_hma(values, period)
    else:
        print(f"[INDICATORS] WARNING: Unknown MA kind '{kind}', falling back to SMA")
        return precompute_sma(values, period)


# =============================================================================
# Source Extraction
# =============================================================================

def _source_values(bars: list, source: str) -> List[float]:
    """Extract price series from bars by source name."""
    if source == "open":
        return [float(b.get("open", 0)) for b in bars]
    elif source == "high":
        return [float(b.get("high", 0)) for b in bars]
    elif source == "low":
        return [float(b.get("low", 0)) for b in bars]
    else:
        return [float(b.get("close", 0)) for b in bars]


def precompute_indicator_series(bars: list, spec: dict) -> List[Optional[float]]:
    """
    Precompute a full indicator series from bars + spec.
    Spec format (from strategy.build_indicators()):
        {"key": "hma_200", "kind": "HMA", "period": 200, "source": "close"}
    """
    kind = spec.get("kind", "SMA").upper()
    source = spec.get("source", "close")
    period = int(spec.get("period", 14))
    values = _source_values(bars, source)
    return precompute_ma(values, kind, period)


# =============================================================================
# Indicator Engine (live — recomputes on every new bar)
# =============================================================================

class IndicatorEngine:
    """
    Manages indicator computation for live trading.

    On each new bar:
      1. Recomputes full series for all declared indicators
      2. Updates ctx.indicators with current-bar values
      3. Updates ctx.ind_series with full series (for strategy lookback)

    This matches backtester behavior where indicators are precomputed
    over the full bar array. For live, we recompute on the growing
    bar deque — slightly less efficient but guarantees identical values.
    """

    def __init__(self, indicator_defs: List[Dict[str, Any]]):
        self._defs = indicator_defs
        self._warned: set = set()

        if self._defs:
            keys = [d["key"] for d in self._defs]
            print(f"[INDICATORS] Registered {len(self._defs)} indicators: {keys}")
        else:
            print("[INDICATORS] No indicators requested by strategy.")

    def update(self, bars: list, ctx) -> None:
        """Recompute all indicators from current bar list and update ctx."""
        for defn in self._defs:
            key = defn["key"]
            kind = defn.get("kind", "SMA").upper()
            source = defn.get("source", "close")
            period = int(defn.get("period", 14))

            values = _source_values(bars, source)
            series = precompute_ma(values, kind, period)

            # Store full series
            ctx._ind_series[key] = series

            # Store current value (last bar)
            if series and len(series) > 0:
                ctx._indicators[key] = series[-1]
            else:
                ctx._indicators[key] = None

    def get_series_at(self, indicator_store: dict, key: str, index: int) -> Optional[float]:
        """Get indicator value at a specific bar index."""
        series = indicator_store.get(key)
        if series is None or index < 0 or index >= len(series):
            return None
        return series[index]
```

---

## FILE: `vm/trading/mt5_history.py`

- Relative path: `vm/trading/mt5_history.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/vm/trading/mt5_history.py`
- Size bytes: `12908`
- SHA256: `8d244e9f97831fc051bd2f492e4f5611e5458cc56c3bd6fe2ec4daf78d87cde9`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
worker/mt5_history.py
MT5 Deal History — Source of Truth for Trade Records

Converts MT5 named-tuple results to plain dicts immediately
to prevent 'tuple indices must be integers' errors.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

log = logging.getLogger("jinni.mt5history")

_mt5 = None


def _get_mt5():
    global _mt5
    if _mt5 is None:
        try:
            import MetaTrader5 as mt5
            _mt5 = mt5
        except ImportError:
            log.error("MetaTrader5 package not available")
            return None
    return _mt5


# ── Safe conversion: MT5 deal object → plain dict ───────────

def _deal_to_dict(deal) -> dict:
    """
    Convert an MT5 TradeDeal object (named tuple / numpy row) to a plain dict.
    Uses getattr() for safety — works regardless of MT5 version.
    """
    return {
        "ticket": int(getattr(deal, "ticket", 0)),
        "order": int(getattr(deal, "order", 0)),
        "time": int(getattr(deal, "time", 0)),
        "time_msc": int(getattr(deal, "time_msc", 0)),
        "type": int(getattr(deal, "type", 0)),
        "entry": int(getattr(deal, "entry", 0)),
        "magic": int(getattr(deal, "magic", 0)),
        "position_id": int(getattr(deal, "position_id", 0)),
        "reason": int(getattr(deal, "reason", -1)),
        "volume": float(getattr(deal, "volume", 0.0)),
        "price": float(getattr(deal, "price", 0.0)),
        "commission": float(getattr(deal, "commission", 0.0)),
        "swap": float(getattr(deal, "swap", 0.0)),
        "profit": float(getattr(deal, "profit", 0.0)),
        "fee": float(getattr(deal, "fee", 0.0) or 0.0),
        "symbol": str(getattr(deal, "symbol", "")),
        "comment": str(getattr(deal, "comment", "")),
        "external_id": str(getattr(deal, "external_id", "")),
    }


# ── Deal Reason Mapping ─────────────────────────────────────

_REASON_MAP = None


def _get_reason_map() -> dict:
    global _REASON_MAP
    if _REASON_MAP is not None:
        return _REASON_MAP

    mt5 = _get_mt5()
    if mt5 is None:
        return {}

    _REASON_MAP = {}
    defs = [
        ("DEAL_REASON_CLIENT", "MANUAL_CLOSE"),
        ("DEAL_REASON_MOBILE", "MANUAL_CLOSE"),
        ("DEAL_REASON_WEB", "MANUAL_CLOSE"),
        ("DEAL_REASON_EXPERT", "STRATEGY_CLOSE"),
        ("DEAL_REASON_SL", "SL_HIT"),
        ("DEAL_REASON_TP", "TP_HIT"),
        ("DEAL_REASON_SO", "STOP_OUT"),
        ("DEAL_REASON_ROLLOVER", "ROLLOVER"),
        ("DEAL_REASON_VMARGIN", "VARIATION_MARGIN"),
        ("DEAL_REASON_SPLIT", "SPLIT"),
    ]
    for attr, label in defs:
        val = getattr(mt5, attr, None)
        if val is not None:
            _REASON_MAP[int(val)] = label

    log.info(f"[MT5-HIST] Reason map loaded: {_REASON_MAP}")
    return _REASON_MAP


# ── Core: Fetch Closed Position ─────────────────────────────

def fetch_closed_position(
    position_ticket: int,
    symbol: str = "",
    max_retries: int = 5,
    retry_delay_ms: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Fetch complete trade record for a closed position from MT5 deal history.
    Retries with increasing delay because MT5 needs time to finalize history.
    """
    mt5 = _get_mt5()
    if mt5 is None:
        log.error("[MT5-HIST] MT5 module not available")
        return None

    position_ticket = int(position_ticket)
    log.info(f"[MT5-HIST] Fetching history: ticket={position_ticket} symbol={symbol}")

    for attempt in range(1, max_retries + 1):
        # Increasing delay: 300ms, 600ms, 900ms, 1200ms, 1500ms
        delay_s = (retry_delay_ms * attempt) / 1000.0
        time.sleep(delay_s)

        try:
            from_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
            to_time = datetime.now(timezone.utc) + timedelta(hours=1)

            raw_deals = mt5.history_deals_get(
                from_time, to_time,
                position=position_ticket
            )

            if raw_deals is None:
                err = mt5.last_error()
                log.warning(
                    f"[MT5-HIST] Attempt {attempt}/{max_retries}: "
                    f"history_deals_get returned None. "
                    f"MT5 error: {err}"
                )
                continue

            if len(raw_deals) == 0:
                log.warning(
                    f"[MT5-HIST] Attempt {attempt}/{max_retries}: "
                    f"0 deals for position {position_ticket}"
                )
                continue

            # Convert ALL deals to plain dicts immediately
            deals = []
            for i, raw in enumerate(raw_deals):
                try:
                    d = _deal_to_dict(raw)
                    deals.append(d)
                    log.debug(
                        f"[MT5-HIST]   deal[{i}]: ticket={d['ticket']} "
                        f"entry={d['entry']} type={d['type']} "
                        f"price={d['price']} profit={d['profit']} "
                        f"commission={d['commission']} reason={d['reason']}"
                    )
                except Exception as conv_err:
                    log.error(
                        f"[MT5-HIST] Failed to convert deal[{i}]: {conv_err} "
                        f"raw type={type(raw)} raw={raw}"
                    )
                    continue

            if not deals:
                log.warning(
                    f"[MT5-HIST] Attempt {attempt}: {len(raw_deals)} raw deals "
                    f"but 0 converted successfully"
                )
                continue

            log.info(
                f"[MT5-HIST] Attempt {attempt}: {len(deals)} deals "
                f"for position {position_ticket}"
            )

            return _build_trade_record(position_ticket, deals, symbol)

        except Exception as e:
            log.error(
                f"[MT5-HIST] Attempt {attempt}/{max_retries} exception: "
                f"{type(e).__name__}: {e}"
            )
            continue

    log.error(
        f"[MT5-HIST] FAILED after {max_retries} retries "
        f"for position {position_ticket}"
    )
    return None


# ── Build trade record from parsed deal dicts ───────────────

def _build_trade_record(
    position_ticket: int,
    deals: List[dict],
    symbol: str
) -> Optional[Dict[str, Any]]:
    """
    Build a clean trade record from a list of deal dicts.
    All deals are already plain dicts (safe to use ["key"]).
    """
    reason_map = _get_reason_map()

    # ── Filter: only actual trade deals (BUY=0, SELL=1) ─────────
    # Excludes DEAL_TYPE_BALANCE(2), CREDIT(3), CHARGE(4),
    # CORRECTION(5), BONUS(6), COMMISSION(7), COMMISSION_DAILY(8),
    # COMMISSION_MONTHLY(9), etc. — these pollute financial totals.
    trade_deals = [d for d in deals if d["type"] in (0, 1)]
    non_trade   = [d for d in deals if d["type"] not in (0, 1)]

    if non_trade:
        log.warning(
        f"[MT5-HIST] Excluded {len(non_trade)} non-trade deal(s) "
        f"for position {position_ticket}: "
        f"{[(d['ticket'], f'type={d['type']}', f'profit={d['profit']}', f'comm={d['commission']}') for d in non_trade]}"
    )

    # Separate IN (entry=0) and OUT (entry=1,2,3) from trade deals only
    in_deals  = [d for d in trade_deals if d["entry"] == 0]
    out_deals = [d for d in trade_deals if d["entry"] in (1, 2, 3)]

    if not in_deals:
        log.warning(
            f"[MT5-HIST] No IN deal for position {position_ticket}. "
            f"Deal entries: {[d['entry'] for d in trade_deals]}"
        )
    if not out_deals:
        log.warning(
            f"[MT5-HIST] No OUT deal for position {position_ticket} "
            f"— may still be open"
        )
        return None

    in_deal  = in_deals[0] if in_deals else None
    out_deal = out_deals[-1]

    # ── Aggregate financials ONLY from actual BUY/SELL deals ────
    matched_deals = in_deals + out_deals
    total_profit     = round(sum(d["profit"]     for d in matched_deals), 2)
    total_commission = -0.01
    total_swap       = round(sum(d["swap"]       for d in matched_deals), 2)
    total_fee        = round(sum(d["fee"]        for d in matched_deals), 2)

    # Some brokers book commission as a separate DEAL_TYPE_COMMISSION (type=7)
    # deal, where the charge lives in the 'profit' field. Include those.
    for d in non_trade:
        if d["type"] in (7, 8, 9):          # COMMISSION / DAILY / MONTHLY
            broker_comm = round(d["profit"] + d["commission"], 2)
            if broker_comm != 0.0:
                total_commission = round(total_commission + broker_comm, 2)
                log.info(
                    f"[MT5-HIST] Added broker commission deal {d['ticket']}: "
                    f"{broker_comm:.2f}"
                )

    net_pnl = round(total_profit + total_commission + total_swap + total_fee, 2)

    # Entry info
    entry_price = in_deal["price"] if in_deal else out_deal["price"]
    entry_time  = in_deal["time"]  if in_deal else out_deal["time"]

    # Exit info
    exit_price = out_deal["price"]
    exit_time  = out_deal["time"]

    # Direction: IN deal type 0=BUY→long, 1=SELL→short
    if in_deal:
        direction = "long" if in_deal["type"] == 0 else "short"
    else:
        direction = "short" if out_deal["type"] == 0 else "long"

    volume       = in_deal["volume"] if in_deal else out_deal["volume"]
    trade_symbol = (in_deal or out_deal)["symbol"] or symbol

    # Close reason from MT5 reason enum
    close_reason    = "UNKNOWN"
    out_reason_code = out_deal["reason"]
    if out_reason_code >= 0:
        close_reason = reason_map.get(out_reason_code, "UNKNOWN")
        log.info(f"[MT5-HIST] Reason code={out_reason_code} -> {close_reason}")

    # Fallback: check deal comment
    if close_reason in ("UNKNOWN", "STRATEGY_CLOSE"):
        comment = out_deal["comment"].lower()
        if "tp" in comment:
            close_reason = "TP_HIT"
        elif "sl" in comment:
            close_reason = "SL_HIT"
        elif "so" in comment:
            close_reason = "STOP_OUT"

    all_tickets = [d["ticket"] for d in matched_deals]

    record = {
        "mt5_position_ticket": position_ticket,
        "mt5_deal_tickets":    all_tickets,
        "mt5_entry_deal":      in_deal["ticket"] if in_deal else None,
        "mt5_exit_deal":       out_deal["ticket"],
        "symbol":              trade_symbol,
        "direction":           direction,
        "volume":              volume,
        "lot_size":            volume,
        "entry_price":         round(entry_price, 8),
        "exit_price":          round(exit_price, 8),
        "entry_time":          entry_time,
        "exit_time":           exit_time,
        "profit":              total_profit,
        "commission":          total_commission,
        "swap":                total_swap,
        "fee":                 total_fee,
        "net_pnl":             net_pnl,
        "exit_reason":         close_reason,
        "mt5_comment":         out_deal["comment"],
        "mt5_source":          True,
    }

    log.info(
        f"[MT5-HIST] RECORD BUILT: pos={position_ticket} "
        f"{direction.upper()} {trade_symbol} "
        f"entry={entry_price:.5f} exit={exit_price:.5f} "
        f"profit={total_profit:.2f} comm={total_commission:.2f} "
        f"swap={total_swap:.2f} net={net_pnl:.2f} "
        f"reason={close_reason} deals={all_tickets}"
    )

    return record


# ── Bulk fetch (for reconciliation) ─────────────────────────

def fetch_recent_closed_positions(since_hours: int = 24) -> list:
    mt5 = _get_mt5()
    if mt5 is None:
        return []

    from_time = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    to_time = datetime.now(timezone.utc) + timedelta(hours=1)

    raw = mt5.history_deals_get(from_time, to_time)
    if raw is None or len(raw) == 0:
        return []

    # Convert and group by position_id
    positions = {}
    for r in raw:
        try:
            d = _deal_to_dict(r)
        except Exception:
            continue
        pid = d["position_id"]
        if pid == 0:
            continue
        positions.setdefault(pid, []).append(d)

    results = []
    for pid, pos_deals in positions.items():
        has_in = any(d["entry"] == 0 for d in pos_deals)
        has_out = any(d["entry"] in (1, 2, 3) for d in pos_deals)
        if has_in and has_out:
            rec = _build_trade_record(pid, pos_deals, "")
            if rec:
                results.append(rec)

    log.info(f"[MT5-HIST] Bulk fetch: {len(results)} closed positions")
    return results
```

---

## FILE: `vm/trading/portfolio.py`

- Relative path: `vm/trading/portfolio.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/vm/trading/portfolio.py`
- Size bytes: `10094`
- SHA256: `a78fb92e3c0b342bdc454bc956e657ca79c1610712bd0347cb590986731c3c29`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID — Portfolio / Trade Ledger
worker/portfolio.py

Persistent trade history + rolling stats + equity tracking.
SQLite-backed, one DB per worker in data/portfolio_{worker_id}.db.

API:
  ledger = TradeLedger(worker_id)
  ledger.add_trade(trade_record)
  ledger.get_all_trades()
  ledger.get_summary()
  ledger.get_equity_curve()
  ledger.export_summary()
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class TradeLedger:
    """Persistent trade ledger for a single worker."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self._lock = threading.Lock()
        os.makedirs(DATA_DIR, exist_ok=True)
        self._db_path = os.path.join(DATA_DIR, f"portfolio_{worker_id}.db")
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
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                deployment_id TEXT,
                strategy_id TEXT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_bar INTEGER,
                exit_bar INTEGER,
                entry_time INTEGER,
                exit_time INTEGER,
                exit_reason TEXT,
                sl_level REAL,
                tp_level REAL,
                lot_size REAL DEFAULT 0.01,
                ticket INTEGER,
                points_pnl REAL DEFAULT 0.0,
                profit REAL DEFAULT 0.0,
                bars_held INTEGER DEFAULT 0,
                status TEXT DEFAULT 'open',
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                data_json TEXT
            );

            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                balance REAL,
                equity REAL,
                floating_pnl REAL,
                open_positions INTEGER DEFAULT 0,
                cumulative_pnl REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
            CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
        """)
        conn.commit()
        conn.close()

    # ── Trade Management ────────────────────────────────────

    def add_trade(self, record: dict, deployment_id: str = None,
                  strategy_id: str = None) -> int:
        """Add a closed trade record. Returns the DB row ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute("""
                    INSERT INTO trades (trade_id, deployment_id, strategy_id, symbol,
                        direction, entry_price, exit_price, entry_bar, exit_bar,
                        entry_time, exit_time, exit_reason, sl_level, tp_level,
                        lot_size, ticket, points_pnl, profit, bars_held,
                        status, opened_at, closed_at, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.get("id"), deployment_id, strategy_id,
                    record.get("symbol", ""), record.get("direction", ""),
                    record.get("entry_price", 0), record.get("exit_price"),
                    record.get("entry_bar"), record.get("exit_bar"),
                    record.get("entry_time"), record.get("exit_time"),
                    record.get("exit_reason"), record.get("sl_level"),
                    record.get("tp_level"), record.get("lot_size", 0.01),
                    record.get("ticket"), record.get("points_pnl", 0),
                    record.get("profit", 0), record.get("bars_held", 0),
                    "closed", now, now,
                    json.dumps(record, default=str),
                ))
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def record_equity_snapshot(self, balance: float, equity: float,
                               floating_pnl: float, open_positions: int):
        """Periodic equity snapshot for curve building."""
        now = datetime.now(timezone.utc).isoformat()
        cum = self._get_cumulative_pnl()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    INSERT INTO equity_snapshots (timestamp, balance, equity,
                        floating_pnl, open_positions, cumulative_pnl)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (now, balance, equity, floating_pnl, open_positions, cum))
                conn.commit()
            finally:
                conn.close()

    def _get_cumulative_pnl(self) -> float:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(profit), 0.0) as total FROM trades WHERE status='closed'"
            ).fetchone()
            return float(row["total"]) if row else 0.0
        finally:
            conn.close()

    # ── Queries ─────────────────────────────────────────────

    def get_all_trades(self, limit: int = 500, symbol: str = None,
                       strategy_id: str = None) -> List[dict]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM trades WHERE status='closed'"
            params = []
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            if strategy_id:
                query += " AND strategy_id = ?"
                params.append(strategy_id)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_open_trades(self) -> List[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='open' ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_equity_curve(self, limit: int = 1000) -> List[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM equity_snapshots ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()

    def get_summary(self) -> dict:
        """Compute rolling stats from closed trades."""
        conn = self._get_conn()
        try:
            trades = conn.execute(
                "SELECT direction, profit, points_pnl, bars_held, exit_reason "
                "FROM trades WHERE status='closed' ORDER BY id"
            ).fetchall()

            if not trades:
                return {
                    "total_trades": 0, "wins": 0, "losses": 0,
                    "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                    "avg_winner": 0.0, "avg_loser": 0.0,
                    "best_trade": 0.0, "worst_trade": 0.0,
                    "avg_bars_held": 0.0, "longs": 0, "shorts": 0,
                    "avg_r": 0.0, "profit_factor": 0.0,
                }

            profits = [float(t["profit"]) for t in trades]
            wins = [p for p in profits if p > 0]
            losses = [p for p in profits if p <= 0]
            bars_list = [int(t["bars_held"]) for t in trades]
            longs = sum(1 for t in trades if t["direction"] == "long")
            shorts = sum(1 for t in trades if t["direction"] == "short")

            gross_profit = sum(wins) if wins else 0.0
            gross_loss = abs(sum(losses)) if losses else 0.0

            return {
                "total_trades": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
                "total_pnl": round(sum(profits), 2),
                "avg_pnl": round(sum(profits) / len(trades), 2) if trades else 0.0,
                "avg_winner": round(sum(wins) / len(wins), 2) if wins else 0.0,
                "avg_loser": round(sum(losses) / len(losses), 2) if losses else 0.0,
                "best_trade": round(max(profits), 2) if profits else 0.0,
                "worst_trade": round(min(profits), 2) if profits else 0.0,
                "avg_bars_held": round(sum(bars_list) / len(bars_list), 1) if bars_list else 0.0,
                "longs": longs,
                "shorts": shorts,
                "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0,
            }
        finally:
            conn.close()

    def export_summary(self) -> dict:
        """Full export for API/UI consumption."""
        return {
            "worker_id": self.worker_id,
            "stats": self.get_summary(),
            "recent_trades": self.get_all_trades(limit=50),
            "equity_curve": self.get_equity_curve(limit=500),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
```
