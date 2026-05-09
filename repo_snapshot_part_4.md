# Repository Snapshot - Part 4 of 4

- Root folder: `/home/hurairahengg/Documents/JinniGrid`
- you knwo my whole jinni grid systeM/ basically it is thereliek a kubernetes server setup what it does is basically a mother server with ui and bunch of lank state VMs. the vms run a speacial typa of renko style bars not normal timeframe u will get more context in the codes but yeha and we can uipload strategy codes though mother ui and it wiill run strategy mt5 report and ecetra ecetra. currently im done coding the strategy system but its not tested yet an have confrimed bugs. so firm i wil ldrop u my whole project codebases from my readme. understand each code its role and keep in ur context i will give u big promtps to update code later duinerstood
- Total files indexed: `26`
- Files in this chunk: `9`
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
worker/config.yaml
worker/event_log.py
worker/execution.py
worker/indicators.py
worker/portfolio.py
worker/README.md
worker/requirements.txt
worker/strategyWorker.py
worker/worker_agent.py
```

## Files In This Chunk - Part 4

```text
app/persistence.py
ui/index.html
worker/config.yaml
worker/event_log.py
worker/execution.py
worker/indicators.py
worker/portfolio.py
worker/README.md
worker/worker_agent.py
```

## File Contents


---

## FILE: `app/persistence.py`

- Relative path: `app/persistence.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/persistence.py`
- Size bytes: `17080`
- SHA256: `1ac4f666a957a3d59fa1aa645fe2934d852df8237751d24a63940d155d385354`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
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
    """)
    conn.commit()


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
        d["active_strategies"] = json.loads(d.get("active_strategies_json", "[]")) if "active_strategies_json" in d.keys() else []
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
```

---

## FILE: `ui/index.html`

- Relative path: `ui/index.html`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/index.html`
- Size bytes: `2851`
- SHA256: `f2022f065a078e84d49798b3903e042f035ad228f5a66eb8a1ce6d19b38b59f7`
- Guessed MIME type: `text/html`
- Guessed encoding: `unknown`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>JINNI GRID — Mother Server Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
    rel="stylesheet"
  />
  <link
    rel="stylesheet"
    href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"
  />
  <link rel="stylesheet" href="/css/style.css" />
</head>
<body data-theme="dark">

  <aside class="sidebar" id="sidebar">
    <div class="sidebar-brand">
      <div class="brand-mark">JG</div>
      <div class="brand-text">
        <span class="brand-name">JINNI GRID</span>
        <span class="brand-sub">Mother Server</span>
      </div>
    </div>
    <nav class="sidebar-nav" id="sidebar-nav">
      <a href="#" class="nav-item active" data-page="dashboard">
        <i class="fa-solid fa-grip"></i><span>Dashboard</span>
      </a>
      <a href="#" class="nav-item" data-page="fleet">
        <i class="fa-solid fa-server"></i><span>Fleet</span>
      </a>
      <a href="#" class="nav-item" data-page="portfolio">
        <i class="fa-solid fa-chart-line"></i><span>Portfolio</span>
      </a>
      <a href="#" class="nav-item" data-page="strategies">
        <i class="fa-solid fa-crosshairs"></i><span>Strategies</span>
      </a>
      <a href="#" class="nav-item" data-page="logs">
        <i class="fa-solid fa-scroll"></i><span>Logs</span>
      </a>
      <a href="#" class="nav-item" data-page="settings">
        <i class="fa-solid fa-gear"></i><span>Settings</span>
      </a>
    </nav>
    <div class="sidebar-footer">
      <button class="theme-toggle" id="theme-toggle" title="Toggle Theme">
        <i class="fa-solid fa-sun"></i><span>Light Mode</span>
      </button>
    </div>
  </aside>

  <div class="main-wrapper">
    <header class="topbar" id="topbar">
      <div class="topbar-left">
        <h1 class="topbar-title" id="topbar-title">Dashboard</h1>
        <span class="topbar-subtitle">Mother Server Control Panel</span>
      </div>
      <div class="topbar-right">
        <div class="topbar-status">
          <span class="status-dot status-dot--online pulse"></span>
          <span class="status-label">System Online</span>
        </div>
        <div class="topbar-clock" id="topbar-clock">00:00:00</div>
      </div>
    </header>
    <main class="content" id="main-content"></main>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
  <script src="/js/main.js"></script>
  <script src="/js/workerDetailRenderer.js"></script>
</body>
</html>
```

