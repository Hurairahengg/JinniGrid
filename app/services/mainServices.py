"""
JINNI GRID — Combined Runtime Services
app/services/mainServices.py

Portfolio computations use ISO date strings from the DB (not raw Unix timestamps).
Equity snapshots throttled to max once per 10 seconds.
All monetary values rounded to 2 decimals.
"""

import logging
import math
import threading
import time
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
    delete_all_trades_db, delete_trades_by_strategy_db,
    delete_trades_by_worker_db,
    delete_strategy_full_db, remove_worker_db, remove_stale_workers_db,
    clear_events_db, get_system_stats_db, full_system_reset_db,
)

log = logging.getLogger("jinni.services")


def _r2(v):
    if v is None:
        return 0.0
    try:
        return round(float(v), 2)
    except (ValueError, TypeError):
        return 0.0


# ── Timestamp helpers (for portfolio date grouping) ─────────

def _trade_exit_date(t: dict) -> str:
    """Extract YYYY-MM-DD from a trade record, handling all formats."""
    # 1. ISO exit_time string (set by persistence layer)
    et = t.get("exit_time")
    if et and isinstance(et, str) and len(et) >= 10 and et[4:5] == "-":
        return et[:10]
    # 2. Unix timestamp in exit_time_unix
    etu = t.get("exit_time_unix")
    if etu:
        try:
            v = int(etu)
            if v > 946684800:
                return datetime.fromtimestamp(
                    v, tz=timezone.utc
                ).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OSError):
            pass
    # 3. created_at from DB
    ca = t.get("created_at")
    if ca and isinstance(ca, str) and len(ca) >= 10:
        return ca[:10]
    return ""


def _trade_exit_month(t: dict) -> str:
    d = _trade_exit_date(t)
    return d[:7] if len(d) >= 7 else ""


# =============================================================================
# Command Queue
# =============================================================================

_command_queues: dict = {}
_command_lock = threading.Lock()


def enqueue_command(worker_id: str, command_type: str, payload: dict) -> dict:
    cmd_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)
    cmd = {"command_id": cmd_id, "worker_id": worker_id,
           "command_type": command_type, "payload": payload,
           "state": "pending", "created_at": now.isoformat(), "acked_at": None}
    with _command_lock:
        _command_queues.setdefault(worker_id, []).append(cmd)
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
                (now - datetime.fromisoformat(c["acked_at"])
                 ).total_seconds() < 300
            )
        ]
    return pending


def ack_command(worker_id: str, command_id: str) -> dict:
    now = datetime.now(timezone.utc)
    with _command_lock:
        for cmd in _command_queues.get(worker_id, []):
            if cmd["command_id"] == command_id:
                cmd["state"] = "acknowledged"
                cmd["acked_at"] = now.isoformat()
                return {"ok": True, "command": cmd}
    return {"ok": False, "error": "Command not found."}


# =============================================================================
# Deployment Registry
# =============================================================================

VALID_STATES = {
    "queued", "sent_to_worker", "acknowledged_by_worker", "loading_strategy",
    "fetching_ticks", "generating_initial_bars", "warming_up", "running",
    "stopped", "failed",
}


def create_deployment(config: dict) -> dict:
    deployment_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)
    settings = get_all_settings()
    record = {
        "deployment_id": deployment_id,
        "strategy_id": config["strategy_id"],
        "worker_id": config["worker_id"],
        "symbol": config.get("symbol") or settings.get(
            "default_symbol", "XAUUSD"),
        "tick_lookback_value": config.get("tick_lookback_value", 30),
        "tick_lookback_unit": config.get("tick_lookback_unit", "minutes"),
        "bar_size_points": config.get("bar_size_points") or float(
            settings.get("default_bar_size", "100")),
        "max_bars_in_memory": config.get("max_bars_in_memory", 500),
        "lot_size": config.get("lot_size") or float(
            settings.get("default_lot_size", "0.01")),
        "strategy_parameters": config.get("strategy_parameters") or {},
        "state": "queued",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "last_error": None,
    }
    save_deployment(deployment_id, record)
    log_event_db("deployment", "created",
                 f"Deployment {deployment_id} created",
                 worker_id=config["worker_id"],
                 strategy_id=config["strategy_id"],
                 deployment_id=deployment_id, symbol=record["symbol"])
    return {"ok": True, "deployment_id": deployment_id,
            "deployment": record}


