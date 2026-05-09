# Repository Snapshot - Part 3 of 4

- Root folder: `/home/hurairahengg/Documents/JinniGrid`
- you knwo my whole jinni grid systeM/ basically it is thereliek a kubernetes server setup what it does is basically a mother server with ui and bunch of lank state VMs. the vms run a speacial typa of renko style bars not normal timeframe u will get more context in the codes but yeha and we can uipload strategy codes though mother ui and it wiill run strategy mt5 report and ecetra ecetra. currently im done coding the strategy system but its not tested yet an have confrimed bugs. so firm i wil ldrop u my whole project codebases from my readme. understand each code its role and keep in ur context i will give u big promtps to update code later duinerstood
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

## Files In This Chunk - Part 3

```text
app/logging_config.py
app/services/strategy_registry.py
config.yaml
README.md
ui/js/workerDetailRenderer.js
worker/requirements.txt
worker/strategyWorker.py
```

## File Contents


---

## FILE: `app/logging_config.py`

- Relative path: `app/logging_config.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/logging_config.py`
- Size bytes: `3530`
- SHA256: `ff7cac1c67b36adeba88e19115556a640f6bd6327864d5f072936a452e5bf07c`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
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
```

---

## FILE: `app/services/strategy_registry.py`

- Relative path: `app/services/strategy_registry.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/services/strategy_registry.py`
- Size bytes: `10796`
- SHA256: `109eff2fc4083c77d8c034935b5b2f366813c48060d8eabd527bb33a6d81d650`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid — Strategy Registry (DB-backed)
app/services/strategy_registry.py

Strategies are stored:
  - Source code: data/strategies/{strategy_id}.py (filesystem)
  - Metadata: SQLite via app/persistence.py
"""

import ast
import hashlib
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from app.persistence import (
    save_strategy, get_all_strategies_db, get_strategy_db,
    delete_strategy_db, log_event_db,
)

log = logging.getLogger("jinni.strategy")

STRATEGY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "strategies"
)

_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(STRATEGY_DIR, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))
    return safe or "unnamed_strategy"


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

def _safe_eval_node(node):
    """
    Safely evaluate an AST node to a Python literal.
    Handles: str, int, float, bool, None, dict, list, tuple, set.
    Returns None if the node cannot be safely evaluated.
    """
    try:
        # ast.literal_eval on the source representation
        source = ast.unparse(node)
        return ast.literal_eval(source)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return None

def _extract_strategy_class(source: str) -> Optional[dict]:
    """Parse source to find a class extending BaseStrategy."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        log.warning(f"Strategy syntax error: {e}")
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr
            if base_name == "BaseStrategy":
                info = {"class_name": node.name}
                for item in node.body:
                    # Class-level simple assignments: strategy_id = "xyz"
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if not isinstance(target, ast.Name):
                                continue
                            val = _safe_eval_node(item.value)
                            if val is not None:
                                info[target.id] = val
                    # Class-level annotated assignments: strategy_id: str = "xyz"
                    elif isinstance(item, ast.AnnAssign):
                        if (isinstance(item.target, ast.Name)
                                and item.value is not None):
                            val = _safe_eval_node(item.value)
                            if val is not None:
                                info[item.target.id] = val
                log.info(f"Extracted strategy class: {node.name} fields={list(info.keys())}")
                return info

    # Log what classes WERE found for debugging
    classes_found = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if classes_found:
        log.warning(f"Found classes {classes_found} but none extend BaseStrategy")
    else:
        log.warning("No classes found in strategy source at all")
    return None


# =============================================================================
# Public API
# =============================================================================

def upload_strategy(filename: str, source_code: str) -> dict:
    """Upload and persist a strategy file."""
    _ensure_dir()

    # Check syntax first
    try:
        ast.parse(source_code)
    except SyntaxError as e:
        return {
            "ok": False,
            "error": f"Python syntax error at line {e.lineno}: {e.msg}",
        }

    info = _extract_strategy_class(source_code)
    if info is None:
        # Give a detailed error
        try:
            tree = ast.parse(source_code)
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        except Exception:
            classes = []
        if classes:
            return {
                "ok": False,
                "error": f"Found classes {classes} but none extend BaseStrategy. "
                         f"Your class must inherit from BaseStrategy.",
            }
        return {
            "ok": False,
            "error": "No class found in file. Strategy must contain a class extending BaseStrategy.",
        }

    strategy_id = info.get("strategy_id", "")
    if not strategy_id:
        strategy_id = info["class_name"].lower()

    class_name = info["class_name"]
    name = info.get("name", class_name)
    description = info.get("description", "")
    version = info.get("version", "1.0")
    min_lookback = info.get("min_lookback", 0)
    parameters = info.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}

    safe_name = _sanitize_filename(strategy_id)
    file_path = os.path.join(STRATEGY_DIR, f"{safe_name}.py")
    fhash = _file_hash(source_code)

    # Atomic write
    tmp_path = file_path + ".tmp"
    with _lock:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(source_code)
            os.replace(tmp_path, file_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return {"ok": False, "error": f"File write failed: {e}"}

    now = datetime.now(timezone.utc).isoformat()

    # Persist metadata to DB
    save_strategy(strategy_id, {
        "filename": filename,
        "class_name": class_name,
        "name": name,
        "description": description,
        "version": version,
        "min_lookback": min_lookback,
        "file_hash": fhash,
        "file_path": file_path,
        "parameters": parameters,
        "uploaded_at": now,
        "is_valid": True,
    })

    log.info(f"Strategy uploaded: {strategy_id} ({class_name}) hash={fhash}")

    log_event_db("strategy", "uploaded",
                 f"Strategy {strategy_id} uploaded from {filename}",
                 strategy_id=strategy_id,
                 data={"class_name": class_name, "version": version, "hash": fhash})

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "class_name": class_name,
        "name": name,
        "version": version,
        "file_hash": fhash,
    }


def get_all_strategies() -> list:
    """Return all valid strategies from DB."""
    db_strategies = get_all_strategies_db()
    result = []
    for s in db_strategies:
        params = s.get("parameters", {})
        if isinstance(params, str):
            try:
                import json
                params = json.loads(params)
            except Exception:
                params = {}
        result.append({
            "strategy_id": s["strategy_id"],
            "strategy_name": s.get("name", s["strategy_id"]),
            "name": s.get("name", s["strategy_id"]),
            "filename": s.get("filename", ""),
            "class_name": s.get("class_name", ""),
            "description": s.get("description", ""),
            "version": s.get("version", ""),
            "min_lookback": s.get("min_lookback", 0),
            "file_hash": s.get("file_hash", ""),
            "uploaded_at": s.get("uploaded_at", ""),
            "validation_status": "validated" if s.get("is_valid") else "invalid",
            "parameter_count": len(params) if isinstance(params, dict) else 0,
            "parameters": params,
            "error": None,
        })
    return result


def get_strategy(strategy_id: str) -> Optional[dict]:
    return get_strategy_db(strategy_id)


def get_strategy_file_content(strategy_id: str) -> Optional[str]:
    """Read strategy source code from disk."""
    rec = get_strategy_db(strategy_id)
    if not rec:
        return None

    file_path = rec.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        # Try default path
        safe_name = _sanitize_filename(strategy_id)
        file_path = os.path.join(STRATEGY_DIR, f"{safe_name}.py")

    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def validate_strategy(strategy_id: str) -> dict:
    content = get_strategy_file_content(strategy_id)
    if content is None:
        return {"ok": False, "error": "Strategy file not found."}

    info = _extract_strategy_class(content)
    if info is None:
        return {"ok": False, "error": "No BaseStrategy class found in file."}

    try:
        compile(content, f"{strategy_id}.py", "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"Syntax error: {e}"}

    log_event_db("strategy", "validated",
                 f"Strategy {strategy_id} passed validation",
                 strategy_id=strategy_id)

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "class_name": info["class_name"],
        "valid": True,
    }


def load_strategies_from_disk():
    """Scan data/strategies/ for .py files and register any not already in DB."""
    _ensure_dir()
    count = 0

    for fname in os.listdir(STRATEGY_DIR):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(STRATEGY_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception:
            continue

        info = _extract_strategy_class(source)
        if info is None:
            continue

        strategy_id = info.get("strategy_id", "")
        if not strategy_id:
            strategy_id = info["class_name"].lower()

        # Check if already in DB
        existing = get_strategy_db(strategy_id)
        if existing:
            continue

        save_strategy(strategy_id, {
            "filename": fname,
            "class_name": info["class_name"],
            "name": info.get("name", info["class_name"]),
            "description": info.get("description", ""),
            "version": info.get("version", "1.0"),
            "min_lookback": info.get("min_lookback", 0),
            "file_hash": _file_hash(source),
            "file_path": fpath,
            "parameters": info.get("parameters", {}),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "is_valid": True,
        })
        count += 1

    if count > 0:
        log.info(f"Loaded {count} strategies from disk into DB")
```

