# Repository Snapshot - Part 2 of 2

- Files in this chunk: `8`
## Full Project Tree

```text
app/__init__.py
app/config.py
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
worker/README.md
worker/requirements.txt
worker/strategyWorker.py
worker/worker_agent.py
```

## Files In This Chunk - Part 2

```text
app/config.py
app/services/__init__.py
app/services/mainServices.py
app/services/strategy_registry.py
ui/index.html
ui/js/main.js
ui/js/workerDetailRenderer.js
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
- Size bytes: `10230`
- SHA256: `3965580d6599b892ff28c35ab11fcf24c41a6e6a1411fcf4ce81dc668ab961aa`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Combined Runtime Services


"""

import random
import threading
import uuid
from datetime import datetime, timedelta, timezone

from app.config import Config


# =============================================================================
# Command Queue
# =============================================================================

_command_queues: dict = {}  # worker_id -> list of commands
_command_lock = threading.Lock()


def enqueue_command(worker_id: str, command_type: str, payload: dict) -> dict:
    """Push a command for a specific worker."""
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

    print(f"[COMMAND] Enqueued {command_type} ({cmd_id}) for worker {worker_id}")
    return cmd


def poll_commands(worker_id: str) -> list:
    """Return all pending commands for a worker."""
    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        pending = [c for c in queue if c["state"] == "pending"]

    return pending


def ack_command(worker_id: str, command_id: str) -> dict:
    """Mark a command as acknowledged."""
    now = datetime.now(timezone.utc)

    with _command_lock:
        queue = _command_queues.get(worker_id, [])

        for cmd in queue:
            if cmd["command_id"] == command_id:
                cmd["state"] = "acknowledged"
                cmd["acked_at"] = now.isoformat()
                print(f"[COMMAND] Ack {command_id} from worker {worker_id}")
                return {"ok": True, "command": cmd}

    return {"ok": False, "error": "Command not found."}


# =============================================================================
# Deployment Registry
# =============================================================================

_deployments: dict = {}
_deployment_lock = threading.Lock()

VALID_STATES = {
    "queued",
    "sent_to_worker",
    "acknowledged_by_worker",
    "loading_strategy",
    "fetching_ticks",
    "generating_initial_bars",
    "warming_up",
    "running",
    "stopped",
    "failed",
}


def create_deployment(config: dict) -> dict:
    """
    Create a new deployment record.

    config must include:
    - strategy_id
    - worker_id
    - symbol
    - bar_size_points

    Optional:
    - max_bars_in_memory
    - tick_lookback_value
    - tick_lookback_unit
    - lot_size
    - strategy_parameters
    """
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
        "strategy_parameters": config.get("strategy_parameters", {}),
        "state": "queued",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "last_error": None,
    }

    with _deployment_lock:
        _deployments[deployment_id] = record

    print(
        f"[DEPLOYMENT] Created {deployment_id} | "
        f"strategy={config['strategy_id']} → worker={config['worker_id']}"
    )

    return {
        "ok": True,
        "deployment_id": deployment_id,
        "deployment": record,
    }


def get_all_deployments() -> list:
    with _deployment_lock:
        return list(_deployments.values())


def get_deployment(deployment_id: str) -> dict | None:
    with _deployment_lock:
        return _deployments.get(deployment_id)


def update_deployment_state(
    deployment_id: str,
    state: str,
    error: str = None,
) -> dict:
    """Update deployment state. Returns updated record or error."""
    if state not in VALID_STATES:
        return {"ok": False, "error": f"Invalid state: {state}"}

    now = datetime.now(timezone.utc)

    with _deployment_lock:
        rec = _deployments.get(deployment_id)

        if not rec:
            return {"ok": False, "error": "Deployment not found."}

        rec["state"] = state
        rec["updated_at"] = now.isoformat()

        if error is not None:
            rec["last_error"] = error
        elif state == "running":
            rec["last_error"] = None

    print(
        f"[DEPLOYMENT] {deployment_id} → {state}"
        + (f" (error: {error})" if error else "")
    )

    return {"ok": True, "deployment": rec}


def stop_deployment(deployment_id: str) -> dict:
    return update_deployment_state(deployment_id, "stopped")


def get_deployments_for_worker(worker_id: str) -> list:
    with _deployment_lock:
        return [
            d for d in _deployments.values()
            if d["worker_id"] == worker_id
        ]


# =============================================================================
# Mock Data Service
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

        points.append({
            "timestamp": d.strftime("%Y-%m-%d"),
            "equity": round(val, 2),
        })

    return points


# =============================================================================
# Worker Registry
# =============================================================================

_workers: dict = {}
_worker_lock = threading.Lock()


def process_heartbeat(payload: dict) -> dict:
    worker_id = payload["worker_id"].strip()
    now = datetime.now(timezone.utc)
    is_new = False

    with _worker_lock:
        if worker_id not in _workers:
            is_new = True
            print(
                f"[HEARTBEAT] Worker '{worker_id}' registered | "
                f"state={payload.get('state', 'unknown')}"
            )
        else:
            print(
                f"[HEARTBEAT] Worker '{worker_id}' updated | "
                f"state={payload.get('state', 'unknown')}"
            )

        _workers[worker_id] = {
            "worker_id": worker_id,
            "worker_name": payload.get("worker_name"),
            "host": payload.get("host"),
            "reported_state": payload.get("state", "online"),
            "last_heartbeat_at": now.isoformat(),
            "_last_heartbeat_dt": now,
            "agent_version": payload.get("agent_version"),
            "mt5_state": payload.get("mt5_state"),
            "account_id": payload.get("account_id"),
            "broker": payload.get("broker"),
            "active_strategies": payload.get("active_strategies", []) or [],
            "open_positions_count": payload.get("open_positions_count", 0) or 0,
            "floating_pnl": payload.get("floating_pnl"),
            "errors": payload.get("errors", []) or [],
        }

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
        for wid, rec in _workers.items():
            age = round((now - rec["_last_heartbeat_dt"]).total_seconds(), 1)
            reported = rec["reported_state"]

            if age >= offline_threshold:
                effective = "offline"
            elif age >= stale_threshold:
                effective = "stale"
            else:
                effective = reported

            result.append({
                "worker_id": rec["worker_id"],
                "worker_name": rec["worker_name"],
                "host": rec["host"],
                "state": effective,
                "reported_state": reported,
                "last_heartbeat_at": rec["last_heartbeat_at"],
                "heartbeat_age_seconds": age,
                "agent_version": rec["agent_version"],
                "mt5_state": rec["mt5_state"],
                "account_id": rec["account_id"],
                "broker": rec["broker"],
                "active_strategies": rec["active_strategies"],
                "open_positions_count": rec["open_positions_count"],
                "floating_pnl": rec["floating_pnl"],
                "errors": rec["errors"],
            })

    return result


def get_fleet_summary() -> dict:
    workers = get_all_workers()

    counts = {
        "online_workers": 0,
        "stale_workers": 0,
        "offline_workers": 0,
        "error_workers": 0,
        "warning_workers": 0,
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

## FILE: `app/services/strategy_registry.py`

- Relative path: `app/services/strategy_registry.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/services/strategy_registry.py`
- Size bytes: `13393`
- SHA256: `f29791d5321e33bf411b0f91d43ea3a18f478be7e4c4af9f86c008789ef488cc`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid – Strategy Registry
Persistent strategy store using filesystem (JSON sidecar + .py code).
Survives server restarts. No database required.
app/services/strategy_registry.py
"""
import ast
import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from typing import Optional

_strategies: dict = {}
_lock = threading.Lock()

# ── Storage Path ────────────────────────────────────────────────
# Lives under <project_root>/data/strategies/ — intentionally OUTSIDE
# the app/ and ui/ source trees so uvicorn's file-watcher never sees
# writes here, even when reload=True.

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(_THIS_DIR)
_PROJECT_ROOT = os.path.dirname(_APP_DIR)
STRATEGIES_DIR = os.path.join(_PROJECT_ROOT, "data", "strategies")
os.makedirs(STRATEGIES_DIR, exist_ok=True)

# Legacy dir (Phase 1C wrote here — inside the reload zone)
_LEGACY_DIR = os.path.join(_PROJECT_ROOT, "strategies")


# ── Filename Sanitization ───────────────────────────────────────

_SAFE_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _sanitize_id(raw: str) -> str:
    """Strip unsafe chars, cap length, guarantee non-empty."""
    clean = _SAFE_RE.sub("_", raw.strip()).strip("_")[:64]
    return clean or "unnamed_strategy"


def _safe_path(filename: str) -> str:
    """Resolve inside STRATEGIES_DIR with traversal protection."""
    safe = os.path.basename(filename)
    full = os.path.realpath(os.path.join(STRATEGIES_DIR, safe))
    if not full.startswith(os.path.realpath(STRATEGIES_DIR)):
        raise ValueError(f"Path traversal blocked: {filename}")
    return full


def _code_path(sid: str) -> str:
    return _safe_path(f"{_sanitize_id(sid)}.py")


def _meta_path(sid: str) -> str:
    return _safe_path(f"{_sanitize_id(sid)}.meta.json")


# ── Atomic Write ────────────────────────────────────────────────

def _write_atomic(target: str, content: str) -> None:
    """Write to temp file in the same dir, then atomic rename."""
    parent = os.path.dirname(target)
    fd, tmp = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        shutil.move(tmp, target)          # same-fs → os.rename (atomic)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── Metadata Persistence ───────────────────────────────────────

def _save_meta(sid: str, record: dict) -> None:
    serialisable = {k: v for k, v in record.items() if k != "file_path"}
    _write_atomic(_meta_path(sid), json.dumps(serialisable, indent=2))


def _load_meta(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[STRATEGY] Bad metadata {path}: {exc}")
        return None


# ── AST Validation (unchanged logic) ───────────────────────────

def _ast_literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _validate_strategy_file(file_content: str) -> dict:
    result = {
        "valid": False, "error": None, "class_name": None,
        "strategy_id": None, "name": None, "description": None,
        "version": None, "min_lookback": None, "parameters": {},
    }
    try:
        tree = ast.parse(file_content)
    except SyntaxError as e:
        result["error"] = f"SyntaxError: {e}"
        return result

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(b.attr)
        if "BaseStrategy" not in bases:
            continue

        result["class_name"] = node.name
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if not isinstance(target, ast.Name):
                    continue
                val = _ast_literal(item.value)
                name = target.id
                if name == "strategy_id" and val is not None:
                    result["strategy_id"] = str(val)
                elif name == "name" and val is not None:
                    result["name"] = str(val)
                elif name == "description" and val is not None:
                    result["description"] = str(val)
                elif name == "version" and val is not None:
                    result["version"] = str(val)
                elif name == "min_lookback" and val is not None:
                    result["min_lookback"] = val
                elif name == "parameters" and isinstance(item.value, ast.Dict):
                    try:
                        result["parameters"] = ast.literal_eval(item.value)
                    except (ValueError, TypeError):
                        result["parameters"] = {}

        if result["strategy_id"]:
            result["valid"] = True
        else:
            result["strategy_id"] = node.name.lower()
            result["valid"] = True
        break

    if result["class_name"] is None:
        result["error"] = "No class extending BaseStrategy found in file."
    return result


# ── Startup Restore ─────────────────────────────────────────────

def load_strategies_from_disk() -> int:
    """
    Scan STRATEGIES_DIR for *.meta.json, restore into memory.
    Also migrates any orphan .py files from the legacy strategies/ dir.
    Called ONCE at server startup.
    """
    _migrate_legacy_dir()

    count = 0
    if not os.path.isdir(STRATEGIES_DIR):
        print("[STRATEGY] Startup: storage dir missing — nothing to load.")
        return 0

    for fname in sorted(os.listdir(STRATEGIES_DIR)):
        if not fname.endswith(".meta.json"):
            continue
        meta = _load_meta(os.path.join(STRATEGIES_DIR, fname))
        if not meta:
            continue
        sid = meta.get("strategy_id")
        if not sid:
            print(f"[STRATEGY] Skipping {fname}: no strategy_id")
            continue
        code = _code_path(sid)
        if not os.path.exists(code):
            print(f"[STRATEGY] Skipping {sid}: .py missing at {code}")
            continue
        meta["file_path"] = code
        with _lock:
            _strategies[sid] = meta
        count += 1
        print(f"[STRATEGY] Restored: {sid} ({meta.get('strategy_name', '?')})")

    print(f"[STRATEGY] Startup complete — {count} strategies loaded from {STRATEGIES_DIR}")
    return count


def _migrate_legacy_dir() -> None:
    """
    One-time migration: if the old <root>/strategies/ dir has .py files
    without corresponding entries in data/strategies/, re-validate and move.
    """
    if not os.path.isdir(_LEGACY_DIR):
        return
    migrated = 0
    for fname in os.listdir(_LEGACY_DIR):
        if not fname.endswith(".py"):
            continue
        src = os.path.join(_LEGACY_DIR, fname)
        try:
            with open(src, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        validation = _validate_strategy_file(content)
        if not validation["valid"]:
            print(f"[STRATEGY] Legacy skip (invalid): {fname}")
            continue
        sid = _sanitize_id(validation["strategy_id"])
        if os.path.exists(_code_path(sid)):
            continue  # already in new location
        # Migrate
        try:
            _write_atomic(_code_path(sid), content)
            now = datetime.now(timezone.utc)
            record = _build_record(sid, validation, now)
            _save_meta(sid, record)
            os.unlink(src)
            migrated += 1
            print(f"[STRATEGY] Migrated legacy: {fname} → {sid}")
        except Exception as e:
            print(f"[STRATEGY] Migration failed for {fname}: {e}")
    if migrated:
        print(f"[STRATEGY] Migrated {migrated} strategies from legacy dir.")


# ── Record Builder ──────────────────────────────────────────────

def _build_record(sid: str, validation: dict, now: datetime) -> dict:
    return {
        "strategy_id": sid,
        "strategy_name": validation["name"] or sid,
        "class_name": validation["class_name"],
        "version": validation["version"] or "unknown",
        "description": validation["description"] or "",
        "min_lookback": validation["min_lookback"],
        "parameters": validation["parameters"],
        "parameter_count": len(validation["parameters"]),
        "filename": f"{sid}.py",
        "file_path": _code_path(sid),
        "uploaded_at": now.isoformat(),
        "validation_status": "validated",
        "load_status": "registered",
        "error": None,
    }


# ── Public API ──────────────────────────────────────────────────

def upload_strategy(filename: str, file_content: str) -> dict:
    """Validate → atomic-write .py + .meta.json → register in memory."""

    if not filename.endswith(".py"):
        return {"ok": False, "error": "Only .py files accepted."}
    if not file_content or not file_content.strip():
        return {"ok": False, "error": "Empty file content."}

    validation = _validate_strategy_file(file_content)
    if not validation["valid"]:
        return {
            "ok": False,
            "error": validation["error"] or "Validation failed.",
            "validation": validation,
        }

    sid = _sanitize_id(validation["strategy_id"])
    now = datetime.now(timezone.utc)

    # ---- persist code ----
    code_file = _code_path(sid)
    try:
        _write_atomic(code_file, file_content)
    except Exception as e:
        print(f"[STRATEGY] Code write failed: {e}")
        return {"ok": False, "error": f"Failed to save strategy file: {e}"}

    # ---- persist metadata ----
    record = _build_record(sid, validation, now)
    try:
        _save_meta(sid, record)
    except Exception as e:
        print(f"[STRATEGY] Meta write failed: {e}")
        try:
            os.unlink(code_file)
        except OSError:
            pass
        return {"ok": False, "error": f"Failed to save metadata: {e}"}

    # ---- register in memory ----
    with _lock:
        _strategies[sid] = record

    print(f"[STRATEGY] Registered '{sid}' from {filename} (class={validation['class_name']})")
    return {
        "ok": True,
        "strategy_id": sid,
        "strategy_name": record["strategy_name"],
        "validation": validation,
    }


def get_all_strategies() -> list:
    with _lock:
        return list(_strategies.values())


def get_strategy(strategy_id: str) -> dict | None:
    with _lock:
        return _strategies.get(strategy_id)


def get_strategy_file_content(strategy_id: str) -> str | None:
    rec = get_strategy(strategy_id)
    if not rec:
        return None
    path = rec.get("file_path")
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def validate_strategy(strategy_id: str) -> dict:
    rec = get_strategy(strategy_id)
    if not rec:
        return {"ok": False, "error": "Strategy not found."}
    content = get_strategy_file_content(strategy_id)
    if not content:
        return {"ok": False, "error": "Strategy file missing from disk."}
    validation = _validate_strategy_file(content)
    with _lock:
        if strategy_id in _strategies:
            _strategies[strategy_id]["validation_status"] = (
                "validated" if validation["valid"] else "failed"
            )
            _strategies[strategy_id]["error"] = validation.get("error")
    try:
        _save_meta(strategy_id, _strategies[strategy_id])
    except Exception as e:
        print(f"[STRATEGY] Meta update after re-validate failed: {e}")
    return {"ok": validation["valid"], "validation": validation}


def delete_strategy(strategy_id: str) -> dict:
    """Remove strategy from memory + disk."""
    with _lock:
        rec = _strategies.pop(strategy_id, None)
    if not rec:
        return {"ok": False, "error": "Strategy not found."}

    for path in (_code_path(strategy_id), _meta_path(strategy_id)):
        try:
            if os.path.exists(path):
                os.unlink(path)
                print(f"[STRATEGY] Deleted file: {path}")
        except OSError as e:
            print(f"[STRATEGY] Delete failed {path}: {e}")

    print(f"[STRATEGY] Removed '{strategy_id}'")
    return {"ok": True, "strategy_id": strategy_id}
```

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