---

## FILE: `worker/config.yaml`

- Relative path: `worker/config.yaml`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/config.yaml`
- Size bytes: `176`
- SHA256: `b6a616e396af64890e55c695fd7cce35828353dfea90fdd1179b08d4642e63b9`
- Guessed MIME type: `application/yaml`
- Guessed encoding: `unknown`

```yaml
worker:
  worker_id: "vm-worker-01"
  worker_name: "Worker 01"

mother_server:
  url: "http://192.168.3.232:5100"

heartbeat:
  interval_seconds: 10

agent:
  version: "0.1.0"
```

---

## FILE: `worker/event_log.py`

- Relative path: `worker/event_log.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/event_log.py`
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

## FILE: `worker/execution.py`

- Relative path: `worker/execution.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/execution.py`
- Size bytes: `20490`
- SHA256: `e563527cf0418b617746d365cbaeab54da0dcf787b3d38beb0a1accbba39e7bb`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID — Trade Execution Layer + Logger
worker/execution.py

Handles:
  - Real MT5 order execution (BUY/SELL/CLOSE)
  - Position querying (filtered by magic number)
  - SL/TP modification
  - R-multiple TP computation from fill price
  - MA-snapshot SL computation
  - MA-cross exit monitoring
  - Dedicated [EXEC] execution logger
  - Trade record building for ctx._trades
  - Signal validation (ported from JINNI ZERO engine_core.py)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Signal Constants
# =============================================================================

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_CLOSE = "CLOSE"
SIGNAL_CLOSE_LONG = "CLOSE_LONG"
SIGNAL_CLOSE_SHORT = "CLOSE_SHORT"
VALID_SIGNALS = {
    SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE,
    SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT, None,
}


# =============================================================================
# Signal Validation (ported from JINNI ZERO engine_core.py)
# =============================================================================

def validate_signal(raw, bar_index: int) -> dict:
    """
    Validate and normalize a raw signal dict from strategy.on_bar().
    Matches JINNI ZERO backtester validate_signal() exactly.
    """
    if raw is None:
        return {"signal": "HOLD"}
    if not isinstance(raw, dict):
        print(f"[EXEC] WARNING: Bar {bar_index}: strategy returned "
              f"{type(raw).__name__}, expected dict or None")
        return {"signal": "HOLD"}

    sig = raw.get("signal")
    if sig is not None:
        sig = str(sig).upper()
    if sig not in VALID_SIGNALS:
        print(f"[EXEC] WARNING: Bar {bar_index}: invalid signal '{sig}'")
        return {"signal": "HOLD"}

    out = {"signal": sig or "HOLD"}

    # Direct SL/TP
    if raw.get("sl") is not None:
        out["sl"] = float(raw["sl"])
    if raw.get("tp") is not None:
        out["tp"] = float(raw["tp"])

    # Engine-computed SL/TP fields
    for key in ("sl_mode", "sl_pts", "sl_ma_key", "sl_ma_val",
                "tp_mode", "tp_r"):
        if raw.get(key) is not None:
            if key in ("sl_mode", "sl_ma_key", "tp_mode"):
                out[key] = raw[key]
            else:
                out[key] = float(raw[key])

    # Engine-level MA cross exit keys
    if raw.get("engine_sl_ma_key") is not None:
        out["engine_sl_ma_key"] = str(raw["engine_sl_ma_key"])
    if raw.get("engine_tp_ma_key") is not None:
        out["engine_tp_ma_key"] = str(raw["engine_tp_ma_key"])

    # CLOSE signal
    if out["signal"] == "CLOSE":
        out["close"] = True
        out["close_reason"] = str(raw.get("close_reason", "strategy_close"))
    elif raw.get("close"):
        out["close"] = True
        out["close_reason"] = str(raw.get("close_reason", "strategy_close"))

    # Dynamic SL/TP updates
    if raw.get("update_sl") is not None:
        out["update_sl"] = float(raw["update_sl"])
    if raw.get("update_tp") is not None:
        out["update_tp"] = float(raw["update_tp"])

    # Comment
    if raw.get("comment"):
        out["comment"] = str(raw["comment"])

    return out


# =============================================================================
# SL/TP Computation Helpers
# =============================================================================

def compute_sl(signal: dict, entry_price: float, direction: str) -> Optional[float]:
    """
    Compute SL price from signal fields.
    Supports: direct sl, sl_mode=ma_snapshot, sl_mode=fixed.
    """
    sl_mode = signal.get("sl_mode")

    if sl_mode == "ma_snapshot":
        ma_val = signal.get("sl_ma_val")
        if ma_val is not None:
            ma_val = float(ma_val)
            if direction == "long" and ma_val < entry_price:
                return round(ma_val, 5)
            elif direction == "short" and ma_val > entry_price:
                return round(ma_val, 5)
        return None

    if sl_mode == "fixed":
        pts = float(signal.get("sl_pts", 0))
        if pts > 0:
            if direction == "long":
                return round(entry_price - pts, 5)
            else:
                return round(entry_price + pts, 5)
        return None

    # Direct SL
    if signal.get("sl") is not None:
        return float(signal["sl"])

    return None


def compute_tp(signal: dict, entry_price: float, sl_price: Optional[float],
               direction: str) -> Optional[float]:
    """
    Compute TP price from signal fields.
    Supports: direct tp, tp_mode=r_multiple.
    """
    tp_mode = signal.get("tp_mode")

    if tp_mode == "r_multiple":
        r = float(signal.get("tp_r", 1.0))
        if sl_price is not None:
            risk = abs(entry_price - sl_price)
            if risk > 0:
                if direction == "long":
                    return round(entry_price + risk * r, 5)
                else:
                    return round(entry_price - risk * r, 5)
        return None

    # Direct TP
    if signal.get("tp") is not None:
        return float(signal["tp"])

    return None


# =============================================================================
# Position State
# =============================================================================

@dataclass
class PositionState:
    has_position: bool = False
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    size: Optional[float] = None
    ticket: Optional[int] = None
    profit: Optional[float] = None
    entry_bar: Optional[int] = None


# =============================================================================
# Execution Logger
# =============================================================================

class ExecutionLogger:
    """Dedicated [EXEC] logger for all trade decisions."""

    def __init__(self, deployment_id: str, symbol: str):
        self.deployment_id = deployment_id
        self.symbol = symbol
        self.buys_attempted = 0
        self.buys_filled = 0
        self.sells_attempted = 0
        self.sells_filled = 0
        self.closes_attempted = 0
        self.closes_filled = 0
        self.holds = 0
        self.skips = 0
        self.rejections = 0
        self.modifications = 0
        self.ma_cross_exits = 0

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

    def _pos_str(self, pos: PositionState) -> str:
        if not pos or not pos.has_position:
            return "FLAT"
        d = (pos.direction or "?").upper()
        p = f"@{pos.entry_price:.5f}" if pos.entry_price else ""
        s = f"x{pos.size}" if pos.size else ""
        pnl = f" pnl={pos.profit:.2f}" if pos.profit is not None else ""
        return f"{d}{p}{s}{pnl}"

    def log_signal(self, action: str, bar_idx: int, bar_time, price,
                   pos: PositionState):
        print(
            f"[EXEC] {self._ts()} | {action} | {self.symbol} | "
            f"bar={bar_idx} t={bar_time} | price={price} | "
            f"pos={self._pos_str(pos)}"
        )

    def log_open(self, direction: str, result: dict, sl=None, tp=None):
        if direction == "BUY":
            self.buys_attempted += 1
        else:
            self.sells_attempted += 1

        if result.get("success"):
            if direction == "BUY":
                self.buys_filled += 1
            else:
                self.sells_filled += 1
            print(
                f"[EXEC]   -> OPENED {direction} | "
                f"ticket={result.get('ticket')} "
                f"price={result.get('price', 0):.5f} "
                f"vol={result.get('volume', 0)} "
                f"sl={sl} tp={tp}"
            )
        else:
            self.rejections += 1
            print(
                f"[EXEC]   -> REJECTED {direction} | "
                f"error={result.get('error', 'unknown')}"
            )

    def log_close(self, results: list, reason: str = "signal"):
        self.closes_attempted += 1
        for r in results:
            if r.get("success"):
                self.closes_filled += 1
                print(
                    f"[EXEC]   -> CLOSED ticket={r.get('ticket')} "
                    f"price={r.get('price', 0):.5f} "
                    f"profit={r.get('profit', 0):.2f} "
                    f"reason={reason}"
                )
            else:
                self.rejections += 1
                print(
                    f"[EXEC]   -> CLOSE FAILED ticket={r.get('ticket', '?')} "
                    f"error={r.get('error', 'unknown')}"
                )

    def log_skip(self, action: str, reason: str):
        self.skips += 1
        print(f"[EXEC]   -> SKIPPED {action} | reason={reason}")

    def log_hold(self):
        self.holds += 1

    def log_modify(self, result: dict, sl=None, tp=None):
        self.modifications += 1
        if result.get("success"):
            print(f"[EXEC]   -> MODIFIED sl={sl} tp={tp}")
        else:
            print(f"[EXEC]   -> MODIFY FAILED error={result.get('error')}")

    def log_ma_cross_exit(self, ma_key: str, direction: str, ma_val: float,
                          close_price: float):
        self.ma_cross_exits += 1
        print(
            f"[EXEC]   -> MA CROSS EXIT | {ma_key}={ma_val:.5f} "
            f"close={close_price:.5f} dir={direction}"
        )

    def get_stats(self) -> dict:
        return {
            "buys_attempted": self.buys_attempted,
            "buys_filled": self.buys_filled,
            "sells_attempted": self.sells_attempted,
            "sells_filled": self.sells_filled,
            "closes_attempted": self.closes_attempted,
            "closes_filled": self.closes_filled,
            "holds": self.holds,
            "skips": self.skips,
            "rejections": self.rejections,
            "modifications": self.modifications,
            "ma_cross_exits": self.ma_cross_exits,
        }


# =============================================================================
# MT5 Trade Executor
# =============================================================================

def _import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


class MT5Executor:
    """Handles all real MT5 order execution."""

    def __init__(self, symbol: str, lot_size: float, deployment_id: str):
        self.symbol = symbol
        self.lot_size = lot_size
        self.magic = self._make_magic(deployment_id)
        self._mt5 = _import_mt5()
        self._filling_mode = None

        if self._mt5:
            self._filling_mode = self._detect_filling()
            print(
                f"[EXECUTOR] Ready: symbol={symbol} lot={lot_size} "
                f"magic={self.magic} filling={self._filling_mode}"
            )
        else:
            print("[EXECUTOR] WARNING: MT5 not available. Execution disabled.")

    @staticmethod
    def _make_magic(deployment_id: str) -> int:
        h = 0
        for c in deployment_id:
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
        return (h % 900000) + 100000

    def _detect_filling(self) -> int:
        mt5 = self._mt5
        info = mt5.symbol_info(self.symbol)
        if info is None:
            return 1
        fm = info.filling_mode
        if fm & 2:
            return 1  # IOC
        elif fm & 1:
            return 0  # FOK
        else:
            return 2  # RETURN

    # ── Open Orders ─────────────────────────────────────────

    def open_buy(self, sl=None, tp=None, comment="") -> dict:
        return self._open_order("buy", sl, tp, comment)

    def open_sell(self, sl=None, tp=None, comment="") -> dict:
        return self._open_order("sell", sl, tp, comment)

    def _open_order(self, direction: str, sl=None, tp=None,
                    comment="") -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "error": "MT5 not available"}

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return {"success": False,
                    "error": f"No tick data for {self.symbol}"}

        is_buy = direction == "buy"
        price = tick.ask if is_buy else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot_size,
            "type": order_type,
            "price": price,
            "deviation": 30,
            "magic": self.magic,
            "comment": comment or f"JG_{direction}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode,
        }

        if sl is not None and sl > 0:
            request["sl"] = round(float(sl), 5)
        if tp is not None and tp > 0:
            request["tp"] = round(float(tp), 5)

        print(f"[EXECUTOR] Sending {direction.upper()}: {request}")
        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            return {"success": False, "error": f"order_send returned None: {err}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "error": f"retcode={result.retcode} comment={result.comment}",
                "retcode": result.retcode,
            }

        return {
            "success": True,
            "ticket": result.order,
            "price": result.price,
            "volume": result.volume,
        }

    # ── Close Orders ────────────────────────────────────────

    def close_position(self, ticket: int, pos_type: int,
                       volume: float, profit: float) -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "ticket": ticket,
                    "error": "MT5 not available"}

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return {"success": False, "ticket": ticket,
                    "error": f"No tick for {self.symbol}"}

        is_long = (pos_type == 0)
        close_price = tick.bid if is_long else tick.ask
        close_type = mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": volume,
            "type": close_type,
            "position": ticket,
            "price": close_price,
            "deviation": 30,
            "magic": self.magic,
            "comment": "JG_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode,
        }

        print(f"[EXECUTOR] Closing ticket={ticket}: {request}")
        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            return {"success": False, "ticket": ticket,
                    "error": f"order_send None: {err}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False, "ticket": ticket,
                "error": f"retcode={result.retcode} comment={result.comment}",
            }

        return {
            "success": True, "ticket": ticket,
            "price": result.price, "volume": volume,
            "profit": profit,
        }

    def close_all_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions()]

    def close_long_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions() if p["type"] == 0]

    def close_short_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions() if p["type"] == 1]

    # ── Modify SL/TP ────────────────────────────────────────

    def modify_sl_tp(self, ticket: int, sl=None, tp=None) -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "error": "MT5 not available"}

        positions = mt5.positions_get(ticket=ticket)
        if positions is None or len(positions) == 0:
            return {"success": False, "error": f"Position {ticket} not found"}

        pos = positions[0]
        new_sl = round(float(sl), 5) if sl is not None else pos.sl
        new_tp = round(float(tp), 5) if tp is not None else pos.tp

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp,
        }

        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "error": "order_send returned None"}
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False,
                    "error": f"retcode={result.retcode} comment={result.comment}"}
        return {"success": True, "sl": new_sl, "tp": new_tp}

    # ── Query ───────────────────────────────────────────────

    def get_positions(self) -> list:
        mt5 = self._mt5
        if mt5 is None:
            return []
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []
        result = []
        for p in positions:
            if p.magic != self.magic:
                continue
            result.append({
                "ticket": p.ticket, "type": p.type,
                "volume": p.volume, "price_open": p.price_open,
                "sl": p.sl, "tp": p.tp, "profit": p.profit,
                "symbol": p.symbol, "magic": p.magic,
            })
        return result

    def get_floating_pnl(self) -> float:
        return sum(p["profit"] for p in self.get_positions())

    def get_open_count(self) -> int:
        return len(self.get_positions())

    def get_position_state(self) -> PositionState:
        positions = self.get_positions()
        if not positions:
            return PositionState(has_position=False)
        p = positions[0]
        return PositionState(
            has_position=True,
            direction="long" if p["type"] == 0 else "short",
            entry_price=p["price_open"],
            sl=p["sl"] if p["sl"] != 0 else None,
            tp=p["tp"] if p["tp"] != 0 else None,
            size=p["volume"],
            ticket=p["ticket"],
            profit=p["profit"],
        )


# =============================================================================
# Trade Record Builder (for ctx._trades)
# =============================================================================

def build_trade_record(
    trade_id: int,
    direction: str,
    entry_price: float,
    entry_bar: int,
    entry_time: int,
    exit_price: float,
    exit_bar: int,
    exit_time: int,
    exit_reason: str,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    lot_size: float = 0.01,
    ticket: Optional[int] = None,
    profit: Optional[float] = None,
) -> dict:
    """
    Build a trade record compatible with JINNI ZERO backtester format.
    Strategies use ctx.trades for gating logic, no-reuse, etc.
    """
    points_pnl = (exit_price - entry_price) if direction == "long" \
                 else (entry_price - exit_price)

    return {
        "id": trade_id,
        "direction": direction,
        "entry_bar": entry_bar,
        "entry_time": entry_time,
        "entry_price": round(entry_price, 5),
        "exit_bar": exit_bar,
        "exit_time": exit_time,
        "exit_price": round(exit_price, 5),
        "exit_reason": exit_reason,
        "sl_level": sl,
        "tp_level": tp,
        "lot_size": lot_size,
        "ticket": ticket,
        "points_pnl": round(points_pnl, 5),
        "profit": profit,
        "bars_held": exit_bar - entry_bar,
    }
```