---

## FILE: `config.yaml`

- Relative path: `config.yaml`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/config.yaml`
- Size bytes: `215`
- SHA256: `9039bd9eac4b71db0e39e29e0cee3b35ba952ba108ebbd604db1570561efc855`
- Guessed MIME type: `application/yaml`
- Guessed encoding: `unknown`

```yaml
server:
  host: "192.168.3.232"
  port: 5100
  debug: true
  cors_origins:
    - "*"

app:
  name: "JINNI Grid Mother Server"
  version: "0.2.0"

fleet:
  stale_threshold_seconds: 30
  offline_threshold_seconds: 90
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

## FILE: `ui/js/workerDetailRenderer.js`

- Relative path: `ui/js/workerDetailRenderer.js`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/js/workerDetailRenderer.js`
- Size bytes: `41744`
- SHA256: `c16202a61f1f2cc1e9a3028821660e16b0ccc95ce0436b8b2748d1b0e6af8c5c`
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
                // Merge parameters from detail into selected
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

## FILE: `worker/requirements.txt`

- Relative path: `worker/requirements.txt`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/requirements.txt`
- Size bytes: `48`
- SHA256: `7a58cbea9db5d6fbf9c1ea4bc53a1363984cef617cc862e83bc855137186f9fc`
- Guessed MIME type: `text/plain`
- Guessed encoding: `unknown`

```text
pyyaml>=6.0
requests>=2.31.0
MetaTrader5>=5.0.45
```

---

## FILE: `worker/strategyWorker.py`

- Relative path: `worker/strategyWorker.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/strategyWorker.py`
- Size bytes: `46091`
- SHA256: `106d42794021f754d383e7e6e3042990c4a3456cf55815b3afca1f965165186c`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID — Combined Worker Runtime
worker/strategyWorker.py

Uses:
  worker/indicators.py  — HMA/WMA/SMA/EMA precompute + IndicatorEngine
  worker/execution.py   — ExecutionLogger, MT5Executor, signal validation,
                           SL/TP computation, trade records, PositionState
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import threading
import time
import traceback
import types
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from worker.indicators import IndicatorEngine, precompute_indicator_series
from worker.execution import (
    SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE,
    SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT, VALID_SIGNALS,
    PositionState, ExecutionLogger, MT5Executor,
    validate_signal, compute_sl, compute_tp, build_trade_record,
)


# =============================================================================
# Strategy Base Class
# =============================================================================

