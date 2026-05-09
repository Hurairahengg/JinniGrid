"""
JINNI Grid - Combined Runtime Services
app/services/mainServices.py
"""

import logging
import math
import threading
import uuid
from datetime import datetime, timedelta, timezone
from app.persistence import save_trade_db
from app.config import Config
from app.persistence import (
    save_worker, get_all_workers_db, get_worker_db,
    save_deployment, update_deployment_state_db,
    get_all_deployments_db, get_deployment_db,
    log_event_db, get_events_db,
)

log = logging.getLogger("jinni.worker")
sys_log = logging.getLogger("jinni.system")


# =============================================================================
# Command Queue
# =============================================================================

_command_queues: dict = {}
_command_lock = threading.Lock()


def enqueue_command(worker_id: str, command_type: str, payload: dict) -> dict:
    cmd_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)
    cmd = {"command_id": cmd_id, "worker_id": worker_id, "command_type": command_type,
           "payload": payload, "state": "pending", "created_at": now.isoformat(), "acked_at": None}
    with _command_lock:
        if worker_id not in _command_queues:
            _command_queues[worker_id] = []
        _command_queues[worker_id].append(cmd)
    log.info(f"Enqueued {command_type} ({cmd_id}) for worker {worker_id}")
    log_event_db("command", "enqueued", f"{command_type} for {worker_id}", worker_id=worker_id, data={"command_id": cmd_id})
    return cmd


def poll_commands(worker_id: str) -> list:
    now = datetime.now(timezone.utc)
    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        pending = [c for c in queue if c["state"] == "pending"]
        # Prune acknowledged commands older than 5 minutes
        _command_queues[worker_id] = [
            c for c in queue
            if c["state"] == "pending" or (
                c.get("acked_at") and
                (now - datetime.fromisoformat(c["acked_at"])).total_seconds() < 300
            )
        ]
    return pending


def ack_command(worker_id: str, command_id: str) -> dict:
    now = datetime.now(timezone.utc)
    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        for cmd in queue:
            if cmd["command_id"] == command_id:
                cmd["state"] = "acknowledged"
                cmd["acked_at"] = now.isoformat()
                return {"ok": True, "command": cmd}
    return {"ok": False, "error": "Command not found."}


# =============================================================================
# Deployment Registry
# =============================================================================

VALID_STATES = {"queued", "sent_to_worker", "acknowledged_by_worker", "loading_strategy",
                "fetching_ticks", "generating_initial_bars", "warming_up", "running", "stopped", "failed"}


def create_deployment(config: dict) -> dict:
    deployment_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)
    record = {
        "deployment_id": deployment_id, "strategy_id": config["strategy_id"],
        "worker_id": config["worker_id"], "symbol": config["symbol"],
        "tick_lookback_value": config.get("tick_lookback_value", 30),
        "tick_lookback_unit": config.get("tick_lookback_unit", "minutes"),
        "bar_size_points": config["bar_size_points"],
        "max_bars_in_memory": config.get("max_bars_in_memory", 500),
        "lot_size": config.get("lot_size", 0.01),
        "strategy_parameters": config.get("strategy_parameters") or {},
        "state": "queued", "created_at": now.isoformat(), "updated_at": now.isoformat(), "last_error": None,
    }
    save_deployment(deployment_id, record)
    log.info(f"Created deployment {deployment_id}")
    log_event_db("deployment", "created", f"Deployment {deployment_id} created",
                 worker_id=config["worker_id"], strategy_id=config["strategy_id"],
                 deployment_id=deployment_id, symbol=config["symbol"])
    return {"ok": True, "deployment_id": deployment_id, "deployment": record}


def get_all_deployments() -> list:
    return get_all_deployments_db()


def get_deployment(deployment_id: str):
    return get_deployment_db(deployment_id)


def update_deployment_state(deployment_id: str, state: str, error: str = None) -> dict:
    if state not in VALID_STATES:
        return {"ok": False, "error": f"Invalid state: {state}"}
    update_deployment_state_db(deployment_id, state, error)
    log_event_db("deployment", "state_change", f"{deployment_id} -> {state}",
                 deployment_id=deployment_id, data={"state": state, "error": error},
                 level="ERROR" if state == "failed" else "INFO")
    rec = get_deployment_db(deployment_id)
    return {"ok": True, "deployment": rec}