## FILE: `ui/js/main.js`

- Relative path: `ui/js/main.js`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/js/main.js`
- Size bytes: `35785`
- SHA256: `1c0f0c43a4b955c53198af0012ea5df08d815e9faa549d7549db156b6c734859`
- Guessed MIME type: `text/javascript`
- Guessed encoding: `unknown`

```javascript
/* main.js
*/

var ApiClient = (function () {
  'use strict';

  function _request(method, path, body) {
    var opts = { method: method };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          var msg = 'HTTP ' + res.status;
          try {
            var json = JSON.parse(text);
            if (json.detail) {
              msg = typeof json.detail === 'string' ? json.detail
                : (json.detail.error || JSON.stringify(json.detail));
            }
          } catch (e) {
            if (text) msg = text;
          }
          var err = new Error(msg);
          err.status = res.status;
          throw err;
        });
      }
      return res.json();
    });
  }

  function _upload(path, file) {
    var fd = new FormData();
    fd.append('file', file);
    return fetch(path, { method: 'POST', body: fd }).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          var msg = 'HTTP ' + res.status;
          try {
            var json = JSON.parse(text);
            if (json.detail) {
              msg = typeof json.detail === 'string' ? json.detail
                : (json.detail.error || JSON.stringify(json.detail));
            }
          } catch (e) {
            if (text) msg = text;
          }
          throw new Error(msg);
        });
      }
      return res.json();
    });
  }

  return {

    getFleetWorkers: function () {
      return _request('GET', '/api/Grid/workers');
    },
    getSystemSummary: function () {
      return _request('GET', '/api/system/summary');
    },
    getHealth: function () {
      return _request('GET', '/api/health');
    },


    getStrategies: function () {
      return _request('GET', '/api/grid/strategies');
    },
    getStrategy: function (id) {
      return _request('GET', '/api/grid/strategies/' + encodeURIComponent(id));
    },
    uploadStrategy: function (file) {
      return _upload('/api/grid/strategies/upload', file);
    },
    validateStrategy: function (id) {
      return _request('POST', '/api/grid/strategies/' + encodeURIComponent(id) + '/validate');
    },


    createDeployment: function (cfg) {
      return _request('POST', '/api/grid/deployments', cfg);
    },
    getDeployments: function () {
      return _request('GET', '/api/grid/deployments');
    },
    getDeployment: function (id) {
      return _request('GET', '/api/grid/deployments/' + encodeURIComponent(id));
    },
    stopDeployment: function (id) {
      return _request('POST', '/api/grid/deployments/' + encodeURIComponent(id) + '/stop');
    }
  };
})();