def get_all_deployments() -> list:
    return get_all_deployments_db()


def get_deployment(deployment_id: str):
    return get_deployment_db(deployment_id)


def update_deployment_state(deployment_id: str, state: str,
                             error: str = None) -> dict:
    if state not in VALID_STATES:
        return {"ok": False, "error": f"Invalid state: {state}"}
    update_deployment_state_db(deployment_id, state, error)
    log_event_db("deployment", "state_change",
                 f"{deployment_id} -> {state}",
                 deployment_id=deployment_id,
                 data={"state": state, "error": error},
                 level="ERROR" if state == "failed" else "INFO")
    return {"ok": True, "deployment": get_deployment_db(deployment_id)}


def stop_deployment(deployment_id: str) -> dict:
    return update_deployment_state(deployment_id, "stopped")


# =============================================================================
# Worker Registry
# =============================================================================

_workers_cache: dict = {}
_worker_lock = threading.Lock()
_last_snapshot_time: float = 0.0  # throttle equity snapshots
_SNAPSHOT_INTERVAL = 10.0         # seconds between snapshots


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


def process_heartbeat(payload: dict) -> dict:
    global _last_snapshot_time
    worker_id = payload["worker_id"].strip()
    now = datetime.now(timezone.utc)
    is_new = False
    with _worker_lock:
        if worker_id not in _workers_cache:
            is_new = True
        _workers_cache[worker_id] = {
            **payload, "worker_id": worker_id,
            "last_heartbeat_at": now.isoformat(),
            "_last_heartbeat_dt": now,
        }
    save_worker(worker_id, {**payload, "last_heartbeat_at": now.isoformat()})
    if is_new:
        log_event_db("worker", "registered",
                     f"Worker {worker_id} first heartbeat",
                     worker_id=worker_id)

    # Throttled equity snapshot (max once per 10s, not every heartbeat)
    mono = time.monotonic()
    if mono - _last_snapshot_time >= _SNAPSHOT_INTERVAL:
        _last_snapshot_time = mono
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
            reported = rec.get("reported_state",
                               rec.get("state", "online"))
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
                "current_bars_in_memory": rec.get("current_bars_in_memory", 0),
                "on_bar_calls": rec.get("on_bar_calls", 0),
                "signal_count": rec.get("signal_count", 0),
                "last_bar_time": rec.get("last_bar_time"),
                "current_price": rec.get("current_price"),
            })
    return result


def get_fleet_summary() -> dict:
    workers = get_all_workers()
    counts = {"online_workers": 0, "stale_workers": 0,
              "offline_workers": 0, "error_workers": 0,
              "warning_workers": 0}
    for w in workers:
        s = w["state"]
        if s in ("online", "running", "idle"):
            counts["online_workers"] += 1
        elif s == "stale":
            counts["stale_workers"] += 1
        elif s == "offline":
            counts["offline_workers"] += 1
        elif s == "error":
            counts["error_workers"] += 1
    counts["total_workers"] = len(workers)
    return counts


# =============================================================================
# Equity Snapshot Engine (throttled)
# =============================================================================

