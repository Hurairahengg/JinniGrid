"""
JINNI Grid - Combined Runtime Services
app/services/mainServices.py
"""

import logging
import math
import threading
import uuid
from datetime import datetime, timedelta, timezone

from app.config import Config
from app.persistence import (
    init_db,
    save_worker, get_all_workers_db, get_worker_db,
    save_deployment, get_all_deployments_db, get_deployment_db,
    update_deployment_state_db,
    log_event_db, get_events_db,
    save_trade_db, get_all_trades_db,
    save_equity_snapshot_db, get_equity_snapshots_db, clear_equity_snapshots_db,
    get_setting, get_all_settings, save_setting, save_settings_bulk,
    delete_all_trades_db, delete_trades_by_strategy_db, delete_trades_by_worker_db,
    delete_strategy_full_db, remove_worker_db, remove_stale_workers_db,
    clear_events_db, get_system_stats_db, full_system_reset_db,
)

log = logging.getLogger("jinni.worker")
sys_log = logging.getLogger("jinni.system")


# ── Rounding helper ─────────────────────────────────────────
def _r2(v):
    """Round to 2 decimals, coerce None to 0."""
    if v is None:
        return 0.0
    return round(float(v), 2)


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
    log_event_db("command", "enqueued", f"{command_type} for {worker_id}",
                 worker_id=worker_id, data={"command_id": cmd_id})
    return cmd


def poll_commands(worker_id: str) -> list:
    now = datetime.now(timezone.utc)
    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        pending = [c for c in queue if c["state"] == "pending"]
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
                "fetching_ticks", "generating_initial_bars", "warming_up", "running",
                "stopped", "failed"}


def create_deployment(config: dict) -> dict:
    deployment_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)

    # Apply defaults from settings if not specified
    settings = get_all_settings()
    record = {
        "deployment_id": deployment_id, "strategy_id": config["strategy_id"],
        "worker_id": config["worker_id"], "symbol": config.get("symbol") or settings.get("default_symbol", "XAUUSD"),
        "tick_lookback_value": config.get("tick_lookback_value", 30),
        "tick_lookback_unit": config.get("tick_lookback_unit", "minutes"),
        "bar_size_points": config.get("bar_size_points") or float(settings.get("default_bar_size", "100")),
        "max_bars_in_memory": config.get("max_bars_in_memory", 500),
        "lot_size": config.get("lot_size") or float(settings.get("default_lot_size", "0.01")),
        "strategy_parameters": config.get("strategy_parameters") or {},
        "state": "queued", "created_at": now.isoformat(), "updated_at": now.isoformat(),
        "last_error": None,
    }
    save_deployment(deployment_id, record)
    log.info(f"Created deployment {deployment_id}")
    log_event_db("deployment", "created", f"Deployment {deployment_id} created",
                 worker_id=config["worker_id"], strategy_id=config["strategy_id"],
                 deployment_id=deployment_id, symbol=record["symbol"])
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
# Worker Registry
# =============================================================================

_workers_cache: dict = {}
_worker_lock = threading.Lock()
_equity_history: list = []


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
        _workers_cache[worker_id] = {
            **payload, "worker_id": worker_id,
            "last_heartbeat_at": now.isoformat(), "_last_heartbeat_dt": now,
        }
    save_worker(worker_id, {**payload, "last_heartbeat_at": now.isoformat()})
    if is_new:
        log.info(f"Worker '{worker_id}' registered")
        log_event_db("worker", "registered", f"Worker {worker_id} first heartbeat",
                     worker_id=worker_id)
    _compute_equity_snapshot()
    return {"ok": True, "worker_id": worker_id, "registered": is_new,
            "server_time": now.isoformat()}