class BaseStrategy(ABC):
    strategy_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0"
    min_lookback: int = 0

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id, "name": self.name or self.strategy_id,
            "description": self.description or "", "version": self.version,
            "min_lookback": self.min_lookback,
            "parameters": self.get_parameter_schema(),
        }

    def get_parameter_schema(self) -> Dict[str, Any]:
        return getattr(self, "parameters", {})

    def get_default_parameters(self) -> Dict[str, Any]:
        schema = self.get_parameter_schema()
        defaults = {}
        for key, spec in schema.items():
            if isinstance(spec, dict) and "default" in spec:
                defaults[key] = spec["default"]
        return defaults

    def validate_parameters(self, raw_params: Dict[str, Any]) -> Dict[str, Any]:
        params = dict(self.get_default_parameters())
        for key, value in (raw_params or {}).items():
            params[key] = value
        return params

    def build_indicators(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def on_init(self, ctx: Any) -> None:
        pass

    def on_end(self, ctx: Any) -> None:
        pass

    @abstractmethod
    def on_bar(self, ctx: Any) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Strategy must implement on_bar()")


# =============================================================================
# Strategy Context
# =============================================================================

class StrategyContext:
    def __init__(self, bars: list, params: dict,
                 position: Optional[PositionState] = None):
        self._bars = bars
        self._params = params
        self._position = position or PositionState()
        self._index: int = 0
        self._trades: list = []
        self._equity: float = 0.0
        self._balance: float = 0.0
        self._indicators: dict = {}
        self._ind_series: dict = {}
        self.state: dict = {}

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, val: int):
        self._index = val

    @property
    def bar(self) -> dict:
        if 0 <= self._index < len(self._bars):
            return self._bars[self._index]
        return {}

    @property
    def bars(self) -> list:
        return self._bars

    @property
    def indicators(self) -> dict:
        return self._indicators

    @property
    def ind_series(self) -> dict:
        return self._ind_series

    @property
    def position(self) -> PositionState:
        return self._position

    @position.setter
    def position(self, val: PositionState):
        self._position = val

    @property
    def params(self) -> dict:
        return self._params

    @property
    def trades(self) -> list:
        return self._trades

    @property
    def equity(self) -> float:
        return self._equity

    @equity.setter
    def equity(self, val: float):
        self._equity = val

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, val: float):
        self._balance = val


# =============================================================================
# Range Bar Engine
# =============================================================================

def _make_bar(time_: int, open_: float, high_: float, low_: float,
              close_: float, volume_: float) -> dict:
    return {
        "time": int(time_), "open": round(open_, 5), "high": round(high_, 5),
        "low": round(low_, 5), "close": round(close_, 5),
        "volume": round(volume_, 2),
    }


class RangeBarEngine:
    def __init__(self, bar_size_points: float, max_bars: int = 500,
                 on_bar: Optional[Callable[[dict], None]] = None):
        self.range_size = float(bar_size_points)
        self.max_bars = max_bars
        self._on_bar = on_bar
        self.trend = 0
        self.bar: Optional[dict] = None
        self.bars: deque = deque(maxlen=max_bars)
        self._last_emitted_ts: Optional[int] = None
        self.total_ticks = 0
        self.total_bars_emitted = 0

    @property
    def current_bars_count(self) -> int:
        return len(self.bars)

    def _emit(self, bar_dict: dict) -> None:
        ts = int(bar_dict["time"])
        if self._last_emitted_ts is not None and ts <= self._last_emitted_ts:
            ts = self._last_emitted_ts + 1
        bar_dict["time"] = ts
        self._last_emitted_ts = ts
        self.bars.append(bar_dict)
        self.total_bars_emitted += 1
        if self._on_bar:
            self._on_bar(bar_dict)

    def _start_bar(self, ts: int, price: float, volume: float) -> None:
        self.bar = {"time": ts, "open": price, "high": price,
                    "low": price, "close": price, "volume": volume}

    def process_tick(self, ts: int, price: float, volume: float = 0.0) -> None:
        self.total_ticks += 1
        if self.bar is None:
            self._start_bar(ts, price, volume)
            return
        p, rs = price, self.range_size
        self.bar["volume"] += volume

        while True:
            o = self.bar["open"]
            if self.trend == 0:
                up_t, dn_t = o + rs, o - rs
                if p >= up_t:
                    self.bar["high"] = max(self.bar["high"], up_t)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = up_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.trend = 1
                    self.bar = {"time": ts, "open": up_t, "high": up_t,
                                "low": up_t, "close": up_t, "volume": 0.0}
                    continue
                if p <= dn_t:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], dn_t)
                    self.bar["close"] = dn_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.trend = -1
                    self.bar = {"time": ts, "open": dn_t, "high": dn_t,
                                "low": dn_t, "close": dn_t, "volume": 0.0}
                    continue
                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break
            if self.trend == 1:
                cont_t, rev_t = o + rs, o - (2 * rs)
                if p >= cont_t:
                    self.bar["high"] = max(self.bar["high"], cont_t)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = cont_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.bar = {"time": ts, "open": cont_t, "high": cont_t,
                                "low": cont_t, "close": cont_t, "volume": 0.0}
                    continue
                if p <= rev_t:
                    ro, rc = o - rs, o - (2 * rs)
                    h_ = max(self.bar["high"], o)
                    l_ = min(self.bar["low"], rc)
                    self._emit(_make_bar(self.bar["time"], ro, h_, l_, rc,
                               self.bar["volume"]))
                    self.trend = -1
                    self.bar = {"time": ts, "open": rc, "high": rc,
                                "low": rc, "close": rc, "volume": 0.0}
                    continue
                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break
            if self.trend == -1:
                cont_t, rev_t = o - rs, o + (2 * rs)
                if p <= cont_t:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], cont_t)
                    self.bar["close"] = cont_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.bar = {"time": ts, "open": cont_t, "high": cont_t,
                                "low": cont_t, "close": cont_t, "volume": 0.0}
                    continue
                if p >= rev_t:
                    ro, rc = o + rs, o + (2 * rs)
                    h_ = max(self.bar["high"], rc)
                    l_ = min(self.bar["low"], o)
                    self._emit(_make_bar(self.bar["time"], ro, h_, l_, rc,
                               self.bar["volume"]))
                    self.trend = 1
                    self.bar = {"time": ts, "open": rc, "high": rc,
                                "low": rc, "close": rc, "volume": 0.0}
                    continue
                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break

    def reset(self) -> None:
        self.trend = 0
        self.bar = None
        self.bars.clear()
        self._last_emitted_ts = None
        self.total_ticks = 0
        self.total_bars_emitted = 0