def _compute_equity_snapshot():
    total_balance = 0.0
    total_equity = 0.0
    total_floating = 0.0
    open_pos = 0
    has_account = False

    with _worker_lock:
        for w in _workers_cache.values():
            ab = w.get("account_balance")
            ae = w.get("account_equity")
            if ab is not None and float(ab or 0) > 0:
                total_balance += float(ab)
                has_account = True
            if ae is not None and float(ae or 0) > 0:
                total_equity += float(ae)
                has_account = True
            total_floating += float(w.get("floating_pnl") or 0)
            open_pos += int(w.get("open_positions_count") or 0)

    # Sum realized PnL from DB (use a fast count, not loading all rows)
    trades = get_all_trades_db(limit=50000)
    realized = sum(_r2(t.get("profit")) for t in trades)

    if not has_account:
        total_balance = realized
        total_equity = realized + total_floating

    # Only save if we have meaningful data (avoid 0-equity pollution)
    if _r2(total_equity) != 0 or _r2(total_balance) != 0 or open_pos > 0:
        try:
            save_equity_snapshot_db(
                balance=_r2(total_balance),
                equity=_r2(total_equity),
                floating_pnl=_r2(total_floating),
                open_positions=open_pos,
                cumulative_pnl=_r2(realized),
            )
        except Exception as e:
            print(f"[PORTFOLIO] Snapshot save failed: {e}")

# =============================================================================
# Portfolio Engine (correct date handling + extended stats)
# =============================================================================

def _compute_trade_stats(trades: list) -> dict:
    """Comprehensive stats from trade records."""
    empty = {
        "total_trades": 0, "wins": 0, "losses": 0,
        "gross_profit": 0, "gross_loss": 0, "net_pnl": 0,
        "win_rate": 0, "profit_factor": 0, "expectancy": 0,
        "avg_trade": 0, "avg_winner": 0, "avg_loser": 0,
        "best_trade": 0, "worst_trade": 0,
        "max_drawdown_pct": 0, "max_drawdown_usd": 0,
        "recovery_factor": 0, "sharpe_estimate": 0,
        "sortino_estimate": 0, "avg_bars_held": 0,
        "max_consec_wins": 0, "max_consec_losses": 0,
        "best_day": None, "worst_day": None, "trades_per_day": 0,
    }
    if not trades:
        return empty

    profits = [_r2(t.get("profit")) for t in trades]
    n = len(profits)
    win_p = [p for p in profits if p > 0]
    loss_p = [p for p in profits if p <= 0]
    bars = [int(t.get("bars_held", 0) or 0) for t in trades]

    gp = _r2(sum(win_p))
    gl = _r2(sum(loss_p))
    net = _r2(gp + gl)

    # Max drawdown (peak-to-trough, capped at 100%)
    cum, peak, dd_usd, dd_pct = 0.0, 0.0, 0.0, 0.0
    for p in profits:
        cum += p
        if cum > peak:
            peak = cum
        d = peak - cum  # always >= 0
        dd_usd = max(dd_usd, d)
        # Only compute % when peak is meaningfully positive
        if peak > 0.01:
            dp = min((d / peak) * 100, 100.0)  # cap at 100%
            dd_pct = max(dd_pct, dp)

    # Sharpe
    mean = net / n
    var = sum((p - mean) ** 2 for p in profits) / (n - 1) if n > 1 else 0
    std = math.sqrt(var) if var > 0 else 0
    sharpe = _r2(mean / std * math.sqrt(252)) if std > 0 else 0

    # Sortino
    down = [p for p in profits if p < 0]
    if down and len(down) > 1:
        dvar = sum(p ** 2 for p in down) / len(down)
        dstd = math.sqrt(dvar) if dvar > 0 else 0
        sortino = _r2(mean / dstd * math.sqrt(252)) if dstd > 0 else 0
    else:
        sortino = 0

    # Consecutive
    mcw, mcl, cw, cl = 0, 0, 0, 0
    for p in profits:
        if p > 0:
            cw += 1; cl = 0
        else:
            cl += 1; cw = 0
        mcw = max(mcw, cw)
        mcl = max(mcl, cl)

    # ★ FIX: Daily grouping uses _trade_exit_date (handles Unix timestamps)
    daily = {}
    for t in trades:
        d = _trade_exit_date(t)
        if not d:
            continue
        daily.setdefault(d, 0.0)
        daily[d] += float(t.get("profit", 0) or 0)

    best_day = worst_day = None
    if daily:
        bd = max(daily.items(), key=lambda x: x[1])
        wd = min(daily.items(), key=lambda x: x[1])
        best_day = {"date": bd[0], "pnl": _r2(bd[1])}
        worst_day = {"date": wd[0], "pnl": _r2(wd[1])}

    num_days = max(len(daily), 1)
    agl = abs(gl)
    pf = _r2(gp / agl) if agl > 0 else (999.99 if gp > 0 else 0)
    rf = _r2(net / dd_usd) if dd_usd > 0 else 0

    return {
        "total_trades": n,
        "wins": len(win_p), "losses": len(loss_p),
        "gross_profit": gp, "gross_loss": gl, "net_pnl": net,
        "win_rate": _r2(len(win_p) / n * 100) if n else 0,
        "profit_factor": pf,
        "expectancy": _r2(net / n) if n else 0,
        "avg_trade": _r2(net / n) if n else 0,
        "avg_winner": _r2(gp / len(win_p)) if win_p else 0,
        "avg_loser": _r2(gl / len(loss_p)) if loss_p else 0,
        "best_trade": _r2(max(profits)),
        "worst_trade": _r2(min(profits)),
        "max_drawdown_pct": _r2(dd_pct),
        "max_drawdown_usd": _r2(dd_usd),
        "recovery_factor": rf,
        "sharpe_estimate": sharpe,
        "sortino_estimate": sortino,
        "avg_bars_held": _r2(sum(bars) / n) if n else 0,
        "max_consec_wins": mcw,
        "max_consec_losses": mcl,
        "best_day": best_day, "worst_day": worst_day,
        "trades_per_day": _r2(n / num_days),
    }


