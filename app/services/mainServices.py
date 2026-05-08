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