def get_all_workers() -> list:
    fleet_config = Config.get_fleet_config()
    timeout_setting = get_setting("worker_timeout_seconds")
    if timeout_setting:
        offline_threshold = int(timeout_setting)
        stale_threshold = max(10, offline_threshold // 3)
    else:
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
                "state": effective, "reported_state": reported,
                "last_heartbeat_at": rec.get("last_heartbeat_at"),
                "heartbeat_age_seconds": age,
                "agent_version": rec.get("agent_version"),
                "mt5_state": rec.get("mt5_state"),
                "account_id": rec.get("account_id"),
                "broker": rec.get("broker"),
                "active_strategies": rec.get("active_strategies") or [],
                "open_positions_count": rec.get("open_positions_count", 0),
                "floating_pnl": _r2(rec.get("floating_pnl")),
                "account_balance": _r2(rec.get("account_balance")),
                "account_equity": _r2(rec.get("account_equity")),
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


# =============================================================================
# Equity Snapshot Engine
# =============================================================================

def _compute_equity_snapshot():
    total_balance = 0.0
    total_equity = 0.0
    total_floating = 0.0
    open_pos = 0
    has_account_data = False

    with _worker_lock:
        for w in _workers_cache.values():
            acc_bal = w.get("account_balance")
            acc_eq = w.get("account_equity")
            if acc_bal is not None and float(acc_bal) > 0:
                total_balance += float(acc_bal)
                has_account_data = True
            if acc_eq is not None and float(acc_eq) > 0:
                total_equity += float(acc_eq)
                has_account_data = True
            total_floating += float(w.get("floating_pnl") or 0)
            open_pos += int(w.get("open_positions_count") or 0)

    trades = get_all_trades_db(limit=100000)
    realized_pnl = sum(float(t.get("profit", 0) or 0) for t in trades)

    if not has_account_data:
        total_balance = realized_pnl
        total_equity = realized_pnl + total_floating

    try:
        save_equity_snapshot_db(
            balance=_r2(total_balance),
            equity=_r2(total_equity),
            floating_pnl=_r2(total_floating),
            open_positions=open_pos,
            cumulative_pnl=_r2(realized_pnl),
        )
    except Exception as e:
        print(f"[PORTFOLIO] Equity snapshot save failed: {e}")

    now = datetime.now(timezone.utc).isoformat()
    _equity_history.append({
        "timestamp": now,
        "equity": _r2(total_equity),
        "balance": _r2(total_balance),
        "floating_pnl": _r2(total_floating),
        "open_positions": open_pos,
        "realized_pnl": _r2(realized_pnl),
        "has_account_data": has_account_data,
        "label": now[-8:],
    })
    if len(_equity_history) > 5000:
        _equity_history[:] = _equity_history[-5000:]


# =============================================================================
# Portfolio Engine (with filtering + extended stats)
# =============================================================================

def _compute_trade_stats(trades: list) -> dict:
    """Compute comprehensive trade statistics from a list of trade records."""
    if not trades:
        return {
            "total_trades": 0, "wins": 0, "losses": 0,
            "gross_profit": 0, "gross_loss": 0, "net_pnl": 0,
            "win_rate": 0, "profit_factor": 0, "expectancy": 0,
            "avg_trade": 0, "avg_winner": 0, "avg_loser": 0,
            "best_trade": 0, "worst_trade": 0,
            "max_drawdown_pct": 0, "max_drawdown_usd": 0,
            "recovery_factor": 0, "sharpe_estimate": 0,
            "sortino_estimate": 0, "avg_bars_held": 0,
            "max_consec_wins": 0, "max_consec_losses": 0,
            "avg_hold_bars": 0, "best_day": None, "worst_day": None,
            "trades_per_day": 0,
        }

    profits = [_r2(t.get("profit", 0) or 0) for t in trades]
    win_profits = [p for p in profits if p > 0]
    loss_profits = [p for p in profits if p <= 0]
    bars_list = [int(t.get("bars_held", 0) or 0) for t in trades]
    n = len(profits)

    gross_profit = _r2(sum(win_profits))
    gross_loss = _r2(sum(loss_profits))
    net_pnl = _r2(gross_profit + gross_loss)

    # Max drawdown
    cum, peak, max_dd_usd, max_dd_pct = 0.0, 0.0, 0.0, 0.0
    for p in profits:
        cum += p
        if cum > peak:
            peak = cum
        dd_usd = peak - cum
        dd_pct = (dd_usd / peak * 100) if peak > 0 else 0
        if dd_usd > max_dd_usd:
            max_dd_usd = dd_usd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    # Sharpe
    mean_pnl = net_pnl / n
    variance = sum((p - mean_pnl) ** 2 for p in profits) / (n - 1) if n > 1 else 0
    std_pnl = math.sqrt(variance) if variance > 0 else 0
    sharpe = _r2((mean_pnl / std_pnl * math.sqrt(252))) if std_pnl > 0 else 0

    # Sortino (only downside deviation)
    downside = [p for p in profits if p < 0]
    if downside and len(downside) > 1:
        down_var = sum(p ** 2 for p in downside) / len(downside)
        down_std = math.sqrt(down_var) if down_var > 0 else 0
        sortino = _r2((mean_pnl / down_std * math.sqrt(252))) if down_std > 0 else 0
    else:
        sortino = 0

    # Consecutive wins/losses
    max_cw, max_cl, cw, cl = 0, 0, 0, 0
    for p in profits:
        if p > 0:
            cw += 1
            cl = 0
        else:
            cl += 1
            cw = 0
        max_cw = max(max_cw, cw)
        max_cl = max(max_cl, cl)

    # Daily breakdown for best/worst day + trades per day
    daily = {}
    for t in trades:
        date = (t.get("exit_time") or t.get("created_at") or "")[:10]
        if not date or len(date) < 10:
            continue
        daily.setdefault(date, 0.0)
        daily[date] += float(t.get("profit", 0) or 0)

    best_day_val = max(daily.values()) if daily else 0
    worst_day_val = min(daily.values()) if daily else 0
    best_day = None
    worst_day = None
    for d, v in daily.items():
        if v == best_day_val and best_day is None:
            best_day = {"date": d, "pnl": _r2(v)}
        if v == worst_day_val and worst_day is None:
            worst_day = {"date": d, "pnl": _r2(v)}

    num_days = len(daily) if daily else 1
    pf_denom = abs(gross_loss)
    profit_factor = _r2(gross_profit / pf_denom) if pf_denom > 0 else (999.99 if gross_profit > 0 else 0)
    recovery = _r2(net_pnl / max_dd_usd) if max_dd_usd > 0 else 0

    return {
        "total_trades": n,
        "wins": len(win_profits),
        "losses": len(loss_profits),
        "gross_profit": _r2(gross_profit),
        "gross_loss": _r2(gross_loss),
        "net_pnl": _r2(net_pnl),
        "win_rate": _r2(len(win_profits) / n * 100) if n > 0 else 0,
        "profit_factor": profit_factor,
        "expectancy": _r2(net_pnl / n) if n > 0 else 0,
        "avg_trade": _r2(net_pnl / n) if n > 0 else 0,
        "avg_winner": _r2(gross_profit / len(win_profits)) if win_profits else 0,
        "avg_loser": _r2(gross_loss / len(loss_profits)) if loss_profits else 0,
        "best_trade": _r2(max(profits)) if profits else 0,
        "worst_trade": _r2(min(profits)) if profits else 0,
        "max_drawdown_pct": _r2(max_dd_pct),
        "max_drawdown_usd": _r2(max_dd_usd),
        "recovery_factor": recovery,
        "sharpe_estimate": sharpe,
        "sortino_estimate": sortino,
        "avg_bars_held": _r2(sum(bars_list) / len(bars_list)) if bars_list else 0,
        "max_consec_wins": max_cw,
        "max_consec_losses": max_cl,
        "avg_hold_bars": _r2(sum(bars_list) / n) if n > 0 else 0,
        "best_day": best_day,
        "worst_day": worst_day,
        "trades_per_day": _r2(n / num_days),
    }


def get_portfolio_summary(strategy_id=None, worker_id=None, symbol=None) -> dict:
    """Get portfolio summary, optionally filtered."""
    trades = get_all_trades_db(limit=100000, strategy_id=strategy_id,
                                worker_id=worker_id, symbol=symbol)

    workers = get_all_workers()
    total_balance = 0.0
    total_equity = 0.0
    total_floating = 0.0
    total_positions = 0
    has_account_data = False

    for w in workers:
        # If filtering by worker, only include matching workers
        if worker_id and w.get("worker_id") != worker_id:
            continue
        acc_bal = w.get("account_balance", 0) or 0
        acc_eq = w.get("account_equity", 0) or 0
        if acc_bal > 0:
            total_balance += acc_bal
            has_account_data = True
        if acc_eq > 0:
            total_equity += acc_eq
            has_account_data = True
        total_floating += (w.get("floating_pnl") or 0)
        total_positions += (w.get("open_positions_count") or 0)

    stats = _compute_trade_stats(trades)

    if not has_account_data:
        total_balance = stats["net_pnl"]
        total_equity = stats["net_pnl"] + total_floating

    active_workers = len([w for w in workers
                          if w.get("state") in ("online", "running")])

    return {
        "total_balance": _r2(total_balance),
        "total_equity": _r2(total_equity),
        "floating_pnl": _r2(total_floating),
        "open_positions": total_positions,
        "has_account_data": has_account_data,
        "active_workers": active_workers,
        # All stats from _compute_trade_stats
        **stats,
    }


def get_equity_history() -> list:
    trades = get_all_trades_db(limit=100000)
    trade_curve = []
    if trades:
        sorted_trades = sorted(trades, key=lambda t: t.get("created_at", ""))
        cumulative_pnl = 0.0
        for t in sorted_trades:
            profit = _r2(t.get("profit", 0) or 0)
            cumulative_pnl += profit
            ts = t.get("exit_time") or t.get("created_at", "")
            ts_str = str(ts)
            label = ts_str[-8:] if len(ts_str) >= 8 else ts_str
            trade_curve.append({
                "timestamp": ts_str,
                "equity": _r2(cumulative_pnl),
                "balance": _r2(cumulative_pnl),
                "floating_pnl": 0.0,
                "realized_pnl": _r2(cumulative_pnl),
                "label": label,
                "source": "trade",
            })

    snapshots = get_equity_snapshots_db(limit=2000)
    snap_curve = []
    for s in snapshots:
        ts = s.get("timestamp", "")
        label = ts[-8:] if len(ts) >= 8 else ts
        snap_curve.append({
            "timestamp": ts,
            "equity": _r2(s.get("equity", 0)),
            "balance": _r2(s.get("balance", 0)),
            "floating_pnl": _r2(s.get("floating_pnl", 0)),
            "realized_pnl": _r2(s.get("cumulative_pnl", 0)),
            "label": label,
            "source": "snapshot",
        })

    if snap_curve:
        result = []
        last_minute = ""
        for s in snap_curve:
            minute = s["timestamp"][:16]
            if minute != last_minute:
                result.append(s)
                last_minute = minute
        return result if result else snap_curve

    if trade_curve:
        return trade_curve

    return [{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "equity": 0, "balance": 0, "floating_pnl": 0,
        "realized_pnl": 0, "label": "start", "source": "initial",
    }]


def get_portfolio_trades(strategy_id=None, worker_id=None, symbol=None,
                         limit=200) -> list:
    return get_all_trades_db(limit=limit, strategy_id=strategy_id,
                             worker_id=worker_id, symbol=symbol)


def get_portfolio_performance(strategy_id=None, worker_id=None,
                              symbol=None) -> dict:
    trades = get_all_trades_db(limit=100000, strategy_id=strategy_id,
                                worker_id=worker_id, symbol=symbol)
    if not trades:
        return {"daily": [], "monthly": [], "by_strategy": [],
                "by_worker": [], "by_symbol": []}

    # Daily
    daily = {}
    for t in trades:
        date = (t.get("exit_time") or "")[:10]
        if not date or len(date) < 10:
            continue
        if date not in daily:
            daily[date] = {"date": date, "pnl": 0, "trades": 0, "wins": 0}
        daily[date]["pnl"] += float(t.get("profit", 0) or 0)
        daily[date]["trades"] += 1
        if float(t.get("profit", 0) or 0) > 0:
            daily[date]["wins"] += 1
    daily_list = sorted(daily.values(), key=lambda x: x["date"])
    cum = 0.0
    for d in daily_list:
        cum += d["pnl"]
        d["pnl"] = _r2(d["pnl"])
        d["cumulative"] = _r2(cum)

    # Monthly
    monthly = {}
    for t in trades:
        date = (t.get("exit_time") or "")[:7]  # YYYY-MM
        if not date or len(date) < 7:
            continue
        if date not in monthly:
            monthly[date] = {"month": date, "pnl": 0, "trades": 0, "wins": 0}
        monthly[date]["pnl"] += float(t.get("profit", 0) or 0)
        monthly[date]["trades"] += 1
        if float(t.get("profit", 0) or 0) > 0:
            monthly[date]["wins"] += 1
    monthly_list = sorted(monthly.values(), key=lambda x: x["month"])
    for m in monthly_list:
        m["pnl"] = _r2(m["pnl"])
        m["win_rate"] = _r2(m["wins"] / m["trades"] * 100) if m["trades"] > 0 else 0

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
            bk[k]["pnl"] += float(t.get("profit", 0) or 0)
            bk[k]["total_bars"] += int(t.get("bars_held", 0) or 0)
            if float(t.get("profit", 0) or 0) > 0:
                bk[k]["wins"] += 1
            else:
                bk[k]["losses"] += 1
        for v in bk.values():
            v["pnl"] = _r2(v["pnl"])
            v["win_rate"] = _r2(v["wins"] / v["trades"] * 100) if v["trades"] > 0 else 0
            v["avg_bars"] = _r2(v["total_bars"] / v["trades"]) if v["trades"] > 0 else 0
            w_sum = sum(float(t.get("profit", 0) or 0) for t in trades
                        if t.get(key) == v[key] and float(t.get("profit", 0) or 0) > 0)
            l_sum = sum(abs(float(t.get("profit", 0) or 0)) for t in trades
                        if t.get(key) == v[key] and float(t.get("profit", 0) or 0) <= 0)
            v["profit_factor"] = _r2(w_sum / l_sum) if l_sum > 0 else (999.99 if w_sum > 0 else 0)
        return list(bk.values())

    return {
        "daily": daily_list,
        "monthly": monthly_list,
        "by_strategy": _breakdown("strategy_id"),
        "by_worker": _breakdown("worker_id"),
        "by_symbol": _breakdown("symbol"),
    }


# =============================================================================
# Events / Logs
# =============================================================================

def get_events_list(category=None, level=None, worker_id=None,
                    deployment_id=None, search=None, limit=200) -> list:
    min_level = get_setting("log_verbosity") or "DEBUG"
    level_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    min_ord = level_order.get(min_level, 0)

    events = get_events_db(limit=max(limit, 500), category=category,
                           worker_id=worker_id, deployment_id=deployment_id)
    if level:
        events = [e for e in events if e.get("level") == level]
    elif min_ord > 0:
        events = [e for e in events
                  if level_order.get(e.get("level", "INFO"), 1) >= min_ord]
    if search:
        sl = search.lower()
        events = [e for e in events if sl in (e.get("message", "") or "").lower()
                  or sl in (e.get("event_type", "") or "").lower()
                  or sl in (e.get("category", "") or "").lower()]
    return events[:limit]


# =============================================================================
# Settings Service
# =============================================================================

def get_system_settings() -> dict:
    return get_all_settings()


def save_system_settings(settings: dict) -> dict:
    save_settings_bulk(settings)
    return get_all_settings()


# =============================================================================
# Emergency Stop
# =============================================================================

def emergency_stop_all() -> dict:
    """
    Emergency stop: stop all deployments + send close_all command to every worker.
    Workers must handle 'emergency_close' by closing all MT5 positions immediately.
    """
    workers = get_all_workers()
    deployments = get_all_deployments_db()

    # Stop all active deployments
    stopped_deps = 0
    for d in deployments:
        if d.get("state") in ("running", "queued", "warming_up", "loading_strategy",
                                "fetching_ticks", "generating_initial_bars"):
            update_deployment_state_db(d["deployment_id"], "stopped")
            stopped_deps += 1

    # Send emergency close command to every online worker
    commands_sent = 0
    for w in workers:
        if w.get("state") in ("online", "running", "idle", "stale"):
            enqueue_command(w["worker_id"], "emergency_close", {
                "action": "close_all_positions",
                "reason": "emergency_stop_all",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            enqueue_command(w["worker_id"], "stop_all_strategies", {
                "reason": "emergency_stop_all",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            commands_sent += 2

    log_event_db("system", "emergency_stop",
                 f"Emergency stop: {stopped_deps} deployments stopped, "
                 f"{commands_sent} commands sent to {len(workers)} workers",
                 level="WARNING")

    return {
        "ok": True,
        "deployments_stopped": stopped_deps,
        "commands_sent": commands_sent,
        "workers_notified": len(workers),
    }


# =============================================================================
# Admin Service
# =============================================================================

def admin_get_stats() -> dict:
    stats = get_system_stats_db()
    stats["fleet_summary"] = get_fleet_summary()
    return stats


def admin_delete_strategy(strategy_id: str) -> dict:
    result = delete_strategy_full_db(strategy_id)
    log_event_db("strategy", "deleted",
                 f"Strategy {strategy_id} deleted by admin",
                 strategy_id=strategy_id, level="WARNING")
    return result


def admin_reset_portfolio() -> dict:
    trade_count = delete_all_trades_db()
    clear_equity_snapshots_db()
    _equity_history.clear()
    log_event_db("system", "portfolio_reset",
                 f"Portfolio reset: {trade_count} trades deleted", level="WARNING")
    return {"trades_deleted": trade_count, "equity_cleared": True}


def admin_clear_trades() -> dict:
    count = delete_all_trades_db()
    log_event_db("system", "trades_cleared",
                 f"{count} trades deleted by admin", level="WARNING")
    return {"trades_deleted": count}


def admin_remove_worker(worker_id: str) -> dict:
    with _worker_lock:
        _workers_cache.pop(worker_id, None)
    with _command_lock:
        _command_queues.pop(worker_id, None)
    result = remove_worker_db(worker_id)
    log_event_db("worker", "removed",
                 f"Worker {worker_id} removed by admin",
                 worker_id=worker_id, level="WARNING")
    return result


def admin_remove_stale_workers(threshold: int = 300) -> dict:
    count = remove_stale_workers_db(threshold)
    now = datetime.now(timezone.utc)
    with _worker_lock:
        stale_ids = []
        for wid, w in _workers_cache.items():
            hb = w.get("last_heartbeat_at")
            if hb:
                try:
                    last = datetime.fromisoformat(hb)
                    if (now - last).total_seconds() > threshold:
                        stale_ids.append(wid)
                except (TypeError, ValueError):
                    stale_ids.append(wid)
        for wid in stale_ids:
            _workers_cache.pop(wid, None)
    log_event_db("system", "stale_workers_removed",
                 f"{count} stale workers removed", level="WARNING")
    return {"removed": count}


def admin_clear_events() -> dict:
    count = clear_events_db()
    return {"events_cleared": count}


def admin_full_reset() -> dict:
    """Full factory reset — clears EVERYTHING including strategies."""
    counts = full_system_reset_db()
    _equity_history.clear()
    with _worker_lock:
        _workers_cache.clear()
    with _command_lock:
        _command_queues.clear()
    log_event_db("system", "full_reset", "Full system reset performed",
                 level="WARNING")
    return counts