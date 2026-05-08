# Repository Snapshot - Part 2 of 3


- Total files indexed: `26`
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

## Files In This Chunk - Part 2

```text
app/config.py
app/persistence.py
README.md
ui/index.html
ui/js/workerDetailRenderer.js
worker/portfolio.py
worker/worker_agent.py
```

## File Contents


---

## FILE: `app/config.py`

- Relative path: `app/config.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/config.py`
- Size bytes: `1591`
- SHA256: `6debd6140b1d072631fd805292dc2789e5737960aff5c78bd80a954b013e537a`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Configuration Loader
Reads config.yaml from project root. Falls back to safe defaults.
app/config.py
"""
import os, yaml

_config_cache = None

_DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": 5100, "debug": False, "cors_origins": ["*"]},
    "app": {"name": "JINNI Grid Mother Server", "version": "0.2.0"},
    "fleet": {"stale_threshold_seconds": 30, "offline_threshold_seconds": 90},
}


def _load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    config_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(config_dir)
    config_path = os.path.join(project_root, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
        print(f"[CONFIG] Loaded config from: {config_path}")
    else:
        print(f"[CONFIG] WARNING: config.yaml not found at {config_path}")
        print("[CONFIG] Using fallback defaults.")
        _config_cache = _DEFAULTS
    return _config_cache


class Config:
    @classmethod
    def get_server_config(cls) -> dict:
        return _load_config().get("server", _DEFAULTS["server"])

    @classmethod
    def get_app_config(cls) -> dict:
        return _load_config().get("app", _DEFAULTS["app"])

    @classmethod
    def get_cors_origins(cls) -> list:
        return cls.get_server_config().get("cors_origins", ["*"])

    @classmethod
    def get_fleet_config(cls) -> dict:
        return _load_config().get("fleet", _DEFAULTS["fleet"])
```

---

## FILE: `app/persistence.py`

- Relative path: `app/persistence.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/persistence.py`
- Size bytes: `14191`
- SHA256: `5461e9fd022ab7eea01eb7fad52045cd3effc76b969056e2b1f12424564a1166`
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
```

---

## FILE: `README.md`

- Relative path: `README.md`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/README.md`
- Size bytes: `5209`
- SHA256: `ed4bd32e218906fdf60ab14ecafc02d8a70ec0ecd6c6f0b36a3a1d0e8bedcb02`
- Guessed MIME type: `text/markdown`
- Guessed encoding: `unknown`

````markdown
# JINNI Grid — Distributed Live Trading Dashboard

## Phase 1B Update — Integrated Mother Server + Worker Heartbeat System

### Overview

JINNI Grid is a distributed live trading system. The Mother Server monitors worker VMs running trading systems. This phase implements the foundational heartbeat/fleet system with a professional dashboard UI.

### What's Implemented

- **Mother Server** — FastAPI backend serving the dashboard UI and fleet API
- **Real Worker Heartbeat** — `POST /api/Grid/workers/heartbeat` endpoint
- **In-Memory Worker Registry** — Tracks workers with freshness/stale logic
- **Fleet API** — `GET /api/Grid/workers` returns real connected worker data
- **Dashboard** — Professional dark-themed UI with portfolio overview (mock) and fleet overview (live from API)
- **Fleet Management Page** — Full fleet page with worker cards, auto-refresh, loading/empty/error states
- **Worker Agent** — Standalone script for worker VMs to send heartbeats
- **Theme System** — Dark/light mode with localStorage persistence
- **Config-Driven** — Host, port, CORS, fleet thresholds all from `config.yaml`

### What's NOT Implemented

- No MT5 connectivity
- No strategy deployment or management
- No trading execution
- No backtesting
- No database (in-memory only, lost on restart)
- No authentication
- No WebSocket
- No Docker/Gridrnetes

---

### Quick Start

#### 1. Start Mother Server

```bash
cd jinni-Grid
pip install -r requirements.txt
python main.py
```

Open `http://<mother-ip>:5100` in your browser.

#### 2. Start Worker Agent

On a worker machine (or same machine for testing):

```bash
cd jinni-Grid/worker
pip install -r requirements.txt
# Edit config.yaml — set mother_server.url to your Mother Server IP:port
python worker_agent.py
```

The worker will appear in the Fleet page within seconds.

---

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard UI |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/Grid/workers/heartbeat` | Worker heartbeat |
| `GET` | `/api/Grid/workers` | Fleet worker list + summary |
| `GET` | `/api/portfolio/summary` | Portfolio summary (mock) |
| `GET` | `/api/portfolio/equity-history` | Equity curve (mock) |
| `GET` | `/api/system/summary` | System summary |
| `GET` | `/docs` | Swagger UI |

---

### Project Structure

```
jinni-Grid/
  main.py                     Entry point
  config.yaml                 Server + fleet configuration
  requirements.txt            Python dependencies
  README.md                   This file
  app/
    __init__.py               App factory (FastAPI + static files + routes)
    config.py                 Config loader
    routes/
      health.py               GET /api/health
      Grid.py                 POST heartbeat + GET workers
      portfolio.py            Portfolio endpoints (mock)
      system.py               System summary
    services/
      mock_data.py            Portfolio + equity mock data
      worker_registry.py      In-memory worker state store
  ui/
    index.html                Dashboard HTML
    css/
      theme.css               Dark/light theme variables
      base.css                Reset + utilities
      layout.css              Sidebar + topbar + content
      dashboard.css           All component styles
    js/
      mockData.js             Portfolio + equity (client-side mock)
      apiClient.js            API fetch wrapper
      themeManager.js         Dark/light toggle
      dashboardRenderer.js    Dashboard page renderer
      fleetRenderer.js        Fleet page renderer
      app.js                  Navigation + clock + init
  worker/
    worker_agent.py           Heartbeat sender script
    config.yaml               Worker configuration
    requirements.txt          Worker dependencies
    README.md                 Worker setup docs
```

---

### Configuration

#### Mother Server (`config.yaml`)

```yaml
server:
  host: "0.0.0.0"              # Bind to all interfaces
  port: 5100                    # Server port
  debug: true                   # Auto-reload on changes
  cors_origins: ["*"]           # Allowed CORS origins

app:
  name: "JINNI Grid Mother Server"
  version: "0.2.0"

fleet:
  stale_threshold_seconds: 30   # Mark worker stale after 30s
  offline_threshold_seconds: 90 # Mark worker offline after 90s
```

#### Worker (`worker/config.yaml`)

```yaml
worker:
  worker_id: "vm-worker-01"
  worker_name: "Worker 01"
mother_server:
  url: "http://192.168.1.100:5100"
heartbeat:
  interval_seconds: 5
agent:
  version: "0.1.0"
```

---

### Fleet Freshness Logic

| Heartbeat Age | Effective State |
|---------------|-----------------|
| < 30 seconds | Worker's reported state (online/running/etc.) |
| 30 - 89 seconds | **Stale** |
| >= 90 seconds | **Offline** |

Thresholds are configurable in `config.yaml` under `fleet`.

---

### Notes

- All fleet data is **real** — driven by actual worker heartbeats
- Portfolio data is still **mock** — will be connected to real accounts later
- Worker registry is **in-memory only** — cleared on server restart
- The server binds to `0.0.0.0` — accessible from other machines on the same network
````

---

## FILE: `ui/index.html`

- Relative path: `ui/index.html`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/index.html`
- Size bytes: `2855`
- SHA256: `b6a9f968c712014a811b81f91b6de7d989b8d9c1173cc972e3136b527afb57cb`
- Guessed MIME type: `text/html`
- Guessed encoding: `unknown`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>JINNI GRID — Mother Server Dashboard</title>

  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
    rel="stylesheet"
  />

  <!-- Font Awesome -->
  <link
    rel="stylesheet"
    href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"
  />

  <!-- CSS -->
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

      <a href="#" class="nav-item" data-page="worker-detail">
        <i class="fa-solid fa-microchip"></i><span>Worker Detail</span>
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

  <!-- JS -->
  <script src="/js/main.js"></script>
  <script src="/js/workerDetailRenderer.js"></script>
</body>
</html>
```

---

## FILE: `ui/js/workerDetailRenderer.js`

- Relative path: `ui/js/workerDetailRenderer.js`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/js/workerDetailRenderer.js`
- Size bytes: `39694`
- SHA256: `58cf3245e875a7e0b7456297bb0af5a9177d75586b6728036d7e67e7f9e96b7e`
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

    var pipelineVal =
      '<span style="color:var(--accent);">' + _fmtNum(ticks) + '</span> ticks \u2192 ' +
      '<span style="color:var(--warning);">' + _fmtNum(bars) + '</span> bars \u2192 ' +
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
          '<span>Strategy: <strong class="mono">' + d.strategy_id + '</strong></span>' +
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
        var val = input.type === 'checkbox' ? input.checked : parseFloat(input.value);
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
          _renderStrategyMeta();
          _loadParamsFromSchema();
          _updateChecklist();
          _addActivity('Strategy selected: ' + sid);
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