# =============================================================================
# MT5 Tick Normalizer + Connector
# =============================================================================

def _tick_field(raw, field: str, default: float = 0.0) -> float:
    try:
        return float(raw[field])
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    try:
        return float(getattr(raw, field))
    except (AttributeError, TypeError, ValueError):
        pass
    return default


def normalize_tick(raw) -> Optional[dict]:
    ts_val = _tick_field(raw, "time", -1.0)
    if ts_val < 0:
        return None
    ts = int(ts_val)
    time_msc_val = _tick_field(raw, "time_msc", -1.0)
    time_msc = int(time_msc_val) if time_msc_val >= 0 else ts * 1000
    bid = _tick_field(raw, "bid", 0.0)
    ask = _tick_field(raw, "ask", 0.0)
    last = _tick_field(raw, "last", 0.0)
    volume = _tick_field(raw, "volume", 0.0)
    price = bid if bid > 0 else (last if last > 0 else ask)
    if price <= 0:
        return None
    return {"ts": ts, "time_msc": time_msc, "price": price,
            "bid": bid, "ask": ask, "last": last, "volume": volume}


def _import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


def init_mt5() -> Tuple[bool, str]:
    mt5 = _import_mt5()
    if mt5 is None:
        return False, "MetaTrader5 package not installed."
    if not mt5.initialize():
        return False, f"MT5 initialize() failed: {mt5.last_error()}"
    info = mt5.terminal_info()
    if info is None:
        return False, "MT5 terminal_info() returned None."
    account = mt5.account_info()
    acct_str = f" | account={account.login} broker={account.company}" if account else ""
    print(f"[MT5] Connected: {info.name}{acct_str}")
    return True, "ok"


def shutdown_mt5() -> None:
    mt5 = _import_mt5()
    if mt5:
        mt5.shutdown()


def get_mt5_account_info() -> Optional[dict]:
    mt5 = _import_mt5()
    if mt5 is None:
        return None
    account = mt5.account_info()
    if account is None:
        return None
    terminal = mt5.terminal_info()
    return {
        "login": str(account.login),
        "broker": str(account.company) if account.company else None,
        "server": str(account.server) if account.server else None,
        "balance": float(account.balance),
        "equity": float(account.equity),
        "terminal": str(terminal.name) if terminal else None,
    }