def get_portfolio_summary(strategy_id=None, worker_id=None,
                           symbol=None) -> dict:
    trades = get_all_trades_db(limit=50000, strategy_id=strategy_id,
                                worker_id=worker_id, symbol=symbol)
    workers = get_all_workers()
    tb = te = tf = 0.0
    tp = 0
    has_acc = False

    for w in workers:
        if worker_id and w.get("worker_id") != worker_id:
            continue
        ab = w.get("account_balance", 0) or 0
        ae = w.get("account_equity", 0) or 0
        if ab > 0:
            tb += ab; has_acc = True
        if ae > 0:
            te += ae; has_acc = True
        tf += (w.get("floating_pnl") or 0)
        tp += (w.get("open_positions_count") or 0)

    stats = _compute_trade_stats(trades)

    if not has_acc:
        tb = stats["net_pnl"]
        te = stats["net_pnl"] + tf

    # Compute drawdown from equity snapshots if available (more accurate)
    snapshots = get_equity_snapshots_db(limit=5000)
    snap_dd_usd = 0.0
    snap_dd_pct = 0.0
    if snapshots:
        eq_vals = [s.get("equity", 0) for s in snapshots if (s.get("equity") or 0) > 0]
        if eq_vals:
            pk = 0.0
            for v in eq_vals:
                if v > pk:
                    pk = v
                d = pk - v
                if d > snap_dd_usd:
                    snap_dd_usd = d
                if pk > 0.01:
                    dp = min((d / pk) * 100, 100.0)
                    if dp > snap_dd_pct:
                        snap_dd_pct = dp

    # Use snapshot-based DD if available and meaningful, else trade-based
    final_dd_usd = snap_dd_usd if snap_dd_usd > 0 else stats["max_drawdown_usd"]
    final_dd_pct = snap_dd_pct if snap_dd_pct > 0 else stats["max_drawdown_pct"]

    # Current drawdown
    current_dd_pct = 0.0
    if snapshots:
        eq_vals = [s.get("equity", 0) for s in snapshots if (s.get("equity") or 0) > 0]
        if eq_vals:
            peak_eq = max(eq_vals)
            current_eq = eq_vals[-1]
            if peak_eq > 0.01:
                current_dd_pct = min(((peak_eq - current_eq) / peak_eq) * 100, 100.0)

    return {
        "total_balance": _r2(tb),
        "total_equity": _r2(te),
        "floating_pnl": _r2(tf),
        "open_positions": tp,
        "has_account_data": has_acc,
        "active_workers": len([w for w in workers
                               if w.get("state") in
                               ("online", "running")]),
        "max_drawdown_usd": _r2(final_dd_usd),
        "max_drawdown_pct": _r2(final_dd_pct),
        "current_drawdown_pct": _r2(current_dd_pct),
        "peak_equity": _r2(max(eq_vals) if snapshots and eq_vals else te),
        # All other stats from _compute_trade_stats (except DD which we override)
        "total_trades": stats["total_trades"],
        "wins": stats["wins"],
        "losses": stats["losses"],
        "gross_profit": stats["gross_profit"],
        "gross_loss": stats["gross_loss"],
        "net_pnl": stats["net_pnl"],
        "win_rate": stats["win_rate"],
        "profit_factor": stats["profit_factor"],
        "expectancy": stats["expectancy"],
        "avg_trade": stats["avg_trade"],
        "avg_winner": stats["avg_winner"],
        "avg_loser": stats["avg_loser"],
        "best_trade": stats["best_trade"],
        "worst_trade": stats["worst_trade"],
        "recovery_factor": _r2(stats["net_pnl"] / final_dd_usd) if final_dd_usd > 0 else 0,
        "sharpe_estimate": stats["sharpe_estimate"],
        "sortino_estimate": stats["sortino_estimate"],
        "avg_bars_held": stats["avg_bars_held"],
        "max_consec_wins": stats["max_consec_wins"],
        "max_consec_losses": stats["max_consec_losses"],
        "best_day": stats["best_day"],
        "worst_day": stats["worst_day"],
        "trades_per_day": stats["trades_per_day"],
    }