var DeploymentConfig = (function () {
  'use strict';

  var runtimeDefaults = {
    symbol: 'EURUSD',
    lot_size: 0.01,
    tick_lookback_value: 30,
    tick_lookback_unit: 'minutes',
    bar_size_points: 100,
    max_bars_memory: 500
  };

  var symbolOptions = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD',
    'USDCHF', 'NZDUSD', 'XAUUSD', 'BTCUSD', 'USTEC',
    'SPX500', 'DOW30', 'FTSE100'
  ];

  var tickLookbackUnits = ['minutes', 'hours', 'days'];

  return {
    runtimeDefaults: runtimeDefaults,
    symbolOptions: symbolOptions,
    tickLookbackUnits: tickLookbackUnits
  };
})();


var ModalManager = (function () {
  'use strict';

  var _overlay = null;

  function show(options) {
    hide();

    var title = options.title || 'Confirm';
    var bodyHtml = options.bodyHtml || '';
    var confirmText = options.confirmText || 'Confirm';
    var cancelText = options.cancelText || 'Cancel';
    var type = options.type || 'default';
    var onConfirm = options.onConfirm || function () {};

    var confirmClass = type === 'danger' ? 'wd-btn wd-btn-primary' : 'wd-btn wd-btn-primary';
    var confirmStyle = type === 'danger' ? ' style="background:var(--danger);"' : '';

    _overlay = document.createElement('div');
    _overlay.className = 'modal-overlay';
    _overlay.innerHTML =
      '<div class="modal-card">' +
        '<div class="modal-header">' +
          '<span class="modal-title">' + title + '</span>' +
          '<button class="modal-close" id="modal-close">&times;</button>' +
        '</div>' +
        '<div class="modal-body">' + bodyHtml + '</div>' +
        '<div class="modal-footer">' +
          '<button class="wd-btn wd-btn-ghost" id="modal-cancel">' + cancelText + '</button>' +
          '<button class="' + confirmClass + '" id="modal-confirm"' + confirmStyle + '>' + confirmText + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(_overlay);

    _overlay.querySelector('#modal-close').addEventListener('click', hide);
    _overlay.querySelector('#modal-cancel').addEventListener('click', hide);
    _overlay.querySelector('#modal-confirm').addEventListener('click', function () {
      onConfirm();
      hide();
    });

    _overlay.addEventListener('click', function (e) {
      if (e.target === _overlay) hide();
    });

    var escHandler = function (e) {
      if (e.key === 'Escape') {
        hide();
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  function hide() {
    if (_overlay && _overlay.parentNode) {
      _overlay.parentNode.removeChild(_overlay);
    }
    _overlay = null;
  }

  return {
    show: show,
    hide: hide
  };
})();


var ToastManager = (function () {
  'use strict';

  var iconMap = {
    success: 'fa-circle-check',
    info: 'fa-circle-info',
    warning: 'fa-triangle-exclamation',
    error: 'fa-circle-xmark'
  };

  function _getContainer() {
    var container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function show(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;

    var container = _getContainer();
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML =
      '<i class="fa-solid ' + (iconMap[type] || iconMap.info) + '"></i>' +
      '<span>' + message + '</span>' +
      '<button class="toast-dismiss"><i class="fa-solid fa-xmark"></i></button>';

    container.appendChild(toast);

    var dismiss = toast.querySelector('.toast-dismiss');
    dismiss.addEventListener('click', function () {
      _remove(toast);
    });

    setTimeout(function () {
      _remove(toast);
    }, duration);
  }

  function _remove(toast) {
    if (!toast || !toast.parentNode) return;

    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';

    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }

  return {
    show: show
  };
})();


var ThemeManager = (function () {
  'use strict';

  var STORAGE_KEY = 'jinni-Grid-theme';
  var currentTheme = 'dark';

  function init() {
    var saved = localStorage.getItem(STORAGE_KEY);
    currentTheme = saved === 'light' ? 'light' : 'dark';
    applyTheme();
    updateToggleButton();

    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggle);
  }

  function toggle() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(STORAGE_KEY, currentTheme);
    applyTheme();
    updateToggleButton();

    if (typeof DashboardRenderer !== 'undefined' && DashboardRenderer.onThemeChange) {
      DashboardRenderer.onThemeChange();
    }
  }

  function applyTheme() {
    document.body.setAttribute('data-theme', currentTheme);
  }

  function updateToggleButton() {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;

    var icon = btn.querySelector('i');
    var label = btn.querySelector('span');

    if (currentTheme === 'dark') {
      icon.className = 'fa-solid fa-sun';
      label.textContent = 'Light Mode';
    } else {
      icon.className = 'fa-solid fa-moon';
      label.textContent = 'Dark Mode';
    }
  }

  function getTheme() {
    return currentTheme;
  }

  return {
    init: init,
    toggle: toggle,
    getTheme: getTheme
  };
})();


var DashboardRenderer = (function () {
  'use strict';

  var _fleetInterval = null;
  var _kpiInterval = null;
  var _lastFleetWorkers = [];

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">—</span>';

    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '') {
      return '<span class="value-null">' + (fallback || '—') + '</span>';
    }
    return val;
  }

  function kpiCard(icon, label, value, sentiment) {
    var valueClass = '';
    if (sentiment === 'positive') valueClass = ' positive';
    else if (sentiment === 'negative') valueClass = ' negative';

    return '<div class="portfolio-card">' +
      '<div class="card-icon ' + sentiment + '"><i class="fa-solid ' + icon + '"></i></div>' +
      '<div class="card-info"><div class="card-value' + valueClass + '">' + value + '</div>' +
      '<div class="card-label">' + label + '</div></div></div>';
  }

  function fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count +
      '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _fetchKPIs() {
    var el = document.getElementById('dashboard-kpi-content');
    if (!el) return;

    Promise.all([
      ApiClient.getStrategies().catch(function () {
        return { strategies: [] };
      }),
      ApiClient.getDeployments().catch(function () {
        return { deployments: [] };
      }),
      ApiClient.getSystemSummary().catch(function () {
        return {};
      })
    ]).then(function (results) {
      var strats = results[0].strategies || [];
      var deps = results[1].deployments || [];
      var sys = results[2];

      var registeredCount = strats.length;
      var activeDeployments = deps.filter(function (d) {
        return [
          'queued',
          'sent_to_worker',
          'acknowledged_by_worker',
          'loading_strategy',
          'fetching_ticks',
          'generating_initial_bars',
          'warming_up',
          'running'
        ].indexOf(d.state) !== -1;
      }).length;

      var runningCount = deps.filter(function (d) {
        return d.state === 'running';
      }).length;

      var failedCount = deps.filter(function (d) {
        return d.state === 'failed';
      }).length;

      var onlineWorkers = sys.online_nodes || 0;
      var totalWorkers = sys.total_nodes || 0;

      var html = '<div class="portfolio-grid">';
      html += kpiCard('fa-crosshairs', 'Registered Strategies', String(registeredCount), 'neutral');
      html += kpiCard('fa-rocket', 'Active Deployments', String(activeDeployments), activeDeployments > 0 ? 'positive' : 'neutral');
      html += kpiCard('fa-play', 'Running Runners', String(runningCount), runningCount > 0 ? 'positive' : 'neutral');
      html += kpiCard('fa-triangle-exclamation', 'Failed Deployments', String(failedCount), failedCount > 0 ? 'negative' : 'neutral');
      html += kpiCard('fa-server', 'Online Workers', onlineWorkers + ' / ' + totalWorkers, onlineWorkers > 0 ? 'positive' : 'warning');
      html += '</div>';

      el.innerHTML = html;
    });
  }

  function _fetchDashboardFleet() {
    var el = document.getElementById('dashboard-fleet-content');
    if (!el) return;

    ApiClient.getFleetWorkers()
      .then(function (data) {
        var s = data.summary || {};
        var workers = data.workers || [];

        _lastFleetWorkers = workers;

        var html = '<div class="fleet-summary">';
        html += fleetBadge(s.total_workers || 0, 'Total', 'total');
        html += fleetBadge(s.online_workers || 0, 'Online', 'online');
        html += fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
        html += fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
        html += fleetBadge(s.error_workers || 0, 'Error', 'error');
        html += '</div>';

        if (workers.length > 0) {
          html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">';
          html += '<thead><tr><th>Worker</th><th>State</th><th>Host</th><th>Strategy</th><th>Heartbeat</th></tr></thead><tbody>';

          workers.forEach(function (w) {
            var name = w.worker_name || w.worker_id;
            var state = w.state || 'unknown';
            var strats = w.active_strategies && w.active_strategies.length > 0
              ? w.active_strategies.join(', ')
              : '<span class="value-null">—</span>';

            html += '<tr class="clickable" onclick="DashboardRenderer._openWorker(\'' + w.worker_id + '\')">';
            html += '<td class="mono">' + name + '</td>';
            html += '<td><span class="state-pill ' + state + '">' + state.toUpperCase() + '</span></td>';
            html += '<td class="mono">' + _nullVal(w.host) + '</td>';
            html += '<td class="mono">' + strats + '</td>';
            html += '<td class="mono">' + _formatAge(w.heartbeat_age_seconds) + '</td>';
            html += '</tr>';
          });

          html += '</tbody></table></div>';
        } else {
          html += '<div style="padding:16px 0;color:var(--text-muted);font-size:12.5px;">' +
            '<i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>' +
            'No workers connected yet — start a worker agent to see fleet data.</div>';
        }

        html += '<span class="view-fleet-link" onclick="App.navigateTo(\'fleet\')">' +
          'View Fleet <i class="fa-solid fa-arrow-right"></i></span>';

        el.innerHTML = html;
      })
      .catch(function () {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">' +
          '<i class="fa-solid fa-circle-exclamation" style="margin-right:6px;color:var(--danger);opacity:0.6;"></i>' +
          'Could not load fleet data from backend.</div>';
      });
  }

  function _openWorker(workerId) {
    for (var i = 0; i < _lastFleetWorkers.length; i++) {
      if (_lastFleetWorkers[i].worker_id === workerId) {
        App.navigateToWorkerDetail(_lastFleetWorkers[i]);
        return;
      }
    }
  }

  function _fetchDeployments() {
    var el = document.getElementById('dashboard-deploy-content');
    if (!el) return;

    ApiClient.getDeployments().then(function (data) {
      var deps = data.deployments || [];

      if (deps.length === 0) {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12.5px;">' +
          '<i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>' +
          'No deployments yet. Deploy a strategy from the Worker Detail page.</div>';
        return;
      }

      deps = deps.slice().reverse();

      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">';
      html += '<thead><tr><th>Deployment</th><th>Strategy</th><th>Worker</th><th>Symbol</th><th>State</th><th>Updated</th></tr></thead><tbody>';

      deps.forEach(function (d) {
        var stateClass = _deployStateClass(d.state);
        var updated = d.updated_at ? d.updated_at.replace('T', ' ').substring(0, 19) : '—';

        html += '<tr>';
        html += '<td class="mono">' + d.deployment_id + '</td>';
        html += '<td class="mono">' + d.strategy_id + '</td>';
        html += '<td class="mono">' + d.worker_id + '</td>';
        html += '<td class="mono">' + d.symbol + '</td>';
        html += '<td><span class="state-pill ' + stateClass + '">' + d.state.toUpperCase().replace(/_/g, ' ') + '</span></td>';
        html += '<td class="mono">' + updated + '</td>';
        html += '</tr>';

        if (d.last_error) {
          html += '<tr><td colspan="6" style="color:var(--danger);font-size:11px;padding:4px 12px;">' +
            '<i class="fa-solid fa-circle-xmark" style="margin-right:4px;"></i>' + d.last_error + '</td></tr>';
        }
      });

      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function () {
      el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">' +
        '<i class="fa-solid fa-circle-exclamation" style="margin-right:6px;color:var(--danger);opacity:0.6;"></i>' +
        'Could not load deployment data.</div>';
    });
  }

  function _deployStateClass(state) {
    if (!state) return 'unknown';
    if (state === 'running') return 'online';
    if (state === 'failed') return 'error';
    if (state === 'stopped') return 'offline';

    if (
      state.indexOf('loading') !== -1 ||
      state.indexOf('fetching') !== -1 ||
      state.indexOf('generating') !== -1 ||
      state.indexOf('warming') !== -1
    ) {
      return 'warning';
    }

    if (
      state === 'queued' ||
      state.indexOf('sent') !== -1 ||
      state.indexOf('acknowledged') !== -1
    ) {
      return 'stale';
    }

    return 'unknown';
  }

  function render() {
    var html = '<div class="dashboard">';

    html += '<section><div class="section-header"><i class="fa-solid fa-gauge-high"></i><h2>System KPIs</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-kpi-content"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div><p>Loading…</p></div></div></section>';

    html += '<section><div class="section-header"><i class="fa-solid fa-server"></i><h2>Fleet Overview</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-fleet-content" class="dashboard-fleet-section">';
    html += '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading fleet data…</p></div>';
    html += '</div></section>';

    html += '<section><div class="section-header"><i class="fa-solid fa-rocket"></i><h2>Recent Deployments</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-deploy-content"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div><p>Loading…</p></div></div></section>';

    html += '</div>';

    document.getElementById('main-content').innerHTML = html;

    _fetchKPIs();
    _fetchDashboardFleet();
    _fetchDeployments();

    _fleetInterval = setInterval(function () {
      _fetchDashboardFleet();
      _fetchDeployments();
    }, 10000);

    _kpiInterval = setInterval(_fetchKPIs, 15000);
  }

  function destroy() {
    if (_fleetInterval) {
      clearInterval(_fleetInterval);
      _fleetInterval = null;
    }

    if (_kpiInterval) {
      clearInterval(_kpiInterval);
      _kpiInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _openWorker: _openWorker
  };
})();


var FleetRenderer = (function () {
  'use strict';

  var _refreshInterval = null;
  var _lastFetchTime = null;
  var _lastWorkers = [];
  var REFRESH_MS = 5000;

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">—</span>';

    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '') {
      return '<span class="value-null">' + (fallback || '—') + '</span>';
    }
    return String(val);
  }

  function _formatPnl(val) {
    if (val === null || val === undefined) return '<span class="value-null">—</span>';

    var sign = val >= 0 ? '+' : '';
    return sign + '$' + val.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function _stateLabel(state) {
    if (!state) return 'Unknown';
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

  function fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count +
      '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _infoRow(label, value) {
    return '<div class="node-info-row"><span class="node-info-label">' + label +
      '</span><span class="node-info-value">' + value + '</span></div>';
  }

  function renderNodeCard(w) {
    var state = w.state || 'unknown';
    var name = w.worker_name || w.worker_id;

    var strategies = w.active_strategies && w.active_strategies.length > 0
      ? w.active_strategies.join(', ')
      : null;

    var errorsStr = w.errors && w.errors.length > 0
      ? w.errors.join(', ')
      : null;

    var pnlVal = _formatPnl(w.floating_pnl);
    var pnlClass = '';

    if (w.floating_pnl !== null && w.floating_pnl !== undefined) {
      pnlClass = w.floating_pnl >= 0
        ? ' style="color:var(--success)"'
        : ' style="color:var(--danger)"';
    }

    return (
      '<div class="node-card clickable" onclick="FleetRenderer._openWorker(\'' + w.worker_id + '\')">' +
        '<div class="node-card-top ' + state + '"></div>' +
        '<div class="node-card-header">' +
          '<div class="node-name-group">' +
            '<span class="node-status-dot ' + state + '"></span>' +
            '<span class="node-name">' + name + '</span>' +
          '</div>' +
          '<span class="node-status-badge ' + state + '">' + _stateLabel(state) + '</span>' +
        '</div>' +
        '<div class="node-card-body">' +
          _infoRow('Worker ID', '<span class="mono">' + w.worker_id + '</span>') +
          _infoRow('Host', _nullVal(w.host)) +
          _infoRow('MT5', _nullVal(w.mt5_state, 'Unknown')) +
          _infoRow('Broker', _nullVal(w.broker)) +
          _infoRow('Account', _nullVal(w.account_id)) +
          _infoRow('Strategies', _nullVal(strategies, 'No active strategy')) +
          _infoRow('Positions', String(w.open_positions_count || 0)) +
          _infoRow('Float PnL', '<span' + pnlClass + '>' + pnlVal + '</span>') +
          _infoRow('Heartbeat', _formatAge(w.heartbeat_age_seconds)) +
          _infoRow('Agent', _nullVal(w.agent_version)) +
          _infoRow('Errors', _nullVal(errorsStr, 'None')) +
          '<div class="node-card-action"><i class="fa-solid fa-arrow-right"></i> View / Deploy Strategy</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderContent(data) {
    var headerEl = document.getElementById('fleet-page-header');
    var contentEl = document.getElementById('fleet-content');
    if (!contentEl) return;

    var workers = data.workers || [];
    var s = data.summary || {};

    _lastWorkers = workers;

    if (headerEl) {
      _lastFetchTime = new Date();

      var timeStr = _lastFetchTime.toLocaleTimeString('en-GB', {
        hour12: false
      });

      headerEl.style.display = 'flex';

      var metaEl = headerEl.querySelector('.last-synced');
      if (metaEl) metaEl.textContent = 'Synced: ' + timeStr;
    }

    if (workers.length === 0) {
      contentEl.innerHTML =
        '<div class="empty-state">' +
          '<i class="fa-solid fa-server"></i>' +
          '<h3>No Worker VMs Connected</h3>' +
          '<p>Start a worker agent and send heartbeat to this Mother Server to see workers here.</p>' +
          '<p>Endpoint: <code>POST /api/grid/workers/heartbeat</code></p>' +
        '</div>';
      return;
    }

    var html = '';
    html += '<div class="fleet-summary">';
    html += fleetBadge(s.total_workers || 0, 'Total', 'total');
    html += fleetBadge(s.online_workers || 0, 'Online', 'online');
    html += fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
    html += fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
    html += fleetBadge(s.error_workers || 0, 'Error', 'error');
    html += '</div>';

    html += '<div class="fleet-grid">';
    workers.forEach(function (w) {
      html += renderNodeCard(w);
    });
    html += '</div>';

    contentEl.innerHTML = html;
  }

  function _renderError() {
    var contentEl = document.getElementById('fleet-content');
    if (!contentEl) return;

    contentEl.innerHTML =
      '<div class="error-state">' +
        '<i class="fa-solid fa-triangle-exclamation"></i>' +
        '<h3>Failed to Load Fleet Data</h3>' +
        '<p>Could not connect to the Mother Server API. Check that the backend is running.</p>' +
        '<button class="retry-btn" onclick="FleetRenderer._retry()">Retry</button>' +
      '</div>';
  }

  function _fetchFleetData() {
    ApiClient.getFleetWorkers().then(_renderContent).catch(_renderError);
  }

  function _openWorker(workerId) {
    for (var i = 0; i < _lastWorkers.length; i++) {
      if (_lastWorkers[i].worker_id === workerId) {
        App.navigateToWorkerDetail(_lastWorkers[i]);
        return;
      }
    }
  }

  function render() {
    var html =
      '<div class="fleet-page">' +
        '<div class="fleet-page-header" id="fleet-page-header" style="display:none;">' +
          '<span class="fleet-page-title"><i class="fa-solid fa-server" style="color:var(--accent);margin-right:8px;"></i>Fleet Management</span>' +
          '<div class="fleet-page-meta">' +
            '<div class="auto-refresh-badge"><span class="auto-refresh-dot"></span>Auto-refresh</div>' +
            '<span class="last-synced">Synced: --:--:--</span>' +
          '</div>' +
        '</div>' +
        '<div id="fleet-content">' +
          '<div class="loading-state"><div class="spinner"></div><p>Loading fleet data…</p></div>' +
        '</div>' +
      '</div>';

    document.getElementById('main-content').innerHTML = html;

    _fetchFleetData();
    _refreshInterval = setInterval(_fetchFleetData, REFRESH_MS);
  }

  function destroy() {
    if (_refreshInterval) {
      clearInterval(_refreshInterval);
      _refreshInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _retry: _fetchFleetData,
    _openWorker: _openWorker
  };
})();


var StrategiesRenderer = (function () {
  'use strict';

  var _refreshInterval = null;

  function render() {
    var html =
      '<div class="fleet-page">' +
        '<div class="fleet-page-header">' +
          '<span class="fleet-page-title"><i class="fa-solid fa-crosshairs" style="color:var(--accent);margin-right:8px;"></i>Strategy Registry</span>' +
          '<div class="fleet-page-meta">' +
            '<button class="wd-refresh-btn" id="strat-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button>' +
          '</div>' +
        '</div>' +

        '<div class="wd-panel">' +
          '<div class="wd-panel-header">Upload Strategy<span class="panel-badge">REGISTER</span></div>' +
          '<div class="wd-panel-body">' +
            '<div class="wd-file-upload" id="strat-upload-area">' +
              '<input type="file" id="strat-file-input" accept=".py" style="display:none" />' +
              '<i class="fa-solid fa-file-code"></i>' +
              '<h4>Upload Strategy File</h4>' +
              '<p>.py files extending BaseStrategy</p>' +
              '<div id="strat-upload-status"></div>' +
            '</div>' +
          '</div>' +
        '</div>' +

        '<div id="strat-list-content">' +
          '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading strategies…</p></div>' +
        '</div>' +
      '</div>';

    document.getElementById('main-content').innerHTML = html;

    _attachEvents();
    _fetch();

    _refreshInterval = setInterval(_fetch, 10000);
  }

  function _attachEvents() {
    document.getElementById('strat-refresh').addEventListener('click', _fetch);

    var area = document.getElementById('strat-upload-area');
    var input = document.getElementById('strat-file-input');

    area.addEventListener('click', function () {
      input.click();
    });

    input.addEventListener('change', function () {
      if (!input.files || !input.files[0]) return;

      var file = input.files[0];

      if (!file.name.endsWith('.py')) {
        ToastManager.show('Only .py files accepted.', 'error');
        return;
      }

      _upload(file);
    });
  }

  function _upload(file) {
    var el = document.getElementById('strat-upload-status');

    el.innerHTML =
      '<div class="wd-file-status" style="color:var(--accent);">' +
      '<i class="fa-solid fa-spinner fa-spin"></i> Uploading &amp; validating…</div>';

    ApiClient.uploadStrategy(file).then(function (data) {
      el.innerHTML =
        '<div class="wd-file-status" style="color:var(--success);">' +
        '<i class="fa-solid fa-circle-check"></i> Registered: ' +
        (data.strategy_name || data.strategy_id) +
        '</div>';

      ToastManager.show('Strategy registered: ' + (data.strategy_name || data.strategy_id), 'success');
      _fetch();
    }).catch(function (err) {
      el.innerHTML =
        '<div class="wd-file-status" style="color:var(--danger);">' +
        '<i class="fa-solid fa-circle-xmark"></i> ' +
        err.message +
        '</div>';

      ToastManager.show('Upload failed: ' + err.message, 'error');
    });
  }

  function _fetch() {
    var el = document.getElementById('strat-list-content');
    if (!el) return;

    ApiClient.getStrategies().then(function (data) {
      var list = data.strategies || [];

      if (list.length === 0) {
        el.innerHTML =
          '<div class="empty-state" style="min-height:200px;">' +
            '<i class="fa-solid fa-crosshairs"></i>' +
            '<h3>No Strategies Registered</h3>' +
            '<p>Upload a .py strategy file extending BaseStrategy to get started.</p>' +
          '</div>';
        return;
      }

      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">' +
        '<thead><tr><th>Strategy ID</th><th>Name</th><th>Version</th><th>Params</th><th>Status</th><th>Uploaded</th></tr></thead><tbody>';

      list.forEach(function (s) {
        var statusClass = s.validation_status === 'validated' ? 'online' : 'error';
        var statusLabel = s.validation_status === 'validated'
          ? 'Validated'
          : (s.validation_status || 'Unknown');

        var uploaded = s.uploaded_at
          ? s.uploaded_at.replace('T', ' ').substring(0, 19)
          : '—';

        html += '<tr>' +
          '<td class="mono">' + s.strategy_id + '</td>' +
          '<td>' + (s.strategy_name || s.strategy_id) + '</td>' +
          '<td class="mono">' + (s.version || '—') + '</td>' +
          '<td class="mono">' + (s.parameter_count || 0) + '</td>' +
          '<td><span class="state-pill ' + statusClass + '">' + statusLabel.toUpperCase() + '</span></td>' +
          '<td class="mono">' + uploaded + '</td>' +
          '</tr>';
      });

      html += '</tbody></table></div>';

      list.forEach(function (s) {
        if (s.description || s.error) {
          html += '<div style="margin-top:8px;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;font-size:11.5px;">';
          html += '<strong class="mono" style="color:var(--accent);">' + s.strategy_id + '</strong>';

          if (s.description) {
            html += '<span style="color:var(--text-secondary);margin-left:8px;">' + s.description + '</span>';
          }

          if (s.error) {
            html += '<span style="color:var(--danger);margin-left:8px;">Error: ' + s.error + '</span>';
          }

          html += '</div>';
        }
      });

      el.innerHTML = html;
    }).catch(function (err) {
      el.innerHTML =
        '<div class="error-state" style="min-height:200px;">' +
          '<i class="fa-solid fa-triangle-exclamation"></i>' +
          '<h3>Failed to Load Strategies</h3>' +
          '<p>' + err.message + '</p>' +
          '<button class="retry-btn" onclick="StrategiesRenderer._retry()">Retry</button>' +
        '</div>';
    });
  }

  function destroy() {
    if (_refreshInterval) {
      clearInterval(_refreshInterval);
      _refreshInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _retry: _fetch
  };
})();


var App = (function () {
  'use strict';

  var currentPage = 'dashboard';
  var _selectedWorker = null;

  var pageIcons = {
    dashboard: 'fa-grip',
    fleet: 'fa-server',
    portfolio: 'fa-chart-line',
    strategies: 'fa-crosshairs',
    logs: 'fa-scroll',
    settings: 'fa-gear'
  };

  var pageDescriptions = {
    portfolio: 'Portfolio analytics will be available when trade execution is implemented.',
    logs: 'Centralized log aggregation, real-time streaming, and advanced search across all fleet nodes.',
    settings: 'System configuration, user preferences, notification settings, and connection management.'
  };

  function init() {
    ThemeManager.init();
    setupNavigation();
    startClock();
    navigateTo('dashboard');
  }

  function setupNavigation() {
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        navigateTo(item.getAttribute('data-page'));
      });
    });
  }

  function navigateTo(page) {
    if (currentPage === 'dashboard') DashboardRenderer.destroy();
    if (currentPage === 'fleet') FleetRenderer.destroy();
    if (currentPage === 'workerDetail') WorkerDetailRenderer.destroy();
    if (currentPage === 'strategies') StrategiesRenderer.destroy();

    currentPage = page;

    var navPage = page === 'workerDetail' ? 'fleet' : page;

    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.classList.toggle('active', item.getAttribute('data-page') === navPage);
    });

    var titleMap = {
      workerDetail: 'Worker Detail'
    };

    var title = titleMap[page] || (page.charAt(0).toUpperCase() + page.slice(1));
    document.getElementById('topbar-title').textContent = title;

    if (page === 'dashboard') {
      DashboardRenderer.render();
    } else if (page === 'fleet') {
      FleetRenderer.render();
    } else if (page === 'workerDetail' && _selectedWorker) {
      WorkerDetailRenderer.render(_selectedWorker);
    } else if (page === 'strategies') {
      StrategiesRenderer.render();
    } else {
      renderPlaceholder(page);
    }
  }

  function navigateToWorkerDetail(workerData) {
    _selectedWorker = workerData;
    navigateTo('workerDetail');
  }

  function renderPlaceholder(page) {
    var icon = pageIcons[page] || 'fa-circle-question';
    var title = page.charAt(0).toUpperCase() + page.slice(1);
    var desc = pageDescriptions[page] || 'This section is under development.';

    document.getElementById('main-content').innerHTML =
      '<div class="placeholder-page"><i class="fa-solid ' + icon + '"></i>' +
      '<h2>' + title + '</h2><p>' + desc + '</p></div>';
  }

  function startClock() {
    function update() {
      var now = new Date();

      document.getElementById('topbar-clock').textContent =
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0') + ':' +
        String(now.getSeconds()).padStart(2, '0');
    }

    update();
    setInterval(update, 1000);
  }

  document.addEventListener('DOMContentLoaded', init);

  return {
    navigateTo: navigateTo,
    navigateToWorkerDetail: navigateToWorkerDetail
  };
})();
```

---

## FILE: `ui/js/workerDetailRenderer.js`

- Relative path: `ui/js/workerDetailRenderer.js`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/js/workerDetailRenderer.js`
- Size bytes: `34626`
- SHA256: `9a07c02293f72c89b704129fb04c7d3e974ef562a8ccb0fcc71881f9432cfa2f`
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
    var pnl = _formatPnl(w.floating_pnl);
    var pnlStyle = '';
    if (w.floating_pnl !== null && w.floating_pnl !== undefined) {
      pnlStyle = w.floating_pnl >= 0 ? 'color:var(--success)' : 'color:var(--danger)';
    }

    var cards = [
      { label: 'Connection', value: '<div class="status-indicator"><span class="wd-status-dot-sm ' + _stateColor(state) + '"></span>' + _stateLabel(state) + '</div>' },
      { label: 'Active Strategy', value: strats },
      { label: 'Open Positions', value: String(w.open_positions_count || 0) },
      { label: 'Floating PnL', value: '<span style="' + pnlStyle + '">' + pnl + '</span>' },
      { label: 'Last Heartbeat', value: _formatAge(w.heartbeat_age_seconds) },
      { label: 'Agent Version', value: _nullVal(w.agent_version) },
    ];

    var html = '';
    cards.forEach(function (c) {
      html += '<div class="wd-status-card"><span class="status-label">' + c.label + '</span><span class="status-value">' + c.value + '</span></div>';
    });
    return html;
  }

  /* ── Checklist ───────────────────────────────────────────── */

  function _renderChecklist() {
    var w = _currentWorker;
    var onlineStates = ['online', 'running', 'idle'];
    var isOnline = onlineStates.indexOf(w.state) !== -1;
    var hasSid = !!_selectedStrategyId;
    var hasSym = !!_runtimeConfig.symbol;
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
    var symbols = DeploymentConfig.symbolOptions;
    var tlUnits = DeploymentConfig.tickLookbackUnits;

    var symOpts = symbols.map(function (s) {
      return '<option value="' + s + '"' + (rc.symbol === s ? ' selected' : '') + '>' + s + '</option>';
    }).join('');

    var tlUnitOpts = tlUnits.map(function (u) {
      var label = u.charAt(0).toUpperCase() + u.slice(1);
      return '<option value="' + u + '"' + (rc.tick_lookback_unit === u ? ' selected' : '') + '>' + label + '</option>';
    }).join('');

    return '<div class="wd-form-grid">' +
      '<div class="wd-form-group"><label class="wd-form-label">Symbol</label>' +
        '<select class="wd-form-select rc-input" data-key="symbol">' + symOpts + '</select></div>' +
      '<div class="wd-form-group"><label class="wd-form-label">Lot Size</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="lot_size" value="' + rc.lot_size + '" step="0.01" min="0.01" /></div>' +
      '<div class="wd-form-group"><label class="wd-form-label">Tick Lookback</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="tick_lookback_value" value="' + rc.tick_lookback_value + '" step="1" min="1" /></div>' +
      '<div class="wd-form-group"><label class="wd-form-label">Lookback Unit</label>' +
        '<select class="wd-form-select rc-input" data-key="tick_lookback_unit">' + tlUnitOpts + '</select></div>' +
      '<div class="wd-form-group"><label class="wd-form-label">Bar Size Points</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="bar_size_points" value="' + rc.bar_size_points + '" step="1" min="1" /></div>' +
      '<div class="wd-form-group"><label class="wd-form-label">Max Bars in Memory</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="max_bars_memory" value="' + rc.max_bars_memory + '" step="10" min="10" /></div>' +
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
      input.addEventListener('change', function () {
        var key = input.getAttribute('data-key');
        _runtimeConfig[key] = input.type === 'number' ? parseFloat(input.value) : input.value;
        _updateChecklist();
        _addActivity('Config: ' + key + ' updated');
      });
    });
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
    if (!_runtimeConfig.symbol) {
      ToastManager.show('Select a symbol.', 'warning');
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

## FILE: `worker/worker_agent.py`

- Relative path: `worker/worker_agent.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/worker_agent.py`
- Size bytes: `8265`
- SHA256: `1af8f6b2cbd643070b3a705f2724f8ad36123c34b9f5afa45b001e94cee52e4a`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Worker Agent
Heartbeat + Command polling + Strategy Runner management.

Usage:
    1. Edit config.yaml
    2. python -m worker.worker_agent   (from project root)
       OR: cd worker && python worker_agent.py
       worker/worker_agent.py
"""
import os
import sys
import time
import socket
import threading
import yaml
import requests

# Ensure worker package is importable when run directly
_worker_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_worker_dir)
if _worker_dir not in sys.path:
    sys.path.insert(0, _worker_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from worker.old.strategy_runner import StrategyRunner


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

        # Active runner (one deployment at a time for now)
        self._runner: StrategyRunner | None = None
        self._runner_lock = threading.Lock()

    # ── Heartbeat ───────────────────────────────────────────────

    def _build_heartbeat_payload(self) -> dict:
        runner = self._runner
        active_strategies = []
        runner_state = "idle"
        floating_pnl = None
        open_positions = 0
        errors = []

        if runner:
            runner_state = runner._runner_state
            if runner._strategy:
                active_strategies = [runner.strategy_id]
            if runner._last_error:
                errors = [runner._last_error]

        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "host": self.host,
            "state": "online" if runner_state in ("idle", "running", "warming_up") else runner_state,
            "agent_version": self.agent_version,
            "mt5_state": None,
            "account_id": None,
            "broker": None,
            "active_strategies": active_strategies,
            "open_positions_count": open_positions,
            "floating_pnl": floating_pnl,
            "errors": errors,
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

    # ── Command Polling ─────────────────────────────────────────

    def poll_commands(self):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/commands/poll"
        try:
            resp = requests.get(endpoint, timeout=10)
            data = resp.json()
            commands = data.get("commands", [])
            for cmd in commands:
                self._handle_command(cmd)
        except requests.exceptions.ConnectionError:
            pass  # Mother unreachable — silent, heartbeat already warns
        except Exception as e:
            print(f"[ERROR] Command poll: {type(e).__name__}: {e}")

    def _handle_command(self, cmd: dict):
        cmd_type = cmd.get("command_type")
        cmd_id = cmd.get("command_id")
        payload = cmd.get("payload", {})

        print(f"[COMMAND] Received: {cmd_type} ({cmd_id})")

        # Acknowledge immediately
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

    # ── Runner Status Callback ──────────────────────────────────

    def _report_runner_status(self, status: dict):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/runner-status"
        try:
            requests.post(endpoint, json=status, timeout=10)
        except Exception as e:
            print(f"[ERROR] Runner status report failed: {e}")

    # ── Deploy / Stop Handlers ──────────────────────────────────

    def _handle_deploy(self, payload: dict):
        with self._runner_lock:
            # Stop existing runner if any
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

    # ── Main Loop ───────────────────────────────────────────────

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

        poll_counter = 0
        try:
            while True:
                self.send_heartbeat()

                # Poll commands every heartbeat
                self.poll_commands()

                poll_counter += 1
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