def fetch_historical_ticks(symbol, lookback_value, lookback_unit):
    mt5 = _import_mt5()
    if mt5 is None:
        return None, "MetaTrader5 package not installed."
    now = datetime.now(timezone.utc)
    if lookback_unit == "minutes":
        from_time = now - timedelta(minutes=lookback_value)
    elif lookback_unit == "hours":
        from_time = now - timedelta(hours=lookback_value)
    elif lookback_unit == "days":
        from_time = now - timedelta(days=lookback_value)
    else:
        return None, f"Invalid lookback_unit: {lookback_unit}"
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return None, f"Symbol '{symbol}' not found in MT5."
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            return None, f"Failed to enable symbol '{symbol}' in MT5."
    print(f"[MT5] Fetching ticks: {symbol} from {from_time.isoformat()}")
    ticks = mt5.copy_ticks_range(symbol, from_time, now, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        return None, f"No ticks for {symbol}. MT5 error: {mt5.last_error()}"
    result, skipped = [], 0
    for raw_tick in ticks:
        n = normalize_tick(raw_tick)
        if n is None:
            skipped += 1
            continue
        result.append({"ts": n["ts"], "price": n["price"], "volume": n["volume"]})
    if not result:
        return None, f"All {len(ticks)} ticks had no valid price."
    print(f"[MT5] Got {len(result)} ticks for {symbol} (skipped {skipped})")
    return result, "ok"


def stream_live_ticks(symbol, poll_interval=0.05):
    mt5 = _import_mt5()
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed.")
    cursor_time = datetime.now(timezone.utc)
    last_tick_msc = 0
    while True:
        ticks = mt5.copy_ticks_from(symbol, cursor_time, 1000, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            for raw_tick in ticks:
                n = normalize_tick(raw_tick)
                if n is None:
                    continue
                if n["time_msc"] <= last_tick_msc:
                    continue
                last_tick_msc = n["time_msc"]
                yield {"ts": n["ts"], "price": n["price"], "volume": n["volume"]}
            last_ts = _tick_field(ticks[-1], "time", 0.0)
            if last_ts > 0:
                cursor_time = datetime.fromtimestamp(int(last_ts), tz=timezone.utc)
        time.sleep(poll_interval)


class _MT5ConnectorFacade:
    init_mt5 = staticmethod(init_mt5)
    shutdown_mt5 = staticmethod(shutdown_mt5)
    fetch_historical_ticks = staticmethod(fetch_historical_ticks)
    stream_live_ticks = staticmethod(stream_live_ticks)
    get_mt5_account_info = staticmethod(get_mt5_account_info)


mt5_connector = _MT5ConnectorFacade()


# =============================================================================
# Strategy Loader
# =============================================================================

def load_strategy_from_source(source_code: str, class_name: str,
                              strategy_id: str) -> Tuple[Optional[object], Optional[str]]:
    try:
        _ensure_base_importable()
    except Exception as exc:
        return None, f"Failed to prepare base imports: {exc}"

    module_name = f"jinni_strategy_{strategy_id}"
    try:
        tmp_dir = tempfile.mkdtemp(prefix="jinni_strat_")
        tmp_path = os.path.join(tmp_dir, f"{module_name}.py")
        with open(tmp_path, "w", encoding="utf-8") as file:
            file.write(source_code)
        spec = importlib.util.spec_from_file_location(module_name, tmp_path)
        if spec is None or spec.loader is None:
            return None, "Failed to create module spec."
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        klass = getattr(module, class_name, None)
        if klass is None:
            available = [k for k in dir(module) if not k.startswith("_")]
            return None, f"Class '{class_name}' not found. Available: {available}"
        instance = klass()
        if not hasattr(instance, "on_bar"):
            return None, f"Class '{class_name}' has no on_bar() method."
        print(f"[LOADER] Strategy loaded: {class_name} (id={strategy_id})")
        return instance, None
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[LOADER] Failed: {exc}\n{tb}")
        return None, f"{type(exc).__name__}: {exc}"


def _ensure_base_importable():
    current_module = sys.modules[__name__]
    sys.modules["base_strategy"] = current_module
    sys.modules["worker.base_strategy"] = current_module
    if "backend" not in sys.modules:
        bm = types.ModuleType("backend")
        bm.__path__ = []
        sys.modules["backend"] = bm
    if "backend.strategies" not in sys.modules:
        sm = types.ModuleType("backend.strategies")
        sm.__path__ = []
        sys.modules["backend.strategies"] = sm
    sys.modules["backend.strategies.base"] = current_module


# =============================================================================
# Strategy Runner
# =============================================================================

class StrategyRunner:
    def __init__(self, deployment_config: dict, status_callback=None):
        self.config = deployment_config
        self._status_callback = status_callback

        self.deployment_id: str = deployment_config["deployment_id"]
        self.strategy_id: str = deployment_config["strategy_id"]
        self.class_name: str = deployment_config.get("strategy_class_name", "")
        self.source_code: str = deployment_config.get("strategy_file_content", "")
        self.symbol: str = deployment_config["symbol"]
        self.tick_lookback_value: int = deployment_config.get("tick_lookback_value", 30)
        self.tick_lookback_unit: str = deployment_config.get("tick_lookback_unit", "minutes")
        self.bar_size_points: float = deployment_config["bar_size_points"]
        self.max_bars: int = deployment_config.get("max_bars_in_memory", 500)
        self.lot_size: float = deployment_config.get("lot_size", 0.01)
        self.strategy_parameters: dict = deployment_config.get("strategy_parameters") or {}

        self._strategy = None
        self._ctx: Optional[StrategyContext] = None
        self._bar_engine: Optional[RangeBarEngine] = None
        self._executor: Optional[MT5Executor] = None
        self._exec_log: Optional[ExecutionLogger] = None
        self._indicator_engine: Optional[IndicatorEngine] = None
        self._runner_state: str = "idle"
        self._last_signal: Optional[dict] = None
        self._last_error: Optional[str] = None
        self._started_at: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._bar_index: int = 0

        # MT5 info
        self._mt5_state: Optional[str] = None
        self._mt5_broker: Optional[str] = None
        self._mt5_account_id: Optional[str] = None
        self._mt5_server: Optional[str] = None
        self._mt5_balance: Optional[float] = None
        self._mt5_equity: Optional[float] = None

        # Pipeline counters
        self._total_ticks_ingested: int = 0
        self._total_bars_produced: int = 0
        self._on_bar_call_count: int = 0
        self._signal_count: int = 0
        self._warmup_signal_count: int = 0
        self._last_bar_time: Optional[int] = None
        self._current_price: Optional[float] = None
        self._trade_counter: int = 0

        # Active trade tracking (for MA-cross exit + trade records)
        self._active_trade_meta: Optional[dict] = None

    # ── Diagnostics ─────────────────────────────────────────

    def get_diagnostics(self) -> dict:
        exec_stats = self._exec_log.get_stats() if self._exec_log else {}
        open_count = self._executor.get_open_count() if self._executor else 0
        floating = self._executor.get_floating_pnl() if self._executor else 0.0

        if self._executor and self._executor._mt5:
            try:
                acct = self._executor._mt5.account_info()
                if acct:
                    self._mt5_balance = float(acct.balance)
                    self._mt5_equity = float(acct.equity)
            except Exception:
                pass

        return {
            "runner_state": self._runner_state,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "mt5_state": self._mt5_state,
            "broker": self._mt5_broker,
            "account_id": self._mt5_account_id,
            "mt5_server": self._mt5_server,
            "mt5_balance": self._mt5_balance,
            "mt5_equity": self._mt5_equity,
            "total_ticks": self._total_ticks_ingested,
            "total_bars": self._total_bars_produced,
            "current_bars_in_memory": (
                self._bar_engine.current_bars_count if self._bar_engine else 0
            ),
            "on_bar_calls": self._on_bar_call_count,
            "signal_count": self._signal_count,
            "warmup_signals": self._warmup_signal_count,
            "last_bar_time": self._last_bar_time,
            "current_price": self._current_price,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "open_positions_count": open_count,
            "floating_pnl": floating,
            "trade_count": self._trade_counter,
            **{f"exec_{k}": v for k, v in exec_stats.items()},
        }

    # ── Status Reporting ────────────────────────────────────

    def _report_status(self):
        if not self._status_callback:
            return
        status = {
            "deployment_id": self.deployment_id,
            "strategy_id": self.strategy_id,
            "strategy_name": getattr(self._strategy, "name", None) if self._strategy else None,
            "symbol": self.symbol,
            "runner_state": self._runner_state,
            "bar_size_points": self.bar_size_points,
            "max_bars_in_memory": self.max_bars,
            "current_bars_count": self._bar_engine.current_bars_count if self._bar_engine else 0,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        for attempt in range(3):
            try:
                self._status_callback(status)
                return
            except Exception as exc:
                print(f"[RUNNER] Status report attempt {attempt + 1}/3 failed: {exc}")
                if attempt < 2:
                    time.sleep(1.0)

    def _set_state(self, state: str, error: str = None):
        self._runner_state = state
        if error:
            self._last_error = error
        print(f"[RUNNER] {self.deployment_id} -> {state}"
              + (f" (error: {error})" if error else ""))
        self._report_status()

    # ── MT5 Info ────────────────────────────────────────────

    def _capture_mt5_info(self):
        info = mt5_connector.get_mt5_account_info()
        if info:
            self._mt5_state = "connected"
            self._mt5_broker = info.get("broker")
            self._mt5_account_id = info.get("login")
            self._mt5_server = info.get("server")
            self._mt5_balance = info.get("balance")
            self._mt5_equity = info.get("equity")
            print(f"[RUNNER] MT5 info: broker={self._mt5_broker} "
                  f"account={self._mt5_account_id} balance={self._mt5_balance}")
        else:
            self._mt5_state = "connected_no_account"

    # ── Position Refresh ────────────────────────────────────

    def _refresh_position(self):
        if self._executor:
            pos = self._executor.get_position_state()
            if self._active_trade_meta and pos.has_position:
                pos.entry_bar = self._active_trade_meta.get("entry_bar")
            self._ctx.position = pos

    # ── Pipeline Log ────────────────────────────────────────

    def _log_pipeline(self, label: str = ""):
        c = f" [{label}]" if label else ""
        exec_s = self._exec_log.get_stats() if self._exec_log else {}
        pos_n = self._executor.get_open_count() if self._executor else 0
        print(
            f"[PIPELINE]{c} dep={self.deployment_id} | "
            f"ticks={self._total_ticks_ingested} "
            f"bars={self._total_bars_produced} "
            f"on_bar={self._on_bar_call_count} "
            f"signals={self._signal_count} "
            f"buys={exec_s.get('buys_filled', 0)} "
            f"sells={exec_s.get('sells_filled', 0)} "
            f"closes={exec_s.get('closes_filled', 0)} "
            f"ma_exits={exec_s.get('ma_cross_exits', 0)} "
            f"positions={pos_n} "
            f"trades={self._trade_counter} "
            f"price={self._current_price}"
        )

    # ── MA-Cross Exit Check ─────────────────────────────────

    def _check_ma_cross_exit(self, bar: dict) -> bool:
        """
        Check if any engine-level MA cross exit triggers.
        Matches JINNI ZERO backtester _check_exit() MA cross logic.
        Returns True if a position was closed.
        """
        if not self._active_trade_meta:
            return False

        pos = self._ctx.position
        if not pos.has_position:
            return False

        close_price = float(bar.get("close", 0))
        direction = pos.direction

        # Check TP MA cross
        tp_ma_key = self._active_trade_meta.get("engine_tp_ma_key")
        if tp_ma_key:
            tp_ma_val = self._ctx.indicators.get(tp_ma_key)
            if tp_ma_val is not None:
                if direction == "long" and close_price < tp_ma_val:
                    self._exec_log.log_ma_cross_exit(tp_ma_key, direction,
                                                     tp_ma_val, close_price)
                    self._close_and_record("MA_TP_EXIT", bar)
                    return True
                if direction == "short" and close_price > tp_ma_val:
                    self._exec_log.log_ma_cross_exit(tp_ma_key, direction,
                                                     tp_ma_val, close_price)
                    self._close_and_record("MA_TP_EXIT", bar)
                    return True

        # Check SL MA cross
        sl_ma_key = self._active_trade_meta.get("engine_sl_ma_key")
        if sl_ma_key:
            sl_ma_val = self._ctx.indicators.get(sl_ma_key)
            if sl_ma_val is not None:
                if direction == "long" and close_price < sl_ma_val:
                    self._exec_log.log_ma_cross_exit(sl_ma_key, direction,
                                                     sl_ma_val, close_price)
                    self._close_and_record("MA_SL_EXIT", bar)
                    return True
                if direction == "short" and close_price > sl_ma_val:
                    self._exec_log.log_ma_cross_exit(sl_ma_key, direction,
                                                     sl_ma_val, close_price)
                    self._close_and_record("MA_SL_EXIT", bar)
                    return True

        return False

    # ── Close + Record Trade ────────────────────────────────

    def _close_and_record(self, reason: str, bar: dict):
        """Close all positions and write trade record to ctx._trades."""
        pos = self._ctx.position
        if not pos.has_position:
            return

        results = self._executor.close_all_positions()
        self._exec_log.log_close(results, reason=reason)

        # Build trade record
        meta = self._active_trade_meta or {}
        for r in results:
            if r.get("success"):
                self._trade_counter += 1
                record = build_trade_record(
                    trade_id=self._trade_counter,
                    direction=pos.direction or "long",
                    entry_price=pos.entry_price or 0,
                    entry_bar=meta.get("entry_bar", self._bar_index),
                    entry_time=meta.get("entry_time", bar.get("time", 0)),
                    exit_price=r.get("price", 0),
                    exit_bar=self._bar_index,
                    exit_time=bar.get("time", 0),
                    exit_reason=reason,
                    sl=pos.sl,
                    tp=pos.tp,
                    lot_size=pos.size or self.lot_size,
                    ticket=r.get("ticket"),
                    profit=r.get("profit", 0),
                )
                self._ctx._trades.append(record)
                print(f"[TRADE #{self._trade_counter}] {record['direction'].upper()} "
                      f"entry={record['entry_price']} exit={record['exit_price']} "
                      f"reason={reason} profit={record.get('profit', 0):.2f}")

        self._active_trade_meta = None
        self._refresh_position()

    # ── Bar Callback ────────────────────────────────────────

    def _on_new_bar(self, bar: dict):
        self._total_bars_produced += 1
        self._last_bar_time = bar.get("time")

        if self._stop_event.is_set():
            return
        if self._strategy is None or self._ctx is None:
            return

        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        self._ctx.index = len(bars_list) - 1
        self._bar_index = self._ctx.index

        # Update indicators
        if self._indicator_engine:
            self._indicator_engine.update(bars_list, self._ctx)

        # Refresh real position from MT5
        self._refresh_position()

        # Check engine-level MA cross exits BEFORE calling strategy
        if self._ctx.position.has_position:
            if self._check_ma_cross_exit(bar):
                # Position was closed by MA cross — strategy will see flat
                self._refresh_position()

        min_lb = getattr(self._strategy, "min_lookback", 0) or 0
        if self._ctx.index < min_lb:
            return

        self._on_bar_call_count += 1

        try:
            raw_signal = self._strategy.on_bar(self._ctx)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[RUNNER] on_bar() error: {exc}\n{tb}")
            self._set_state("failed", f"on_bar error: {type(exc).__name__}: {exc}")
            self._stop_event.set()
            return

        action = validate_signal(raw_signal, self._bar_index)
        self._handle_signal(action, bar)

        if self._on_bar_call_count % 50 == 0:
            self._log_pipeline("LIVE_BAR")

    # ── Signal Handling + Execution ─────────────────────────

    def _handle_signal(self, action: dict, bar: dict):
        sig = action.get("signal")
        if sig not in VALID_SIGNALS:
            return

        pos = self._ctx.position

        self._exec_log.log_signal(
            sig, self._bar_index, self._last_bar_time,
            self._current_price, pos,
        )

        # ── HOLD ────────────────────────────────────────
        if sig == SIGNAL_HOLD:
            self._exec_log.log_hold()
            if "update_sl" in action or "update_tp" in action:
                self._handle_modify(action)
            return

        # ── CLOSE variants ──────────────────────────────
        if sig == SIGNAL_CLOSE or action.get("close"):
            if not pos.has_position:
                self._exec_log.log_skip("CLOSE", "no position")
                return
            reason = action.get("close_reason", "strategy_close")
            self._close_and_record(reason, bar)
            self._signal_count += 1
            self._last_signal = action
            return

        if sig == SIGNAL_CLOSE_LONG:
            if not pos.has_position or pos.direction != "long":
                self._exec_log.log_skip("CLOSE_LONG", "no long position")
                return
            self._close_and_record("strategy_close_long", bar)
            self._signal_count += 1
            self._last_signal = action
            return

        if sig == SIGNAL_CLOSE_SHORT:
            if not pos.has_position or pos.direction != "short":
                self._exec_log.log_skip("CLOSE_SHORT", "no short position")
                return
            self._close_and_record("strategy_close_short", bar)
            self._signal_count += 1
            self._last_signal = action
            return

        # ── BUY / SELL ──────────────────────────────────
        if sig not in (SIGNAL_BUY, SIGNAL_SELL):
            return

        self._signal_count += 1
        self._last_signal = action
        direction = "long" if sig == SIGNAL_BUY else "short"

        # Already in same direction
        if pos.has_position and pos.direction == direction:
            self._exec_log.log_skip(sig, f"already {direction}")
            return

        # In opposite direction — close first
        if pos.has_position:
            self._close_and_record("reverse", bar)

        # Compute SL from signal (ma_snapshot, fixed, or direct)
        entry_estimate = self._current_price or float(bar.get("close", 0))
        sl_price = compute_sl(action, entry_estimate, direction)
        tp_price = compute_tp(action, entry_estimate, sl_price, direction)

        # Validate SL/TP sanity
        if sl_price is not None:
            if direction == "long" and sl_price >= entry_estimate:
                print(f"[EXEC] WARNING: Long SL {sl_price} >= entry {entry_estimate}, clearing SL")
                sl_price = None
            elif direction == "short" and sl_price <= entry_estimate:
                print(f"[EXEC] WARNING: Short SL {sl_price} <= entry {entry_estimate}, clearing SL")
                sl_price = None

        if tp_price is not None:
            if direction == "long" and tp_price <= entry_estimate:
                print(f"[EXEC] WARNING: Long TP {tp_price} <= entry {entry_estimate}, clearing TP")
                tp_price = None
            elif direction == "short" and tp_price >= entry_estimate:
                print(f"[EXEC] WARNING: Short TP {tp_price} >= entry {entry_estimate}, clearing TP")
                tp_price = None

        comment = action.get("comment", f"JG_{sig}")

        # Execute
        if sig == SIGNAL_BUY:
            result = self._executor.open_buy(sl=sl_price, tp=tp_price, comment=comment)
        else:
            result = self._executor.open_sell(sl=sl_price, tp=tp_price, comment=comment)

        self._exec_log.log_open(sig, result, sl_price, tp_price)

        if result.get("success"):
            fill_price = result.get("price", entry_estimate)

            # Recompute TP from actual fill price for R-multiple
            if action.get("tp_mode") == "r_multiple" and sl_price is not None:
                real_risk = abs(fill_price - sl_price)
                r = float(action.get("tp_r", 1.0))
                if real_risk > 0:
                    if direction == "long":
                        tp_price = round(fill_price + real_risk * r, 5)
                    else:
                        tp_price = round(fill_price - real_risk * r, 5)
                    # Modify TP on the position
                    mod_result = self._executor.modify_sl_tp(
                        result["ticket"], sl=sl_price, tp=tp_price
                    )
                    self._exec_log.log_modify(mod_result, sl=sl_price, tp=tp_price)

            # Store trade metadata for MA-cross exits + trade records
            self._active_trade_meta = {
                "entry_bar": self._bar_index,
                "entry_time": bar.get("time", 0),
                "entry_price": fill_price,
                "direction": direction,
                "sl": sl_price,
                "tp": tp_price,
                "ticket": result.get("ticket"),
                "engine_sl_ma_key": action.get("engine_sl_ma_key"),
                "engine_tp_ma_key": action.get("engine_tp_ma_key"),
            }

        self._refresh_position()
        self._report_status()

    def _handle_modify(self, action: dict):
        pos = self._ctx.position
        if not pos.has_position or not pos.ticket:
            self._exec_log.log_skip("MODIFY", "no position")
            return
        new_sl = action.get("update_sl")
        new_tp = action.get("update_tp")
        result = self._executor.modify_sl_tp(pos.ticket, sl=new_sl, tp=new_tp)
        self._exec_log.log_modify(result, sl=new_sl, tp=new_tp)
        self._refresh_position()

    # ── Lifecycle ───────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._set_state("stopped")
        if self._thread:
            self._thread.join(timeout=10)

    def _run(self):
        try:
            self._run_lifecycle()
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[RUNNER] FATAL: {self.deployment_id}:\n{tb}")
            self._set_state("failed", f"{type(exc).__name__}: {exc}")
            try:
                mt5_connector.shutdown_mt5()
            except Exception:
                pass

    def _run_lifecycle(self):
        self._started_at = datetime.now(timezone.utc).isoformat()

        # Phase 1: Load Strategy
        self._set_state("loading_strategy")
        strategy_instance, load_error = load_strategy_from_source(
            self.source_code, self.class_name, self.strategy_id,
        )
        if load_error:
            self._set_state("failed", f"Strategy load failed: {load_error}")
            return
        self._strategy = strategy_instance
        params = self._strategy.validate_parameters(self.strategy_parameters)
        self._ctx = StrategyContext(bars=[], params=params)

        # Build indicator engine from strategy declarations
        indicator_defs = self._strategy.build_indicators(params)
        self._indicator_engine = IndicatorEngine(indicator_defs)

        try:
            self._strategy.on_init(self._ctx)
        except Exception as exc:
            self._set_state("failed", f"on_init() failed: {type(exc).__name__}: {exc}")
            return
        print(f"[RUNNER] Strategy loaded: {self.class_name} | "
              f"min_lookback={getattr(self._strategy, 'min_lookback', 0)} | "
              f"indicators={len(indicator_defs)} | params={params}")

        # Phase 2: Init MT5
        ok, msg = mt5_connector.init_mt5()
        if not ok:
            self._set_state("failed", f"MT5 init failed: {msg}")
            return
        self._capture_mt5_info()

        # Phase 2b: Create executor + logger
        self._executor = MT5Executor(self.symbol, self.lot_size, self.deployment_id)
        self._exec_log = ExecutionLogger(self.deployment_id, self.symbol)

        # Phase 3: Fetch Historical Ticks
        self._set_state("fetching_ticks")
        ticks, tick_err = mt5_connector.fetch_historical_ticks(
            self.symbol, self.tick_lookback_value, self.tick_lookback_unit,
        )
        if ticks is None:
            self._set_state("failed", f"Tick fetch failed: {tick_err}")
            mt5_connector.shutdown_mt5()
            return
        if len(ticks) == 0:
            self._set_state("failed", "No ticks returned from MT5.")
            mt5_connector.shutdown_mt5()
            return
        self._total_ticks_ingested = len(ticks)
        self._current_price = ticks[-1]["price"]
        print(f"[RUNNER] Fetched {len(ticks)} historical ticks for {self.symbol}")

        # Phase 4: Generate Initial Bars
        self._set_state("generating_initial_bars")
        self._bar_engine = RangeBarEngine(
            bar_size_points=self.bar_size_points,
            max_bars=self.max_bars,
            on_bar=None,
        )
        for tick in ticks:
            self._bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])

        initial_count = self._bar_engine.current_bars_count
        self._total_bars_produced = self._bar_engine.total_bars_emitted
        if self._bar_engine.bars:
            self._last_bar_time = self._bar_engine.bars[-1].get("time")

        print(f"[RUNNER] Initial bars: {initial_count} "
              f"(total emitted: {self._total_bars_produced}) "
              f"(from {len(ticks)} ticks, bar_size={self.bar_size_points}pt)")

        if initial_count == 0:
            self._set_state("failed",
                f"No bars from {len(ticks)} ticks. "
                f"bar_size_points={self.bar_size_points} may be too large for {self.symbol}.")
            mt5_connector.shutdown_mt5()
            return

        self._log_pipeline("INITIAL_BARS")

        # Phase 5: Warm Up (signals logged, NOT executed)
        self._set_state("warming_up")
        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        min_lb = getattr(self._strategy, "min_lookback", 0) or 0

        for i in range(len(bars_list)):
            if self._stop_event.is_set():
                return
            self._ctx.index = i
            self._bar_index = i

            # Compute indicators for warmup bars
            if self._indicator_engine:
                warmup_slice = bars_list[:i + 1]
                self._indicator_engine.update(warmup_slice, self._ctx)

            self._refresh_position()

            if i < min_lb:
                continue

            self._on_bar_call_count += 1
            try:
                raw_signal = self._strategy.on_bar(self._ctx)
                if raw_signal:
                    s = raw_signal.get("signal")
                    if s in (SIGNAL_BUY, SIGNAL_SELL, SIGNAL_CLOSE,
                             SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT):
                        self._warmup_signal_count += 1
                        print(f"[RUNNER] Warmup signal #{self._warmup_signal_count} "
                              f"at bar {i}: {s} (NOT executed)")
            except Exception as exc:
                print(f"[RUNNER] Warmup on_bar error at bar {i}: {exc}")

        print(f"[RUNNER] Warmup complete. on_bar calls: {self._on_bar_call_count} | "
              f"warmup signals: {self._warmup_signal_count} (all skipped)")
        self._log_pipeline("WARMUP_DONE")

        # Phase 6: Live Tick Loop (signals ARE executed)
        self._set_state("running")
        self._bar_engine._on_bar = self._on_new_bar
        live_tick_count = 0

        try:
            for tick in mt5_connector.stream_live_ticks(self.symbol):
                if self._stop_event.is_set():
                    break
                self._total_ticks_ingested += 1
                self._current_price = tick["price"]
                live_tick_count += 1
                self._bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])
                if live_tick_count % 5000 == 0:
                    self._log_pipeline("LIVE_TICK")
        except Exception as exc:
            if not self._stop_event.is_set():
                tb = traceback.format_exc()
                print(f"[RUNNER] Live loop error: {exc}\n{tb}")
                self._set_state("failed", f"Live loop error: {type(exc).__name__}: {exc}")
        finally:
            self._log_pipeline("SHUTDOWN")
            mt5_connector.shutdown_mt5()
            self._mt5_state = "disconnected"
            if not self._stop_event.is_set():
                self._set_state("stopped")
```