def get_equity_history() -> list:
    trades = get_all_trades_db(limit=50000)
    trade_curve = []
    if trades:
        sorted_t = sorted(trades, key=lambda t: t.get("id", 0))
        cum = 0.0
        for t in sorted_t:
            cum += _r2(t.get("profit"))
            ts = t.get("exit_time") or t.get("created_at") or ""
            label = str(ts)[-8:] if len(str(ts)) >= 8 else str(ts)
            trade_curve.append({
                "timestamp": str(ts),
                "equity": _r2(cum),
                "balance": _r2(cum),
                "floating_pnl": 0.0,
                "realized_pnl": _r2(cum),
                "label": label,
                "source": "trade",
            })

    # Periodic snapshots
    snapshots = get_equity_snapshots_db(limit=2000)
    snap_curve = []
    for s in snapshots:
        eq = _r2(s.get("equity", 0))
        bal = _r2(s.get("balance", 0))
        # Skip zero-equity snapshots (worker not initialized yet)
        if eq <= 0 and bal <= 0:
            continue
        ts = s.get("timestamp", "")
        label = ts[-8:] if len(ts) >= 8 else ts
        snap_curve.append({
            "timestamp": ts,
            "equity": eq,
            "balance": bal,
            "floating_pnl": _r2(s.get("floating_pnl", 0)),
            "realized_pnl": _r2(s.get("cumulative_pnl", 0)),
            "label": label,
            "source": "snapshot",
        })

    if snap_curve:
        # Downsample to one per minute
        result, last_min = [], ""
        for s in snap_curve:
            m = s["timestamp"][:16]
            if m != last_min:
                result.append(s)
                last_min = m
        return result if result else snap_curve

    if trade_curve:
        return trade_curve

    # No data at all — return empty (UI handles gracefully)
    return []