---

## FILE: `worker/indicators.py`

- Relative path: `worker/indicators.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/indicators.py`
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

## FILE: `worker/portfolio.py`

- Relative path: `worker/portfolio.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/portfolio.py`
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

---

## FILE: `worker/README.md`

- Relative path: `worker/README.md`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/README.md`
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

## FILE: `worker/worker_agent.py`

- Relative path: `worker/worker_agent.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/worker_agent.py`
- Size bytes: `8281`
- SHA256: `3f7c2363d67c80f55159925893dbf80d96c2d95cce9a540f02d6c7a439e791a2`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Worker Agent
Heartbeat + Command polling + Strategy Runner management.
worker/worker_agent.py
"""
import os
import sys
import time
import socket
import threading
import yaml
import requests

_worker_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_worker_dir)
if _worker_dir not in sys.path:
    sys.path.insert(0, _worker_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from strategyWorker import StrategyRunner


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    if not os.path.exists(config_path):
        print(f"[ERROR] config.yaml not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_host():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return f"{hostname} ({ip})"
    except Exception:
        return socket.gethostname()


class WorkerAgent:
    def __init__(self, config: dict):
        self.worker_id = config["worker"]["worker_id"]
        self.worker_name = config["worker"].get("worker_name", self.worker_id)
        self.mother_url = config["mother_server"]["url"].rstrip("/")
        self.heartbeat_interval = config["heartbeat"].get("interval_seconds", 10)
        self.agent_version = config["agent"].get("version", "0.1.0")
        self.host = detect_host()

        self._runner: StrategyRunner | None = None
        self._runner_lock = threading.Lock()

    # ── Heartbeat ───────────────────────────────────────────

    def _build_heartbeat_payload(self) -> dict:
        runner = self._runner
        diag = runner.get_diagnostics() if runner else {}

        runner_state = diag.get("runner_state", "idle")
        if runner_state in ("idle", "running", "warming_up"):
            worker_state = "online"
        elif runner_state == "failed":
            worker_state = "error"
        elif runner_state == "stopped":
            worker_state = "online"
        else:
            worker_state = runner_state if runner else "online"

        active_strategies = []
        if diag.get("strategy_id"):
            active_strategies = [diag["strategy_id"]]

        errors = []
        if diag.get("last_error"):
            errors = [diag["last_error"]]

        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "host": self.host,
            "state": worker_state,
            "agent_version": self.agent_version,
            "mt5_state": diag.get("mt5_state"),
            "account_id": diag.get("account_id"),
            "broker": diag.get("broker"),
            "active_strategies": active_strategies,
            "open_positions_count": diag.get("open_positions_count", 0),
            "floating_pnl": diag.get("floating_pnl", 0.0),
            "errors": errors,
            # Pipeline
            "total_ticks": diag.get("total_ticks", 0),
            "total_bars": diag.get("total_bars", 0),
            "on_bar_calls": diag.get("on_bar_calls", 0),
            "signal_count": diag.get("signal_count", 0),
            "last_bar_time": str(diag["last_bar_time"]) if diag.get("last_bar_time") else None,
            "current_price": diag.get("current_price"),
        }

    def send_heartbeat(self):
        endpoint = f"{self.mother_url}/api/Grid/workers/heartbeat"
        payload = self._build_heartbeat_payload()
        try:
            resp = requests.post(endpoint, json=payload, timeout=10)
            data = resp.json()
            status = "REGISTERED" if data.get("registered") else "OK"
            print(f"[HEARTBEAT] {status} | worker={self.worker_id}")
        except requests.exceptions.ConnectionError:
            print(f"[WARNING] Could not reach Mother Server at {self.mother_url}")
        except Exception as e:
            print(f"[ERROR] Heartbeat: {type(e).__name__}: {e}")

    # ── Command Polling ─────────────────────────────────────

    def poll_commands(self):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/commands/poll"
        try:
            resp = requests.get(endpoint, timeout=10)
            data = resp.json()
            commands = data.get("commands", [])
            for cmd in commands:
                self._handle_command(cmd)
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            print(f"[ERROR] Command poll: {type(e).__name__}: {e}")

    def _handle_command(self, cmd: dict):
        cmd_type = cmd.get("command_type")
        cmd_id = cmd.get("command_id")
        payload = cmd.get("payload", {})
        print(f"[COMMAND] Received: {cmd_type} ({cmd_id})")
        self._ack_command(cmd_id)

        if cmd_type == "deploy_strategy":
            self._handle_deploy(payload)
        elif cmd_type == "stop_strategy":
            self._handle_stop(payload)
        else:
            print(f"[COMMAND] Unknown command type: {cmd_type}")

    def _ack_command(self, command_id: str):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/commands/ack"
        try:
            requests.post(endpoint, json={"command_id": command_id}, timeout=10)
            print(f"[COMMAND] Ack sent: {command_id}")
        except Exception as e:
            print(f"[ERROR] Ack failed: {e}")

    def _report_runner_status(self, status: dict):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/runner-status"
        try:
            requests.post(endpoint, json=status, timeout=10)
        except Exception as e:
            print(f"[ERROR] Runner status report failed: {e}")

    # ── Deploy / Stop ───────────────────────────────────────

    def _handle_deploy(self, payload: dict):
        with self._runner_lock:
            if self._runner:
                print("[RUNNER] Stopping existing runner before new deployment.")
                self._runner.stop()
                self._runner = None

            runner = StrategyRunner(
                deployment_config=payload,
                status_callback=self._report_runner_status,
            )
            self._runner = runner
            runner.start()

    def _handle_stop(self, payload: dict):
        with self._runner_lock:
            if self._runner:
                dep_id = payload.get("deployment_id")
                if dep_id and self._runner.deployment_id != dep_id:
                    print(f"[COMMAND] Stop ignored — deployment_id mismatch.")
                    return
                self._runner.stop()
                self._runner = None
                print(f"[RUNNER] Stopped deployment {dep_id}")
            else:
                print("[COMMAND] Stop received but no active runner.")

    # ── Main Loop ───────────────────────────────────────────

    def run(self):
        print("")
        print("=" * 56)
        print("  JINNI Grid Worker Agent")
        print("=" * 56)
        print(f"  Worker ID:    {self.worker_id}")
        print(f"  Worker Name:  {self.worker_name}")
        print(f"  Host:         {self.host}")
        print(f"  Mother URL:   {self.mother_url}")
        print(f"  Heartbeat:    {self.heartbeat_interval}s")
        print(f"  Agent:        v{self.agent_version}")
        print("=" * 56)
        print("")

        try:
            while True:
                self.send_heartbeat()
                self.poll_commands()
                time.sleep(self.heartbeat_interval)

        except KeyboardInterrupt:
            print("")
            print(f"[SHUTDOWN] Stopping worker agent '{self.worker_id}'...")
            with self._runner_lock:
                if self._runner:
                    self._runner.stop()
            sys.exit(0)


def main():
    config = load_config()
    agent = WorkerAgent(config)
    agent.run()


if __name__ == "__main__":
    main()
```
