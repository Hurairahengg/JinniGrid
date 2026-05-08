"""
JINNI Grid - Combined Runtime Services
app/services/mainServices.py
"""

import logging
import math
import random
import threading
import uuid
from datetime import datetime, timedelta, timezone

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
# Mock Trade Data
# =============================================================================

_MOCK_TRADES = None


def _generate_mock_trades():
    rng = random.Random(42)
    trades = []
    symbols = ['EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'BTCUSD']
    strats = ['hma_cross_v1', 'smc_reversal', 'range_breakout']
    workers = ['vm-worker-01', 'vm-worker-02', 'vm-worker-03']
    reasons = ['tp_hit', 'sl_hit', 'strategy_close', 'MA_TP_EXIT', 'MA_SL_EXIT', 'reverse']
    base_prices = {'EURUSD': 1.0850, 'GBPUSD': 1.2650, 'XAUUSD': 2340.0, 'USDJPY': 155.50, 'BTCUSD': 68500.0}
    base_time = datetime(2026, 2, 5, 8, 0, 0, tzinfo=timezone.utc)

    for i in range(300):
        sym = rng.choice(symbols)
        direction = rng.choice(['long', 'short'])
        lot = rng.choice([0.01, 0.02, 0.05, 0.10, 0.20])
        is_win = rng.random() < 0.65
        if is_win:
            profit = round(rng.uniform(30, 600) * lot * 10, 2)
        else:
            profit = round(-rng.uniform(20, 450) * lot * 10, 2)
        bp = base_prices[sym]
        entry_p = bp + (rng.random() - 0.5) * bp * 0.008
        dp = 2 if sym in ('XAUUSD', 'BTCUSD', 'USDJPY') else 5
        entry_p = round(entry_p, dp)
        delta = profit / (lot * 100000) if sym in ('EURUSD', 'GBPUSD') else profit / (lot * 100)
        exit_p = round(entry_p + delta if direction == 'long' else entry_p - delta, dp)
        bars = max(5, int(rng.gauss(85, 40)))
        entry_t = base_time + timedelta(hours=i * 2.4 + rng.random() * 2)
        exit_t = entry_t + timedelta(minutes=bars * rng.uniform(1.5, 3))
        trades.append({
            "id": i + 1, "direction": direction, "symbol": sym,
            "strategy_id": rng.choice(strats), "worker_id": rng.choice(workers),
            "entry_price": entry_p, "exit_price": exit_p,
            "entry_time": entry_t.isoformat(), "exit_time": exit_t.isoformat(),
            "exit_reason": rng.choice(reasons), "lot_size": lot,
            "profit": profit, "bars_held": bars, "status": "closed",
        })
    return trades


def _get_mock_trades():
    global _MOCK_TRADES
    if _MOCK_TRADES is None:
        _MOCK_TRADES = _generate_mock_trades()
    return _MOCK_TRADES


# =============================================================================
# Portfolio Data
# =============================================================================

def get_portfolio_summary() -> dict:
    trades = _get_mock_trades()
    profits = [t['profit'] for t in trades]
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p <= 0]
    total_pnl = sum(profits)
    equity_hist = get_equity_history()
    peak = 0.0
    max_dd = 0.0
    for p in equity_hist:
        if p['equity'] > peak:
            peak = p['equity']
        dd = (peak - p['equity']) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    mean_pnl = total_pnl / len(profits) if profits else 0
    variance = sum((p - mean_pnl) ** 2 for p in profits) / (len(profits) - 1) if len(profits) > 1 else 0
    std_pnl = math.sqrt(variance) if variance > 0 else 0
    sharpe = round((mean_pnl / std_pnl * math.sqrt(252)), 2) if std_pnl > 0 else 0
    bars_list = [t['bars_held'] for t in trades]
    return {
        "total_balance": 248750.00, "total_equity": 251320.45, "floating_pnl": 2570.45,
        "daily_pnl": 1847.30, "open_positions": 12,
        "realized_pnl": round(total_pnl, 2), "margin_usage": 34.7,
        "win_rate": round(len(wins) / len(profits) * 100, 1) if profits else 0,
        "total_trades": len(trades),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else 0,
        "max_drawdown": round(max_dd, 2), "avg_trade": round(total_pnl / len(trades), 2) if trades else 0,
        "avg_winner": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loser": round(sum(losses) / len(losses), 2) if losses else 0,
        "best_trade": round(max(profits), 2) if profits else 0,
        "worst_trade": round(min(profits), 2) if profits else 0,
        "sharpe_estimate": sharpe,
        "avg_bars_held": round(sum(bars_list) / len(bars_list), 1) if bars_list else 0,
    }


def get_equity_history() -> list:
    rng = random.Random(42)
    points = []
    start = datetime(2025, 11, 1, tzinfo=timezone.utc)
    val = 200000.0
    for i in range(180):
        d = start + timedelta(days=i)
        val += (rng.random() - 0.42) * 2000
        if val < 180000:
            val = 180000.0
        points.append({"timestamp": d.strftime("%Y-%m-%d"), "equity": round(val, 2)})
    return points


def get_portfolio_trades(strategy_id=None, worker_id=None, symbol=None, limit=200) -> list:
    trades = list(_get_mock_trades())
    if strategy_id:
        trades = [t for t in trades if t['strategy_id'] == strategy_id]
    if worker_id:
        trades = [t for t in trades if t['worker_id'] == worker_id]
    if symbol:
        trades = [t for t in trades if t['symbol'] == symbol]
    return trades[:limit]


def get_portfolio_performance() -> dict:
    trades = _get_mock_trades()
    daily = {}
    for t in trades:
        date = t['exit_time'][:10]
        if date not in daily:
            daily[date] = {'date': date, 'pnl': 0, 'trades': 0, 'wins': 0}
        daily[date]['pnl'] += t['profit']
        daily[date]['trades'] += 1
        if t['profit'] > 0:
            daily[date]['wins'] += 1
    daily_list = sorted(daily.values(), key=lambda x: x['date'])
    cum = 0
    for d in daily_list:
        cum += d['pnl']
        d['pnl'] = round(d['pnl'], 2)
        d['cumulative'] = round(cum, 2)

    def _breakdown(key):
        bk = {}
        for t in trades:
            k = t[key]
            if k not in bk:
                bk[k] = {key: k, 'trades': 0, 'pnl': 0, 'wins': 0, 'losses': 0, 'total_bars': 0}
            bk[k]['trades'] += 1
            bk[k]['pnl'] += t['profit']
            bk[k]['total_bars'] += t['bars_held']
            if t['profit'] > 0:
                bk[k]['wins'] += 1
            else:
                bk[k]['losses'] += 1
        for v in bk.values():
            v['pnl'] = round(v['pnl'], 2)
            v['win_rate'] = round(v['wins'] / v['trades'] * 100, 1) if v['trades'] > 0 else 0
            v['avg_bars'] = round(v['total_bars'] / v['trades'], 1) if v['trades'] > 0 else 0
            w_profits = [t['profit'] for t in trades if t[key] == v[key] and t['profit'] > 0]
            l_profits = [abs(t['profit']) for t in trades if t[key] == v[key] and t['profit'] <= 0]
            gl = sum(l_profits)
            v['profit_factor'] = round(sum(w_profits) / gl, 2) if gl > 0 else 0
        return list(bk.values())

    return {
        "daily": daily_list,
        "by_strategy": _breakdown('strategy_id'),
        "by_worker": _breakdown('worker_id'),
        "by_symbol": _breakdown('symbol'),
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