def get_portfolio_trades(strategy_id=None, worker_id=None,
                          symbol=None, limit=500) -> list:
    return get_all_trades_db(limit=limit, strategy_id=strategy_id,
                             worker_id=worker_id, symbol=symbol)


def get_portfolio_performance(strategy_id=None, worker_id=None,
                               symbol=None) -> dict:
    trades = get_all_trades_db(limit=50000, strategy_id=strategy_id,
                                worker_id=worker_id, symbol=symbol)
    if not trades:
        return {"daily": [], "monthly": [],
                "by_strategy": [], "by_worker": [], "by_symbol": []}

    # ★ FIX: Daily uses _trade_exit_date (converts Unix → YYYY-MM-DD)
    daily = {}
    for t in trades:
        d = _trade_exit_date(t)
        if not d:
            continue
        if d not in daily:
            daily[d] = {"date": d, "pnl": 0, "trades": 0, "wins": 0}
        daily[d]["pnl"] += float(t.get("profit", 0) or 0)
        daily[d]["trades"] += 1
        if float(t.get("profit", 0) or 0) > 0:
            daily[d]["wins"] += 1

    daily_list = sorted(daily.values(), key=lambda x: x["date"])
    cum = 0.0
    for d in daily_list:
        cum += d["pnl"]
        d["pnl"] = _r2(d["pnl"])
        d["cumulative"] = _r2(cum)

    # ★ FIX: Monthly uses _trade_exit_month
    monthly = {}
    for t in trades:
        m = _trade_exit_month(t)
        if not m:
            continue
        if m not in monthly:
            monthly[m] = {"month": m, "pnl": 0, "trades": 0, "wins": 0}
        monthly[m]["pnl"] += float(t.get("profit", 0) or 0)
        monthly[m]["trades"] += 1
        if float(t.get("profit", 0) or 0) > 0:
            monthly[m]["wins"] += 1

    monthly_list = sorted(monthly.values(), key=lambda x: x["month"])
    for m in monthly_list:
        m["pnl"] = _r2(m["pnl"])
        m["win_rate"] = _r2(
            m["wins"] / m["trades"] * 100
        ) if m["trades"] else 0

    # Breakdowns
    def _bk(key):
        bk = {}
        for t in trades:
            k = t.get(key, "")
            if not k:
                continue
            if k not in bk:
                bk[k] = {key: k, "trades": 0, "pnl": 0,
                         "wins": 0, "losses": 0, "total_bars": 0}
            bk[k]["trades"] += 1
            p = float(t.get("profit", 0) or 0)
            bk[k]["pnl"] += p
            bk[k]["total_bars"] += int(t.get("bars_held", 0) or 0)
            if p > 0:
                bk[k]["wins"] += 1
            else:
                bk[k]["losses"] += 1
        for v in bk.values():
            v["pnl"] = _r2(v["pnl"])
            v["win_rate"] = _r2(
                v["wins"] / v["trades"] * 100
            ) if v["trades"] else 0
            v["avg_bars"] = _r2(
                v["total_bars"] / v["trades"]
            ) if v["trades"] else 0
            ws = sum(float(t.get("profit", 0) or 0)
                     for t in trades
                     if t.get(key) == v[key]
                     and float(t.get("profit", 0) or 0) > 0)
            ls = sum(abs(float(t.get("profit", 0) or 0))
                     for t in trades
                     if t.get(key) == v[key]
                     and float(t.get("profit", 0) or 0) <= 0)
            v["profit_factor"] = _r2(
                ws / ls) if ls > 0 else (999.99 if ws > 0 else 0)
        return list(bk.values())

    return {
        "daily": daily_list,
        "monthly": monthly_list,
        "by_strategy": _bk("strategy_id"),
        "by_worker": _bk("worker_id"),
        "by_symbol": _bk("symbol"),
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
                           worker_id=worker_id,
                           deployment_id=deployment_id)
    if level:
        events = [e for e in events if e.get("level") == level]
    elif min_ord > 0:
        events = [e for e in events
                  if level_order.get(e.get("level", "INFO"), 1) >= min_ord]
    if search:
        sl = search.lower()
        events = [e for e in events
                  if sl in (e.get("message", "") or "").lower()
                  or sl in (e.get("event_type", "") or "").lower()]
    return events[:limit]


