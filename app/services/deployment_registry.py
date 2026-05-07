"""
JINNI Grid - Deployment Registry
In-memory deployment store. Create, list, update state.
No database — all lost on restart.
"""
import threading
import uuid
from datetime import datetime, timezone

_deployments: dict = {}
_lock = threading.Lock()

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
    config must include: strategy_id, worker_id, symbol, bar_size_points,
    max_bars_in_memory, tick_lookback_value, tick_lookback_unit.
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

    with _lock:
        _deployments[deployment_id] = record

    print(f"[DEPLOYMENT] Created {deployment_id} | strategy={config['strategy_id']} → worker={config['worker_id']}")
    return {"ok": True, "deployment_id": deployment_id, "deployment": record}


def get_all_deployments() -> list:
    with _lock:
        return list(_deployments.values())


def get_deployment(deployment_id: str) -> dict | None:
    with _lock:
        return _deployments.get(deployment_id)


def update_deployment_state(deployment_id: str, state: str, error: str = None) -> dict:
    """Update deployment state. Returns updated record or error."""
    if state not in VALID_STATES:
        return {"ok": False, "error": f"Invalid state: {state}"}

    now = datetime.now(timezone.utc)
    with _lock:
        rec = _deployments.get(deployment_id)
        if not rec:
            return {"ok": False, "error": "Deployment not found."}
        rec["state"] = state
        rec["updated_at"] = now.isoformat()
        if error is not None:
            rec["last_error"] = error
        elif state == "running":
            rec["last_error"] = None

    print(f"[DEPLOYMENT] {deployment_id} → {state}" + (f" (error: {error})" if error else ""))
    return {"ok": True, "deployment": rec}


def stop_deployment(deployment_id: str) -> dict:
    return update_deployment_state(deployment_id, "stopped")


def get_deployments_for_worker(worker_id: str) -> list:
    with _lock:
        return [d for d in _deployments.values() if d["worker_id"] == worker_id]