def stop_deployment(deployment_id: str) -> dict:
    return update_deployment_state(deployment_id, "stopped")

# =============================================================================
# Portfolio Data (Real — backed by trades table)
# =============================================================================

def get_portfolio_summary() -> dict:
    from app.persistence import get_all_trades_db
    trades = get_all_trades_db(limit=50000)

    # Live worker data (even if no trades yet)
    workers = get_all_workers()
    total_floating = sum((w.get("floating_pnl") or 0) for w in workers)
    total_positions = sum((w.get("open_positions_count") or 0) for w in workers)

    if not trades:
        return {
            "total_balance": 0, "total_equity": 0,
            "floating_pnl": round(total_floating, 2),
            "daily_pnl": 0, "open_positions": total_positions,
            "realized_pnl": 0, "margin_usage": 0,
            "win_rate": 0, "total_trades": 0,
            "profit_factor": 0, "max_drawdown": 0, "avg_trade": 0,
            "avg_winner": 0, "avg_loser": 0, "best_trade": 0,
            "worst_trade": 0, "sharpe_estimate": 0, "avg_bars_held": 0,
        }

    profits = [t.get("profit", 0) for t in trades]
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p <= 0]
    total_pnl = sum(profits)
    bars_list = [t.get("bars_held", 0) for t in trades]

    # Max drawdown from cumulative PnL
    cum, peak, max_dd = 0, 0, 0
    for p in profits:
        cum += p
        if cum > peak:
            peak = cum
        dd = (peak - cum) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    # Sharpe estimate
    mean_pnl = total_pnl / len(profits)
    variance = sum((p - mean_pnl) ** 2 for p in profits) / (len(profits) - 1) if len(profits) > 1 else 0
    std_pnl = math.sqrt(variance) if variance > 0 else 0
    sharpe = round((mean_pnl / std_pnl * math.sqrt(252)), 2) if std_pnl > 0 else 0

    return {
        "total_balance": 0, "total_equity": 0,
        "floating_pnl": round(total_floating, 2),
        "daily_pnl": 0, "open_positions": total_positions,
        "realized_pnl": round(total_pnl, 2), "margin_usage": 0,
        "win_rate": round(len(wins) / len(profits) * 100, 1) if profits else 0,
        "total_trades": len(trades),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else (999.99 if wins else 0),
        "max_drawdown": round(max_dd, 2),
        "avg_trade": round(total_pnl / len(trades), 2),
        "avg_winner": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loser": round(sum(losses) / len(losses), 2) if losses else 0,
        "best_trade": round(max(profits), 2),
        "worst_trade": round(min(profits), 2),
        "sharpe_estimate": sharpe,
        "avg_bars_held": round(sum(bars_list) / len(bars_list), 1) if bars_list else 0,
    }


def get_equity_history() -> list:
    from app.persistence import get_all_trades_db
    trades = get_all_trades_db(limit=50000)
    if not trades:
        return []
    sorted_trades = sorted(trades, key=lambda t: t.get("exit_time") or "")
    daily = {}
    cum = 0
    for t in sorted_trades:
        date = (t.get("exit_time") or "")[:10]
        if not date:
            continue
        cum += t.get("profit", 0)
        daily[date] = round(cum, 2)
    return [{"timestamp": d, "equity": v} for d, v in sorted(daily.items())]


def get_portfolio_trades(strategy_id=None, worker_id=None, symbol=None, limit=200) -> list:
    from app.persistence import get_all_trades_db
    return get_all_trades_db(limit=limit, strategy_id=strategy_id,
                             worker_id=worker_id, symbol=symbol)