# =============================================================================
# Settings
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
    workers = get_all_workers()
    deployments = get_all_deployments_db()
    stopped = 0
    for d in deployments:
        if d.get("state") in ("running", "queued", "warming_up",
                                "loading_strategy", "fetching_ticks",
                                "generating_initial_bars"):
            update_deployment_state_db(d["deployment_id"], "stopped")
            stopped += 1
    cmds = 0
    for w in workers:
        if w.get("state") in ("online", "running", "idle", "stale"):
            enqueue_command(w["worker_id"], "emergency_close", {
                "action": "close_all_positions",
                "reason": "emergency_stop_all",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            enqueue_command(w["worker_id"], "stop_all_strategies", {
                "reason": "emergency_stop_all",
            })
            cmds += 2
    log_event_db("system", "emergency_stop",
                 f"Emergency stop: {stopped} deps stopped, "
                 f"{cmds} commands sent",
                 level="WARNING")
    return {"ok": True, "deployments_stopped": stopped,
            "commands_sent": cmds,
            "workers_notified": len(workers)}


# =============================================================================
# Admin
# =============================================================================

def admin_get_stats() -> dict:
    stats = get_system_stats_db()
    stats["fleet_summary"] = get_fleet_summary()
    return stats


def admin_delete_strategy(strategy_id: str) -> dict:
    result = delete_strategy_full_db(strategy_id)
    log_event_db("strategy", "deleted",
                 f"Strategy {strategy_id} deleted",
                 strategy_id=strategy_id, level="WARNING")
    return result


def admin_reset_portfolio() -> dict:
    tc = delete_all_trades_db()
    clear_equity_snapshots_db()
    log_event_db("system", "portfolio_reset",
                 f"{tc} trades deleted", level="WARNING")
    return {"trades_deleted": tc, "equity_cleared": True}


def admin_clear_trades() -> dict:
    c = delete_all_trades_db()
    log_event_db("system", "trades_cleared",
                 f"{c} trades deleted", level="WARNING")
    return {"trades_deleted": c}


def admin_remove_worker(worker_id: str) -> dict:
    with _worker_lock:
        _workers_cache.pop(worker_id, None)
    with _command_lock:
        _command_queues.pop(worker_id, None)
    result = remove_worker_db(worker_id)
    log_event_db("worker", "removed",
                 f"Worker {worker_id} removed",
                 worker_id=worker_id, level="WARNING")
    return result


def admin_remove_stale_workers(threshold: int = 300) -> dict:
    count = remove_stale_workers_db(threshold)
    now = datetime.now(timezone.utc)
    with _worker_lock:
        stale = []
        for wid, w in _workers_cache.items():
            hb = w.get("last_heartbeat_at")
            if hb:
                try:
                    last = datetime.fromisoformat(hb)
                    if (now - last).total_seconds() > threshold:
                        stale.append(wid)
                except (TypeError, ValueError):
                    stale.append(wid)
        for wid in stale:
            _workers_cache.pop(wid, None)
    return {"removed": count}


def admin_clear_events() -> dict:
    c = clear_events_db()
    return {"events_cleared": c}


def admin_full_reset() -> dict:
    counts = full_system_reset_db()
    with _worker_lock:
        _workers_cache.clear()
    with _command_lock:
        _command_queues.clear()
    log_event_db("system", "full_reset",
                 "Full system reset", level="WARNING")
    return counts