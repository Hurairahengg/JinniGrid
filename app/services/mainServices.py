"""
JINNI Grid - Combined Runtime Services
app/services/mainServices.py
"""

import random
import threading
import uuid
from datetime import datetime, timedelta, timezone

from app.config import Config


# =============================================================================
# Command Queue
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

    print(f"[COMMAND] Enqueued {command_type} ({cmd_id}) for worker {worker_id}")
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

    with _deployment_lock:
        _deployments[deployment_id] = record

    print(
        f"[DEPLOYMENT] Created {deployment_id} | "
        f"strategy={config['strategy_id']} -> worker={config['worker_id']}"
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
        f"[DEPLOYMENT] {deployment_id} -> {state}"
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
                f"state={payload.get('state', 'unknown')} "
                f"mt5={payload.get('mt5_state', '-')} "
                f"ticks={payload.get('total_ticks', 0)} "
                f"bars={payload.get('total_bars', 0)} "
                f"signals={payload.get('signal_count', 0)}"
            )

        _workers[worker_id] = {
            "worker_id": worker_id,
            "worker_name": payload.get("worker_name"),
            "host": payload.get("host"),
            "reported_state": payload.get("state", "online"),
            "last_heartbeat_at": now.isoformat(),
            "_last_heartbeat_dt": now,
            "agent_version": payload.get("agent_version"),
            # MT5 info
            "mt5_state": payload.get("mt5_state"),
            "account_id": payload.get("account_id"),
            "broker": payload.get("broker"),
            # Strategies + positions
            "active_strategies": payload.get("active_strategies") or [],
            "open_positions_count": payload.get("open_positions_count", 0) or 0,
            "floating_pnl": payload.get("floating_pnl"),
            "errors": payload.get("errors") or [],
            # Pipeline diagnostics
            "total_ticks": payload.get("total_ticks", 0) or 0,
            "total_bars": payload.get("total_bars", 0) or 0,
            "on_bar_calls": payload.get("on_bar_calls", 0) or 0,
            "signal_count": payload.get("signal_count", 0) or 0,
            "last_bar_time": payload.get("last_bar_time"),
            "current_price": payload.get("current_price"),
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
                # MT5 info
                "mt5_state": rec["mt5_state"],
                "account_id": rec["account_id"],
                "broker": rec["broker"],
                # Strategies + positions
                "active_strategies": rec["active_strategies"],
                "open_positions_count": rec["open_positions_count"],
                "floating_pnl": rec["floating_pnl"],
                "errors": rec["errors"],
                # Pipeline diagnostics
                "total_ticks": rec["total_ticks"],
                "total_bars": rec["total_bars"],
                "on_bar_calls": rec["on_bar_calls"],
                "signal_count": rec["signal_count"],
                "last_bar_time": rec["last_bar_time"],
                "current_price": rec["current_price"],
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