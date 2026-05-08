# Repository Snapshot - Part 3 of 3

- Total files indexed: `26`
- Files in this chunk: `8`
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
app/services/__init__.py
app/services/mainServices.py
config.yaml
main.py
requirements.txt
ui/css/style.css
worker/execution.py
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

## FILE: `app/services/__init__.py`

- Relative path: `app/services/__init__.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/services/__init__.py`
- Size bytes: `32`
- SHA256: `7c8c9aaeb9f535f7ae6fc3fdcc296366803058cb89ef2cde2421ccff1612799b`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
# JINNI Grid - Services package
```

---

## FILE: `app/services/mainServices.py`

- Relative path: `app/services/mainServices.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/services/mainServices.py`
- Size bytes: `11052`
- SHA256: `3480f5c818ae7aa24b86a15319cb37d8080fa39bc4efe1c406f082cadf331d35`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Combined Runtime Services
app/services/mainServices.py

Now backed by SQLite persistence (app/persistence.py).
In-memory caches kept for performance, synced to DB on writes.
"""

import logging
import random
import threading
import uuid
from datetime import datetime, timedelta, timezone

from app.config import Config
from app.persistence import (
    save_worker, get_all_workers_db, get_worker_db,
    save_deployment, update_deployment_state_db,
    get_all_deployments_db, get_deployment_db,
    log_event_db,
)

log = logging.getLogger("jinni.worker")
sys_log = logging.getLogger("jinni.system")


# =============================================================================
# Command Queue (in-memory — commands are transient by nature)
# =============================================================================

_command_queues: dict = {}
_command_lock = threading.Lock()


def enqueue_command(worker_id: str, command_type: str, payload: dict) -> dict:
    cmd_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)

    cmd = {
        "command_id": cmd_id,
        "worker_id": worker_id,
        "command_type": command_type,
        "payload": payload,
        "state": "pending",
        "created_at": now.isoformat(),
        "acked_at": None,
    }

    with _command_lock:
        if worker_id not in _command_queues:
            _command_queues[worker_id] = []
        _command_queues[worker_id].append(cmd)

    log.info(f"Enqueued {command_type} ({cmd_id}) for worker {worker_id}")

    log_event_db("command", "enqueued", f"{command_type} for {worker_id}",
                 worker_id=worker_id, data={"command_id": cmd_id})

    return cmd


def poll_commands(worker_id: str) -> list:
    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        pending = [c for c in queue if c["state"] == "pending"]
    return pending


def ack_command(worker_id: str, command_id: str) -> dict:
    now = datetime.now(timezone.utc)

    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        for cmd in queue:
            if cmd["command_id"] == command_id:
                cmd["state"] = "acknowledged"
                cmd["acked_at"] = now.isoformat()
                log.info(f"Ack {command_id} from worker {worker_id}")
                return {"ok": True, "command": cmd}

    return {"ok": False, "error": "Command not found."}


# =============================================================================
# Deployment Registry (DB-backed)
# =============================================================================

VALID_STATES = {
    "queued", "sent_to_worker", "acknowledged_by_worker",
    "loading_strategy", "fetching_ticks", "generating_initial_bars",
    "warming_up", "running", "stopped", "failed",
}


def create_deployment(config: dict) -> dict:
    deployment_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)

    record = {
        "deployment_id": deployment_id,
        "strategy_id": config["strategy_id"],
        "worker_id": config["worker_id"],
        "symbol": config["symbol"],
        "tick_lookback_value": config.get("tick_lookback_value", 30),
        "tick_lookback_unit": config.get("tick_lookback_unit", "minutes"),
        "bar_size_points": config["bar_size_points"],
        "max_bars_in_memory": config.get("max_bars_in_memory", 500),
        "lot_size": config.get("lot_size", 0.01),
        "strategy_parameters": config.get("strategy_parameters") or {},
        "state": "queued",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "last_error": None,
    }

    save_deployment(deployment_id, record)

    log.info(f"Created deployment {deployment_id} | "
             f"strategy={config['strategy_id']} -> worker={config['worker_id']}")

    log_event_db("deployment", "created",
                 f"Deployment {deployment_id} created",
                 worker_id=config["worker_id"],
                 strategy_id=config["strategy_id"],
                 deployment_id=deployment_id,
                 symbol=config["symbol"])

    return {"ok": True, "deployment_id": deployment_id, "deployment": record}


def get_all_deployments() -> list:
    return get_all_deployments_db()


def get_deployment(deployment_id: str):
    return get_deployment_db(deployment_id)


def update_deployment_state(deployment_id: str, state: str, error: str = None) -> dict:
    if state not in VALID_STATES:
        return {"ok": False, "error": f"Invalid state: {state}"}

    update_deployment_state_db(deployment_id, state, error)

    log.info(f"Deployment {deployment_id} -> {state}"
             + (f" (error: {error})" if error else ""))

    log_event_db("deployment", "state_change",
                 f"{deployment_id} -> {state}",
                 deployment_id=deployment_id,
                 data={"state": state, "error": error},
                 level="ERROR" if state == "failed" else "INFO")

    rec = get_deployment_db(deployment_id)
    return {"ok": True, "deployment": rec}


def stop_deployment(deployment_id: str) -> dict:
    return update_deployment_state(deployment_id, "stopped")


def get_deployments_for_worker(worker_id: str) -> list:
    all_deps = get_all_deployments_db()
    return [d for d in all_deps if d["worker_id"] == worker_id]


# =============================================================================
# Mock Portfolio Data (will be replaced by real portfolio module)
# =============================================================================

def get_portfolio_summary() -> dict:
    return {
        "total_balance": 248750.00,
        "total_equity": 251320.45,
        "floating_pnl": 2570.45,
        "daily_pnl": 1847.30,
        "open_positions": 12,
        "realized_pnl": 18432.60,
        "margin_usage": 34.7,
        "win_rate": 68.5,
    }


def get_equity_history() -> list:
    rng = random.Random(42)
    points = []
    start = datetime(2026, 2, 5, tzinfo=timezone.utc)
    val = 200000.0
    for i in range(90):
        d = start + timedelta(days=i)
        val += (rng.random() - 0.42) * 2000
        if val < 180000:
            val = 180000.0
        points.append({"timestamp": d.strftime("%Y-%m-%d"), "equity": round(val, 2)})
    return points


# =============================================================================
# Worker Registry (DB-backed + in-memory cache for heartbeat age calc)
# =============================================================================

_workers_cache: dict = {}
_worker_lock = threading.Lock()


def _load_workers_from_db():
    """Load workers from DB into memory cache on startup."""
    global _workers_cache
    db_workers = get_all_workers_db()
    with _worker_lock:
        for w in db_workers:
            wid = w["worker_id"]
            hb_at = w.get("last_heartbeat_at")
            if hb_at:
                try:
                    dt = datetime.fromisoformat(hb_at)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            w["_last_heartbeat_dt"] = dt
            _workers_cache[wid] = w
    sys_log.info(f"Loaded {len(_workers_cache)} workers from DB")


def process_heartbeat(payload: dict) -> dict:
    worker_id = payload["worker_id"].strip()
    now = datetime.now(timezone.utc)
    is_new = False

    with _worker_lock:
        if worker_id not in _workers_cache:
            is_new = True

        _workers_cache[worker_id] = {
            **payload,
            "worker_id": worker_id,
            "last_heartbeat_at": now.isoformat(),
            "_last_heartbeat_dt": now,
        }

    # Persist to DB
    save_worker(worker_id, {
        **payload,
        "last_heartbeat_at": now.isoformat(),
    })

    if is_new:
        log.info(f"Worker '{worker_id}' registered | state={payload.get('state')}")
        log_event_db("worker", "registered",
                     f"Worker {worker_id} first heartbeat",
                     worker_id=worker_id)

    return {
        "ok": True,
        "worker_id": worker_id,
        "registered": is_new,
        "server_time": now.isoformat(),
    }


def get_all_workers() -> list:
    fleet_config = Config.get_fleet_config()
    stale_threshold = fleet_config.get("stale_threshold_seconds", 30)
    offline_threshold = fleet_config.get("offline_threshold_seconds", 90)
    now = datetime.now(timezone.utc)
    result = []

    with _worker_lock:
        for wid, rec in _workers_cache.items():
            hb_dt = rec.get("_last_heartbeat_dt", now)
            age = round((now - hb_dt).total_seconds(), 1)
            reported = rec.get("reported_state", rec.get("state", "online"))

            if age >= offline_threshold:
                effective = "offline"
            elif age >= stale_threshold:
                effective = "stale"
            else:
                effective = reported

            result.append({
                "worker_id": rec.get("worker_id", wid),
                "worker_name": rec.get("worker_name"),
                "host": rec.get("host"),
                "state": effective,
                "reported_state": reported,
                "last_heartbeat_at": rec.get("last_heartbeat_at"),
                "heartbeat_age_seconds": age,
                "agent_version": rec.get("agent_version"),
                "mt5_state": rec.get("mt5_state"),
                "account_id": rec.get("account_id"),
                "broker": rec.get("broker"),
                "active_strategies": rec.get("active_strategies") or [],
                "open_positions_count": rec.get("open_positions_count", 0),
                "floating_pnl": rec.get("floating_pnl"),
                "errors": rec.get("errors") or [],
                "total_ticks": rec.get("total_ticks", 0),
                "total_bars": rec.get("total_bars", 0),
                "on_bar_calls": rec.get("on_bar_calls", 0),
                "signal_count": rec.get("signal_count", 0),
                "last_bar_time": rec.get("last_bar_time"),
                "current_price": rec.get("current_price"),
            })

    return result


def get_fleet_summary() -> dict:
    workers = get_all_workers()
    counts = {
        "online_workers": 0, "stale_workers": 0, "offline_workers": 0,
        "error_workers": 0, "warning_workers": 0,
    }
    online_states = {"online", "running", "idle"}
    for w in workers:
        state = w["state"]
        if state in online_states:
            counts["online_workers"] += 1
        elif state == "stale":
            counts["stale_workers"] += 1
        elif state == "offline":
            counts["offline_workers"] += 1
        elif state == "error":
            counts["error_workers"] += 1
        elif state == "warning":
            counts["warning_workers"] += 1
    counts["total_workers"] = len(workers)
    return counts
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

## FILE: `main.py`

- Relative path: `main.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/main.py`
- Size bytes: `1411`
- SHA256: `005db2d807f1a8a88b01bbfc1a3f14f504a36fbfdc8c12652f1ff75b4c04ff1f`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID - Mother Server Entry Point
Run: python main.py
"""

import os
import uvicorn

from app.logging_config import setup_logging
from app import create_app
from app.config import Config


# Initialize logging BEFORE anything else
setup_logging()

# App instance at module level so uvicorn reloader can find it
app = create_app()


def main():
    server_config = Config.get_server_config()
    app_config = Config.get_app_config()

    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 5100)
    debug = server_config.get("debug", False)
    name = app_config.get("name", "JINNI GRID Mother Server")
    version = app_config.get("version", "0.2.0")

    print("")
    print("=" * 56)
    print(f"  {name} v{version}")
    print("=" * 56)
    print(f"  Dashboard:   http://{host}:{port}")
    print(f"  API docs:    http://{host}:{port}/docs")
    print(f"  Debug mode:  {debug}")
    print(f"  Database:    data/jinni_grid.db")
    print(f"  Logs:        data/logs/")
    print("=" * 56)
    print("")

    run_kwargs = {"host": host, "port": port, "reload": debug}

    if debug:
        project_root = os.path.dirname(os.path.abspath(__file__))
        run_kwargs["reload_dirs"] = [
            os.path.join(project_root, "app"),
            os.path.join(project_root, "ui"),
        ]

    uvicorn.run("main:app", **run_kwargs)


if __name__ == "__main__":
    main()
```