def get_portfolio_performance() -> dict:
    from app.persistence import get_all_trades_db
    trades = get_all_trades_db(limit=50000)
    if not trades:
        return {"daily": [], "by_strategy": [], "by_worker": [], "by_symbol": []}

    # Daily
    daily = {}
    for t in trades:
        date = (t.get("exit_time") or "")[:10]
        if not date:
            continue
        if date not in daily:
            daily[date] = {"date": date, "pnl": 0, "trades": 0, "wins": 0}
        daily[date]["pnl"] += t.get("profit", 0)
        daily[date]["trades"] += 1
        if t.get("profit", 0) > 0:
            daily[date]["wins"] += 1
    daily_list = sorted(daily.values(), key=lambda x: x["date"])
    cum = 0
    for d in daily_list:
        cum += d["pnl"]
        d["pnl"] = round(d["pnl"], 2)
        d["cumulative"] = round(cum, 2)

    # Breakdown helper
    def _breakdown(key):
        bk = {}
        for t in trades:
            k = t.get(key, "")
            if not k:
                continue
            if k not in bk:
                bk[k] = {key: k, "trades": 0, "pnl": 0, "wins": 0,
                         "losses": 0, "total_bars": 0}
            bk[k]["trades"] += 1
            bk[k]["pnl"] += t.get("profit", 0)
            bk[k]["total_bars"] += t.get("bars_held", 0)
            if t.get("profit", 0) > 0:
                bk[k]["wins"] += 1
            else:
                bk[k]["losses"] += 1
        for v in bk.values():
            v["pnl"] = round(v["pnl"], 2)
            v["win_rate"] = round(v["wins"] / v["trades"] * 100, 1) if v["trades"] > 0 else 0
            v["avg_bars"] = round(v["total_bars"] / v["trades"], 1) if v["trades"] > 0 else 0
            w_sum = sum(t.get("profit", 0) for t in trades
                        if t.get(key) == v[key] and t.get("profit", 0) > 0)
            l_sum = sum(abs(t.get("profit", 0)) for t in trades
                        if t.get(key) == v[key] and t.get("profit", 0) <= 0)
            v["profit_factor"] = round(w_sum / l_sum, 2) if l_sum > 0 else (999.99 if w_sum > 0 else 0)
        return list(bk.values())

    return {
        "daily": daily_list,
        "by_strategy": _breakdown("strategy_id"),
        "by_worker": _breakdown("worker_id"),
        "by_symbol": _breakdown("symbol"),
    }


# =============================================================================
# Events / Logs
# =============================================================================

def get_events_list(category=None, level=None, worker_id=None,
                    deployment_id=None, search=None, limit=200) -> list:
    events = get_events_db(limit=max(limit, 500), category=category,
                           worker_id=worker_id, deployment_id=deployment_id)
    if level:
        events = [e for e in events if e.get("level") == level]
    if search:
        sl = search.lower()
        events = [e for e in events if sl in (e.get("message", "") or "").lower()
                  or sl in (e.get("event_type", "") or "").lower()
                  or sl in (e.get("category", "") or "").lower()]
    return events[:limit]


# =============================================================================
# Worker Registry
# =============================================================================

_workers_cache: dict = {}
_worker_lock = threading.Lock()


def _load_workers_from_db():
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
        _workers_cache[worker_id] = {**payload, "worker_id": worker_id,
                                      "last_heartbeat_at": now.isoformat(), "_last_heartbeat_dt": now}
    save_worker(worker_id, {**payload, "last_heartbeat_at": now.isoformat()})
    if is_new:
        log.info(f"Worker '{worker_id}' registered")
        log_event_db("worker", "registered", f"Worker {worker_id} first heartbeat", worker_id=worker_id)
    return {"ok": True, "worker_id": worker_id, "registered": is_new, "server_time": now.isoformat()}


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
                "worker_id": rec.get("worker_id", wid), "worker_name": rec.get("worker_name"),
                "host": rec.get("host"), "state": effective, "reported_state": reported,
                "last_heartbeat_at": rec.get("last_heartbeat_at"), "heartbeat_age_seconds": age,
                "agent_version": rec.get("agent_version"), "mt5_state": rec.get("mt5_state"),
                "account_id": rec.get("account_id"), "broker": rec.get("broker"),
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
    counts = {"online_workers": 0, "stale_workers": 0, "offline_workers": 0,
              "error_workers": 0, "warning_workers": 0}
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