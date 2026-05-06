"""
JINNI Grid - Worker Registry
Runtime-only in-memory worker state store.
All data is lost on server restart. No database persistence yet.
"""
import threading
from datetime import datetime, timezone
from app.config import Config

# In-memory state (runtime only)
_workers: dict = {}
_lock = threading.Lock()


def process_heartbeat(payload: dict) -> dict:
    worker_id = payload["worker_id"].strip()
    now = datetime.now(timezone.utc)
    is_new = False

    with _lock:
        if worker_id not in _workers:
            is_new = True
            print(f"[HEARTBEAT] Worker '{worker_id}' registered | state={payload.get('state', 'unknown')}")
        else:
            print(f"[HEARTBEAT] Worker '{worker_id}' updated | state={payload.get('state', 'unknown')}")

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

    return {"ok": True, "worker_id": worker_id, "registered": is_new, "server_time": now.isoformat()}


def get_all_workers() -> list:
    fleet_config = Config.get_fleet_config()
    stale_threshold = fleet_config.get("stale_threshold_seconds", 30)
    offline_threshold = fleet_config.get("offline_threshold_seconds", 90)
    now = datetime.now(timezone.utc)
    result = []

    with _lock:
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
    counts = {"online_workers": 0, "stale_workers": 0, "offline_workers": 0, "error_workers": 0, "warning_workers": 0}
    online_states = {"online", "running", "idle"}
    for w in workers:
        s = w["state"]
        if s in online_states: counts["online_workers"] += 1
        elif s == "stale": counts["stale_workers"] += 1
        elif s == "offline": counts["offline_workers"] += 1
        elif s == "error": counts["error_workers"] += 1
        elif s == "warning": counts["warning_workers"] += 1
    counts["total_workers"] = len(workers)
    return counts