---

## FILE: `requirements.txt`

- Relative path: `requirements.txt`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/requirements.txt`
- Size bytes: `68`
- SHA256: `e1bb6d373c1916a0cfc941a59698ad1f70b2d70b84da0c666131c6adeec80e95`
- Guessed MIME type: `text/plain`
- Guessed encoding: `unknown`

```text
fastapi>=0.110.0
uvicorn>=0.27.0
pyyaml>=6.0
python-multipart>=0.0.9
```

---

## FILE: `ui/css/style.css`

- Relative path: `ui/css/style.css`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/css/style.css`
- Size bytes: `43652`
- SHA256: `6c44ea355be3b9492f2a432214e4fe81b650cdf7dbf5cf2aa430c0d8e1fbfe17`
- Guessed MIME type: `text/css`
- Guessed encoding: `unknown`

```css
/* base.css */

*,*::before,*::after { margin:0; padding:0; box-sizing:border-box; }
html { font-size: 14px; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  overflow: hidden;
  height: 100vh;
  -webkit-font-smoothing: antialiased;
}
a { text-decoration: none; color: inherit; }
button { font-family: inherit; border: none; cursor: pointer; background: none; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--scrollbar-track); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }
.text-success { color: var(--success) !important; }
.text-danger  { color: var(--danger) !important; }
.text-warning { color: var(--warning) !important; }
.text-accent  { color: var(--accent) !important; }
.text-muted   { color: var(--text-muted) !important; }
.text-stale   { color: var(--stale) !important; }
.mono { font-family: 'JetBrains Mono', monospace; }

/* ── dashboard.css  ───────────────────────────────────────────────────── */

.dashboard {
  display: flex; flex-direction: column; gap: 28px;
  width: 100%; max-width: 1400px;
}

/* ── Section Header ─────────────────────────────────────────────── */

.section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.section-header i { color: var(--accent); font-size: 14px; }
.section-header h2 { font-size: 14px; font-weight: 600; color: var(--text-primary); letter-spacing: 0.3px; }
.section-badge {
  margin-left: 8px; font-family: 'JetBrains Mono', monospace; font-size: 10.5px;
  font-weight: 500; padding: 2px 8px; border-radius: 4px;
  background: var(--accent-dim); color: var(--accent);
}

/* ── Portfolio Cards Grid ───────────────────────────────────────── */

.portfolio-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  width: 100%;
}

.portfolio-card {
  background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: 10px;
  padding: 16px 18px; display: flex; align-items: flex-start; gap: 14px;
  box-shadow: var(--shadow-sm); animation: fadeInUp 0.4s ease both;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.3s ease;
  min-width: 0;
}
.portfolio-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); background: var(--bg-card-hover); }
.portfolio-card:nth-child(1) { animation-delay: 0.02s; }
.portfolio-card:nth-child(2) { animation-delay: 0.04s; }
.portfolio-card:nth-child(3) { animation-delay: 0.06s; }
.portfolio-card:nth-child(4) { animation-delay: 0.08s; }
.portfolio-card:nth-child(5) { animation-delay: 0.10s; }
.portfolio-card:nth-child(6) { animation-delay: 0.12s; }
.portfolio-card:nth-child(7) { animation-delay: 0.14s; }
.portfolio-card:nth-child(8) { animation-delay: 0.16s; }

/* ── Card Icon ──────────────────────────────────────────────────── */

.card-icon {
  width: 40px; height: 40px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; flex-shrink: 0;
}
.card-icon.neutral  { background: var(--accent-dim);  color: var(--accent); }
.card-icon.positive { background: var(--success-dim); color: var(--success); }
.card-icon.negative { background: var(--danger-dim);  color: var(--danger); }
.card-icon.warning  { background: var(--warning-dim); color: var(--warning); }

/* ── Card Info ──────────────────────────────────────────────────── */

.card-info { display: flex; flex-direction: column; gap: 4px; min-width: 0; overflow: hidden; }
.card-value {
  font-family: 'JetBrains Mono', monospace; font-size: 17px;
  font-weight: 700; color: var(--text-primary); line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.card-value.positive { color: var(--success); }
.card-value.negative { color: var(--danger); }
.card-label {
  font-size: 11.5px; font-weight: 500; text-transform: uppercase;
  letter-spacing: 0.6px; color: var(--text-muted);
  white-space: nowrap;
}

/* ── Equity Chart ───────────────────────────────────────────────── */

.chart-container {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 20px; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.4s ease 0.2s both; width: 100%;
}
.chart-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.chart-title { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.chart-period { font-size: 11px; color: var(--text-muted); font-weight: 500; }
.chart-wrapper { height: 280px; position: relative; }

/* ── Fleet Summary Badges ───────────────────────────────────────── */

.fleet-summary { display: flex; gap: 14px; flex-wrap: wrap; width: 100%; margin-bottom: 18px; }
.fleet-badge {
  display: flex; align-items: center; gap: 10px;
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 8px; padding: 10px 16px; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.3s ease both;
}
.badge-count { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }
.badge-label { font-size: 11.5px; font-weight: 500; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.badge-count.total   { color: var(--text-primary); }
.badge-count.online  { color: var(--success); }
.badge-count.warning { color: var(--warning); }
.badge-count.stale   { color: var(--stale); }
.badge-count.offline { color: var(--text-muted); }
.badge-count.error   { color: var(--danger); }

/* ── Fleet Grid ─────────────────────────────────────────────────── */

.fleet-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  width: 100%;
}

/* ── Node Card ──────────────────────────────────────────────────── */

.node-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; overflow: hidden; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.4s ease both;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.3s ease;
  min-width: 0;
}
.node-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); background: var(--bg-card-hover); }
.node-card:nth-child(1) { animation-delay: 0.02s; }
.node-card:nth-child(2) { animation-delay: 0.04s; }
.node-card:nth-child(3) { animation-delay: 0.06s; }
.node-card:nth-child(4) { animation-delay: 0.08s; }
.node-card:nth-child(5) { animation-delay: 0.10s; }
.node-card:nth-child(6) { animation-delay: 0.12s; }

/* ── Node Card Top Bar ──────────────────────────────────────────── */

.node-card-top { height: 2px; }
.node-card-top.online  { background: var(--success); }
.node-card-top.running { background: var(--success); }
.node-card-top.idle    { background: var(--accent); }
.node-card-top.warning { background: var(--warning); }
.node-card-top.stale   { background: var(--stale); }
.node-card-top.offline { background: var(--text-muted); }
.node-card-top.error   { background: var(--danger); }

/* ── Node Card Header ───────────────────────────────────────────── */

.node-card-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px 10px; }
.node-name-group { display: flex; align-items: center; gap: 8px; min-width: 0; }
.node-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.node-status-dot.online  { background: var(--success); }
.node-status-dot.running { background: var(--success); }
.node-status-dot.idle    { background: var(--accent); }
.node-status-dot.warning { background: var(--warning); }
.node-status-dot.stale   { background: var(--stale); }
.node-status-dot.offline { background: var(--text-muted); }
.node-status-dot.error   { background: var(--danger); }
.node-name {
  font-family: 'JetBrains Mono', monospace; font-size: 12.5px;
  font-weight: 500; color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.node-status-badge {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; padding: 3px 8px; border-radius: 4px; flex-shrink: 0;
}
.node-status-badge.online  { background: var(--success-dim); color: var(--success); }
.node-status-badge.running { background: var(--success-dim); color: var(--success); }
.node-status-badge.idle    { background: var(--accent-dim);  color: var(--accent); }
.node-status-badge.warning { background: var(--warning-dim); color: var(--warning); }
.node-status-badge.stale   { background: var(--stale-dim);   color: var(--stale); }
.node-status-badge.offline { background: rgba(100,116,139,0.15); color: var(--text-muted); }
.node-status-badge.error   { background: var(--danger-dim);  color: var(--danger); }
.node-status-badge.unknown { background: rgba(100,116,139,0.15); color: var(--text-muted); }

/* ── Node Card Body ─────────────────────────────────────────────── */

.node-card-body { padding: 0 16px 14px; }
.node-info-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 0; border-bottom: 1px solid var(--border-subtle);
}
.node-info-row:last-child { border-bottom: none; }
.node-info-label { font-size: 11px; color: var(--text-muted); font-weight: 500; white-space: nowrap; }
.node-info-value {
  font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
  color: var(--text-secondary); font-weight: 400; text-align: right;
  max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.node-info-value.strategy { color: var(--accent); font-weight: 500; }
.node-info-value.inactive { color: var(--text-muted); }

/* ── State Pills ────────────────────────────────────────────────── */

.state-pill {
  display: inline-block; font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.4px;
  padding: 2px 8px; border-radius: 4px;
}
.state-pill.online  { background: var(--success-dim); color: var(--success); }
.state-pill.running { background: var(--success-dim); color: var(--success); }
.state-pill.idle    { background: var(--accent-dim);  color: var(--accent); }
.state-pill.warning { background: var(--warning-dim); color: var(--warning); }
.state-pill.stale   { background: var(--stale-dim);   color: var(--stale); }
.state-pill.error   { background: var(--danger-dim);  color: var(--danger); }
.state-pill.offline { background: rgba(100,116,139,0.15); color: var(--text-muted); }
.state-pill.unknown { background: rgba(100,116,139,0.15); color: var(--text-muted); }

/* ── Compact Fleet Table ────────────────────────────────────────── */

.compact-fleet-wrapper {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 16px; overflow-x: auto;
  box-shadow: var(--shadow-sm); margin-top: 12px;
}
.compact-fleet-table { width: 100%; border-collapse: separate; border-spacing: 0; }
.compact-fleet-table th {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-muted); font-weight: 600; padding: 8px 12px;
  text-align: left; border-bottom: 1px solid var(--border-primary);
}
.compact-fleet-table td {
  font-size: 12px; padding: 8px 12px;
  border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary);
}
.compact-fleet-table td.mono { font-family: 'JetBrains Mono', monospace; }
.compact-fleet-table tr:hover td { background: var(--bg-card-hover); }

/* ── View Fleet Link ────────────────────────────────────────────── */

.view-fleet-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--accent); font-weight: 500;
  cursor: pointer; margin-top: 12px; transition: opacity 0.2s;
}
.view-fleet-link:hover { opacity: 0.8; }

/* ── Null Value ─────────────────────────────────────────────────── */

.value-null { color: var(--text-muted); font-style: italic; }

/* ── Dashboard Fleet Section ────────────────────────────────────── */

.dashboard-fleet-section { min-height: 120px; }

/* ── Loading State ──────────────────────────────────────────────── */

.loading-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 16px;
  animation: fadeInUp 0.4s ease both;
}
.spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--border-primary);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-state p { font-size: 13px; color: var(--text-muted); }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Empty State ────────────────────────────────────────────────── */

.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 14px;
  animation: fadeInUp 0.4s ease both; padding: 40px;
}
.empty-state i { font-size: 52px; color: var(--text-muted); opacity: 0.25; }
.empty-state h3 { font-size: 16px; font-weight: 600; color: var(--text-secondary); }
.empty-state p {
  font-size: 13px; color: var(--text-muted); max-width: 420px;
  text-align: center; line-height: 1.6;
}
.empty-state code {
  font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
  background: var(--bg-secondary); padding: 2px 8px;
  border-radius: 4px; color: var(--accent);
}

/* ── Error State ────────────────────────────────────────────────── */

.error-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 14px;
  animation: fadeInUp 0.4s ease both; padding: 40px;
}
.error-state i { font-size: 52px; color: var(--danger); opacity: 0.4; }
.error-state h3 { font-size: 16px; font-weight: 600; color: var(--text-secondary); }
.error-state p {
  font-size: 13px; color: var(--text-muted); max-width: 420px;
  text-align: center; line-height: 1.6;
}
.retry-btn {
  padding: 8px 20px; background: var(--accent-dim); color: var(--accent);
  border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer;
  border: 1px solid transparent; transition: all 0.2s ease;
}
.retry-btn:hover { background: var(--accent); color: #fff; }

/* ── Fleet Page ─────────────────────────────────────────────────── */

.fleet-page {
  display: flex; flex-direction: column; gap: 24px;
  width: 100%; max-width: 1400px;
  animation: fadeInUp 0.3s ease both;
}
.fleet-page-header {
  display: flex; align-items: center; justify-content: space-between;
}
.fleet-page-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.fleet-page-meta { display: flex; align-items: center; gap: 14px; }
.auto-refresh-badge {
  display: flex; align-items: center; gap: 6px; font-size: 11px;
  color: var(--text-muted); background: var(--bg-card);
  border: 1px solid var(--border-primary); padding: 4px 10px; border-radius: 5px;
}
.auto-refresh-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--success); animation: pulse-glow 2s ease-in-out infinite;
}
.last-synced {
  font-size: 11px; color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

/* ── Placeholder Page ───────────────────────────────────────────── */

.placeholder-page {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; min-height: 400px; gap: 16px;
  animation: fadeInUp 0.4s ease both;
}
.placeholder-page i { font-size: 48px; color: var(--text-muted); opacity: 0.3; }
.placeholder-page h2 { font-size: 18px; font-weight: 600; color: var(--text-secondary); }
.placeholder-page p {
  font-size: 13px; color: var(--text-muted); max-width: 360px;
  text-align: center; line-height: 1.6;
}

/* ── Animations ─────────────────────────────────────────────────── */

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Responsive ─────────────────────────────────────────────────── */

@media (max-width: 1100px) {
  .portfolio-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fleet-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .portfolio-grid { grid-template-columns: minmax(0, 1fr); }
  .fleet-grid { grid-template-columns: minmax(0, 1fr); }
}

/* ── layout.css  ────────────────────────────────────────────────── */

body { display: flex; flex-direction: row; }

/* ── Sidebar (always dark) ──────────────────────────────────────── */

.sidebar {
  width: 240px; min-width: 240px; height: 100vh; background: #0d1117;
  display: flex; flex-direction: column; border-right: 1px solid #1e293b; z-index: 10;
}
.sidebar-brand {
  height: 60px; display: flex; align-items: center; gap: 12px;
  padding: 0 20px; border-bottom: 1px solid #1e293b;
}
.brand-mark {
  width: 32px; height: 32px; border-radius: 8px;
  background: linear-gradient(135deg, #06b6d4, #3b82f6);
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace; font-weight: 700;
  font-size: 12px; color: #fff; letter-spacing: -0.5px; flex-shrink: 0;
}
.brand-text { display: flex; flex-direction: column; line-height: 1; }
.brand-name { font-weight: 700; font-size: 13px; color: #e2e8f0; letter-spacing: 1.2px; }
.brand-sub { font-size: 10px; color: #64748b; margin-top: 3px; letter-spacing: 0.5px; }

/* ── Navigation ─────────────────────────────────────────────────── */

.sidebar-nav { flex: 1; display: flex; flex-direction: column; padding: 12px 0; overflow-y: auto; }
.nav-item {
  display: flex; align-items: center; gap: 12px; padding: 10px 20px;
  color: #94a3b8; font-size: 13px; font-weight: 500;
  border-left: 3px solid transparent; transition: all 0.2s ease;
}
.nav-item:hover { color: #e2e8f0; background: rgba(255,255,255,0.03); }
.nav-item.active { color: #06b6d4; border-left-color: #06b6d4; background: rgba(6,182,212,0.08); }
.nav-item i { width: 18px; text-align: center; font-size: 14px; }

/* ── Sidebar Footer / Theme Toggle ──────────────────────────────── */

.sidebar-footer { padding: 12px 16px; border-top: 1px solid #1e293b; }
.theme-toggle {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 8px 12px; border-radius: 6px; color: #94a3b8;
  font-size: 12px; font-weight: 500; transition: all 0.2s ease;
}
.theme-toggle:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }
.theme-toggle i { width: 16px; text-align: center; font-size: 13px; }

/* ── Main Wrapper ───────────────────────────────────────────────── */

.main-wrapper {
  flex: 1; display: flex; flex-direction: column;
  height: 100vh; min-width: 0; overflow: hidden;
}

/* ── Top Bar ────────────────────────────────────────────────────── */

.topbar {
  height: 60px; min-height: 60px; background: var(--bg-topbar);
  border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between; padding: 0 28px;
}
.topbar-left { display: flex; align-items: baseline; gap: 12px; }
.topbar-title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.topbar-subtitle { font-size: 11.5px; color: var(--text-muted); font-weight: 400; }
.topbar-right { display: flex; align-items: center; gap: 20px; }
.topbar-status { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); font-weight: 500; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot--online { background: var(--success); }
.status-dot--offline { background: var(--text-muted); }
.status-dot--warning { background: var(--warning); }
.status-dot--error { background: var(--danger); }
.status-dot.pulse { animation: pulse-glow 2s ease-in-out infinite; }

@keyframes pulse-glow {
  0%,100% { box-shadow: 0 0 0 0 rgba(16,185,129,0.5); }
  50% { box-shadow: 0 0 0 6px rgba(16,185,129,0); }
}

.topbar-clock {
  font-family: 'JetBrains Mono', monospace; font-size: 13px;
  font-weight: 500; color: var(--text-secondary); letter-spacing: 0.5px;
}

/* ── Content Area ───────────────────────────────────────────────── */

.content {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 24px 28px;
  background: var(--bg-primary);
  width: 100%;
}

/*theme.css*/

[data-theme="dark"] {
  --bg-primary: #0b0f19;
  --bg-secondary: #111827;
  --bg-card: #151c2c;
  --bg-card-hover: #1a2236;
  --bg-topbar: #0d1117;
  --border-primary: #1e293b;
  --border-subtle: #162033;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent: #06b6d4;
  --accent-dim: rgba(6, 182, 212, 0.15);
  --success: #10b981;
  --success-dim: rgba(16, 185, 129, 0.15);
  --danger: #ef4444;
  --danger-dim: rgba(239, 68, 68, 0.15);
  --warning: #f59e0b;
  --warning-dim: rgba(245, 158, 11, 0.15);
  --stale: #fb923c;
  --stale-dim: rgba(251, 146, 60, 0.15);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.5);
  --scrollbar-track: #0b0f19;
  --scrollbar-thumb: #1e293b;
  --scrollbar-thumb-hover: #334155;
}
[data-theme="light"] {
  --bg-primary: #f0f4f8;
  --bg-secondary: #e2e8f0;
  --bg-card: #ffffff;
  --bg-card-hover: #f8fafc;
  --bg-topbar: #ffffff;
  --border-primary: #e2e8f0;
  --border-subtle: #f1f5f9;
  --text-primary: #1e293b;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --accent: #0891b2;
  --accent-dim: rgba(8, 145, 178, 0.12);
  --success: #059669;
  --success-dim: rgba(5, 150, 105, 0.12);
  --danger: #dc2626;
  --danger-dim: rgba(220, 38, 38, 0.12);
  --warning: #d97706;
  --warning-dim: rgba(217, 119, 6, 0.12);
  --stale: #ea580c;
  --stale-dim: rgba(234, 88, 12, 0.12);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.1);
  --scrollbar-track: #f0f4f8;
  --scrollbar-thumb: #cbd5e1;
  --scrollbar-thumb-hover: #94a3b8;
}
body,.topbar,.content,.portfolio-card,.node-card,.section-header,.fleet-summary,
.chart-container,.fleet-page,.loading-state,.empty-state,.error-state,.compact-fleet-wrapper,
.fleet-badge {
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

/* worker-detail.css*/


/* ── Clickable Fleet Enhancement ──────────────────────────── */
.node-card.clickable { cursor: pointer; }
.node-card.clickable:hover { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-dim), var(--shadow-md); }
.node-card-action {
  display: flex; align-items: center; gap: 6px; margin-top: 8px; padding-top: 8px;
  border-top: 1px solid var(--border-subtle); font-size: 11px; color: var(--accent);
  font-weight: 500;
}
.compact-fleet-table tr.clickable { cursor: pointer; }
.compact-fleet-table tr.clickable:hover td { background: var(--bg-card-hover); }

/* ── Worker Detail Page ───────────────────────────────────── */
.worker-detail { display: flex; flex-direction: column; gap: 24px; max-width: 1400px; animation: fadeInUp 0.3s ease both; }

.wd-header {
  background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: 10px;
  padding: 20px; display: flex; align-items: center; justify-content: space-between;
  box-shadow: var(--shadow-sm);
}
.wd-header-left { display: flex; align-items: center; gap: 16px; }
.wd-back-btn {
  padding: 8px 14px; background: var(--bg-secondary); border: 1px solid var(--border-primary);
  border-radius: 6px; color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; gap: 6px;
}
.wd-back-btn:hover { color: var(--accent); border-color: var(--accent); }
.wd-header-info { display: flex; flex-direction: column; gap: 4px; }
.wd-header-info h2 { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.wd-header-meta {
  display: flex; align-items: center; gap: 8px; font-size: 11.5px;
  color: var(--text-muted); font-family: 'JetBrains Mono', monospace;
}
.meta-sep { opacity: 0.4; }
.wd-header-right { display: flex; align-items: center; gap: 12px; }
.wd-refresh-btn {
  padding: 8px 14px; background: var(--bg-secondary); border: 1px solid var(--border-primary);
  border-radius: 6px; color: var(--text-secondary); font-size: 11px; font-weight: 500;
  cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.wd-refresh-btn:hover { color: var(--accent); border-color: var(--accent); }
.wd-emergency-btn {
  padding: 8px 16px; background: var(--danger-dim); color: var(--danger);
  border-radius: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; border: 1px solid transparent; cursor: pointer;
  transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.wd-emergency-btn:hover { background: var(--danger); color: #fff; }

/* ── Status Cards Grid ────────────────────────────────────── */
.wd-status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.wd-status-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 6px;
  box-shadow: var(--shadow-sm);
}
.wd-status-card .status-label {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-muted); font-weight: 500;
}
.wd-status-card .status-value {
  font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 600;
  color: var(--text-primary);
}
.status-indicator { display: flex; align-items: center; gap: 6px; }
.wd-status-dot-sm {
  width: 6px; height: 6px; border-radius: 50%; display: inline-block; flex-shrink: 0;
}
.wd-status-dot-sm.green { background: var(--success); }
.wd-status-dot-sm.amber { background: var(--warning); }
.wd-status-dot-sm.orange { background: var(--stale); }
.wd-status-dot-sm.red { background: var(--danger); }
.wd-status-dot-sm.blue { background: var(--accent); }
.wd-status-dot-sm.gray { background: var(--text-muted); }

/* ── Content Layout ───────────────────────────────────────── */
.wd-content { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
.wd-main-col { display: flex; flex-direction: column; gap: 20px; }
.wd-side-col { display: flex; flex-direction: column; gap: 20px; }

/* ── Panel ────────────────────────────────────────────────── */
.wd-panel {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; overflow: hidden; box-shadow: var(--shadow-sm);
}
.wd-panel-header {
  font-size: 13px; font-weight: 600; color: var(--text-primary);
  padding: 16px 20px; border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between;
}
.panel-badge {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 500;
  padding: 2px 8px; border-radius: 4px; background: var(--accent-dim); color: var(--accent);
}
.panel-badge.mock {
  background: var(--warning-dim); color: var(--warning);
}
.wd-panel-body { padding: 20px; }

/* ── File Upload ──────────────────────────────────────────── */
.wd-file-upload {
  border: 2px dashed var(--border-primary); border-radius: 8px; padding: 32px;
  text-align: center; transition: all 0.2s; cursor: pointer;
}
.wd-file-upload:hover { border-color: var(--accent); }
.wd-file-upload.has-file { border-color: var(--success); border-style: solid; }
.wd-file-upload i { font-size: 32px; color: var(--text-muted); opacity: 0.4; }
.wd-file-upload h4 { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-top: 10px; }
.wd-file-upload p { font-size: 11.5px; color: var(--text-muted); margin-top: 4px; }
.file-name {
  font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent);
  font-weight: 500; margin-top: 8px;
}
.wd-file-status {
  display: flex; align-items: center; gap: 6px; justify-content: center;
  margin-top: 8px; font-size: 11px;
}

/* ── Metadata Preview ─────────────────────────────────────── */
.wd-metadata {
  margin-top: 16px; background: var(--bg-secondary); border-radius: 8px;
  padding: 16px; animation: fadeInUp 0.3s ease both;
}
.wd-metadata-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.wd-metadata-item { display: flex; flex-direction: column; gap: 2px; }
.wd-metadata-label {
  font-size: 10px; text-transform: uppercase; color: var(--text-muted);
  font-weight: 500; letter-spacing: 0.4px;
}
.wd-metadata-value {
  font-size: 12px; color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
}

/* ── Form Controls ────────────────────────────────────────── */
.wd-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.wd-form-group { display: flex; flex-direction: column; gap: 5px; }
.wd-form-label {
  font-size: 11px; color: var(--text-muted); font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.4px;
}
.wd-form-input, .wd-form-select {
  width: 100%; padding: 8px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-primary); border-radius: 6px;
  color: var(--text-primary); font-size: 12px; font-family: 'JetBrains Mono', monospace;
  outline: none; transition: border-color 0.2s;
}
.wd-form-input:focus, .wd-form-select:focus { border-color: var(--accent); }
.wd-form-select { cursor: pointer; }

/* ── Toggle Switch ────────────────────────────────────────── */
.wd-toggle-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid var(--border-subtle);
}
.wd-toggle-row:last-child { border-bottom: none; }
.wd-toggle-label { display: flex; flex-direction: column; gap: 2px; }
.wd-toggle-label span:first-child { font-size: 12px; color: var(--text-primary); font-weight: 500; }
.wd-toggle-label span:last-child { font-size: 10.5px; color: var(--text-muted); }
.wd-toggle {
  position: relative; width: 40px; height: 22px; -webkit-appearance: none;
  appearance: none; background: var(--border-primary); border-radius: 11px;
  cursor: pointer; transition: background 0.2s; flex-shrink: 0; border: none;
}
.wd-toggle:checked { background: var(--accent); }
.wd-toggle::after {
  content: ''; position: absolute; width: 18px; height: 18px; border-radius: 50%;
  background: var(--text-primary); top: 2px; left: 2px; transition: transform 0.2s;
}
.wd-toggle:checked::after { transform: translateX(18px); }

/* ── Parameters Editor ────────────────────────────────────── */
.wd-params-list { display: flex; flex-direction: column; }
.wd-param-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid var(--border-subtle); gap: 12px;
}
.wd-param-row:last-child { border-bottom: none; }
.wd-param-row.modified { border-left: 3px solid var(--accent); padding-left: 12px; margin-left: -4px; }
.wd-param-info { flex: 1; min-width: 0; }
.wd-param-name { font-size: 12px; font-weight: 500; color: var(--text-primary); }
.wd-param-desc { font-size: 10.5px; color: var(--text-muted); margin-top: 2px; }
.wd-param-type-badge {
  display: inline-block; font-size: 9px; font-weight: 600; text-transform: uppercase;
  padding: 1px 6px; border-radius: 3px; margin-left: 6px; vertical-align: middle;
}
.type-int { background: var(--accent-dim); color: var(--accent); }
.type-float { background: var(--warning-dim); color: var(--warning); }
.type-bool { background: var(--success-dim); color: var(--success); }
.type-string { background: var(--stale-dim); color: var(--stale); }
.wd-param-controls { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.wd-param-input {
  width: 100px; padding: 6px 10px; background: var(--bg-secondary);
  border: 1px solid var(--border-primary); border-radius: 6px;
  color: var(--text-primary); font-size: 11.5px; font-family: 'JetBrains Mono', monospace;
  outline: none; transition: border-color 0.2s; text-align: right;
}
.wd-param-input:focus { border-color: var(--accent); }
.wd-param-reset {
  width: 24px; height: 24px; border-radius: 50%; background: transparent;
  border: none; color: var(--text-muted); font-size: 11px; cursor: pointer;
  opacity: 0.5; transition: all 0.2s; display: flex; align-items: center; justify-content: center;
}
.wd-param-reset:hover { opacity: 1; color: var(--accent); }

/* ── Checklist ────────────────────────────────────────────── */
.wd-checklist { display: flex; flex-direction: column; }
.wd-check-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.wd-check-item:last-child { border-bottom: none; }
.wd-check-icon {
  width: 18px; height: 18px; border-radius: 4px; display: flex;
  align-items: center; justify-content: center; font-size: 10px; flex-shrink: 0;
}
.wd-check-icon.pass { background: var(--success-dim); color: var(--success); }
.wd-check-icon.fail { background: var(--danger-dim); color: var(--danger); }
.wd-check-icon.warn { background: var(--warning-dim); color: var(--warning); }
.wd-check-icon.info { background: var(--accent-dim); color: var(--accent); }
.wd-check-text { font-size: 12px; color: var(--text-secondary); }
.wd-check-text.pass { color: var(--text-primary); }
.wd-check-text.dimmed { color: var(--text-muted); font-style: italic; }

/* ── Deploy Action Bar ────────────────────────────────────── */
.wd-action-bar {
  padding: 16px 20px; display: flex; align-items: center;
  justify-content: space-between; border-top: 1px solid var(--border-primary);
}
.wd-action-bar-left, .wd-action-bar-right { display: flex; gap: 10px; }
.wd-btn {
  padding: 8px 18px; border-radius: 6px; font-size: 12px; font-weight: 500;
  border: 1px solid transparent; cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; gap: 6px;
}
.wd-btn-ghost { background: transparent; border-color: var(--border-primary); color: var(--text-secondary); }
.wd-btn-ghost:hover { color: var(--text-primary); border-color: var(--text-muted); }
.wd-btn-outline { background: transparent; border-color: var(--accent); color: var(--accent); }
.wd-btn-outline:hover { background: var(--accent); color: #fff; }
.wd-btn-primary { background: var(--accent); color: #fff; font-weight: 600; }
.wd-btn-primary:hover { filter: brightness(1.1); }
.wd-btn-primary.deploy {
  background: linear-gradient(135deg, #06b6d4, #3b82f6); box-shadow: var(--shadow-md);
}
.wd-btn-primary.deploy:hover { box-shadow: var(--shadow-lg); transform: translateY(-1px); }

/* ── Activity Timeline ────────────────────────────────────── */
.wd-timeline { display: flex; flex-direction: column; }
.wd-timeline-item {
  display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border-subtle);
}
.wd-timeline-item:last-child { border-bottom: none; }
.wd-timeline-time {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--text-muted);
  width: 60px; flex-shrink: 0;
}
.wd-timeline-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
  flex-shrink: 0; margin-top: 5px;
}
.wd-timeline-text { font-size: 11.5px; color: var(--text-secondary); }

/* ── Modal ────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
  animation: modal-fade-in 0.2s ease;
}
.modal-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 12px; width: 480px; max-width: 90vw; box-shadow: var(--shadow-lg);
  animation: modal-slide-in 0.3s ease;
}
.modal-header {
  padding: 20px 24px; border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between;
}
.modal-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.modal-close { font-size: 18px; cursor: pointer; color: var(--text-muted); transition: color 0.2s; background: none; border: none; }
.modal-close:hover { color: var(--text-primary); }
.modal-body { padding: 20px 24px; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.modal-footer {
  padding: 16px 24px; border-top: 1px solid var(--border-primary);
  display: flex; justify-content: flex-end; gap: 10px;
}
.modal-summary {
  background: var(--bg-secondary); border-radius: 8px; padding: 14px; margin-top: 12px;
}
.modal-summary-row { display: flex; justify-content: space-between; padding: 4px 0; }
.modal-summary-label { font-size: 11.5px; color: var(--text-muted); }
.modal-summary-value { font-size: 12px; font-family: 'JetBrains Mono', monospace; color: var(--text-primary); }
.modal-warning {
  background: var(--warning-dim); border-radius: 6px; padding: 10px 14px;
  margin-top: 12px; font-size: 11.5px; color: var(--warning);
  display: flex; gap: 8px; align-items: flex-start; line-height: 1.5;
}

@keyframes modal-fade-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes modal-slide-in {
  from { opacity: 0; transform: translateY(-10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* ── Toast ─────────────────────────────────────────────────── */
.toast-container {
  position: fixed; top: 20px; right: 20px; z-index: 1100;
  display: flex; flex-direction: column; gap: 8px;
}
.toast {
  padding: 12px 18px; border-radius: 8px; box-shadow: var(--shadow-md);
  display: flex; align-items: center; gap: 10px; font-size: 12.5px; font-weight: 500;
  animation: toast-in 0.3s ease; min-width: 300px; max-width: 420px;
}
.toast-success { background: var(--success-dim); border: 1px solid rgba(16,185,129,0.2); color: var(--success); }
.toast-info { background: var(--accent-dim); border: 1px solid rgba(6,182,212,0.2); color: var(--accent); }
.toast-warning { background: var(--warning-dim); border: 1px solid rgba(245,158,11,0.2); color: var(--warning); }
.toast-error { background: var(--danger-dim); border: 1px solid rgba(239,68,68,0.2); color: var(--danger); }
.toast i { font-size: 14px; flex-shrink: 0; }
.toast-dismiss {
  margin-left: auto; cursor: pointer; opacity: 0.6; font-size: 14px;
  background: none; border: none; color: inherit;
}
.toast-dismiss:hover { opacity: 1; }

@keyframes toast-in { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }

/* ── Responsive ───────────────────────────────────────────── */
@media (max-width: 1200px) {
  .wd-content { grid-template-columns: 1fr; }
  .wd-status-grid { grid-template-columns: repeat(2, 1fr); }
  .wd-form-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .wd-status-grid { grid-template-columns: 1fr; }
}

/* ── Symbol Input + Inline Lookback ───────────────────────── */
.wd-inline-row {
  display: flex; gap: 8px; align-items: center;
}
.wd-inline-row .wd-form-input { flex: 1; min-width: 0; }
.wd-inline-row .wd-form-select { flex: 0 0 130px; }
.wd-field-error {
  font-size: 10.5px; color: var(--danger); margin-top: 4px;
  display: none; align-items: center; gap: 4px;
}
.wd-field-error.visible { display: flex; }
.wd-field-error i { font-size: 10px; }
.wd-form-input.input-error { border-color: var(--danger); }
.wd-symbol-hint {
  font-size: 10px; color: var(--text-muted); margin-top: 3px;
  font-style: italic;
}
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
