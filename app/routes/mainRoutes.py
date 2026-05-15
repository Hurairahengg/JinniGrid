"""
JINNI Grid — Combined API Routes
app/routes/mainRoutes.py
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Query
from pydantic import BaseModel

from app.config import Config
from app.persistence import log_event_db, save_trade_db

from app.services.mainServices import (
    process_heartbeat,
    get_all_workers,
    get_fleet_summary,
    get_system_settings,
    save_system_settings,
    admin_get_stats,
    admin_delete_strategy,
    admin_reset_portfolio,
    admin_clear_trades,
    admin_remove_worker,
    admin_remove_stale_workers,
    admin_clear_events,
    admin_full_reset,
    emergency_stop_all,
    get_portfolio_summary,
    get_equity_history,
    get_portfolio_trades,
    get_portfolio_performance,
    get_events_list,
    create_deployment,
    get_all_deployments,
    get_deployment,
    update_deployment_state,
    stop_deployment,
    enqueue_command,
    poll_commands,
    ack_command,
)

from app.services.strategy_registry import (
    upload_strategy,
    get_all_strategies,
    get_strategy,
    get_strategy_file_content,
    validate_strategy,
)


router = APIRouter()


# =============================================================================
# Health
# =============================================================================

@router.get("/api/health", tags=["Health"])
async def health_check():
    app_config = Config.get_app_config()
    return {
        "status": "ok",
        "service": app_config["name"],
        "version": app_config["version"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Worker Heartbeat + Fleet
# =============================================================================

class HeartbeatPayload(BaseModel):
    worker_id: str
    worker_name: Optional[str] = None
    host: Optional[str] = None
    state: Optional[str] = "online"
    agent_version: Optional[str] = None
    mt5_state: Optional[str] = None
    account_id: Optional[str] = None
    broker: Optional[str] = None
    mt5_server: Optional[str] = None
    active_strategies: Optional[List[str]] = None
    open_positions_count: Optional[int] = 0
    floating_pnl: Optional[float] = None
    account_balance: Optional[float] = None
    account_equity: Optional[float] = None
    errors: Optional[List[str]] = None
    total_ticks: Optional[int] = 0
    total_bars: Optional[int] = 0
    current_bars_in_memory: Optional[int] = 0
    on_bar_calls: Optional[int] = 0
    signal_count: Optional[int] = 0
    last_bar_time: Optional[str] = None
    current_price: Optional[float] = None


@router.post("/api/Grid/workers/heartbeat", tags=["Grid"])
@router.post("/api/grid/workers/heartbeat", tags=["Grid"])
async def worker_heartbeat(payload: HeartbeatPayload):
    if not payload.worker_id or not payload.worker_id.strip():
        raise HTTPException(
            status_code=422,
            detail={"ok": False, "error": "worker_id is required"},
        )
    return process_heartbeat(payload.model_dump())


@router.get("/api/Grid/workers", tags=["Grid"])
@router.get("/api/grid/workers", tags=["Grid"])
async def list_workers():
    return {
        "ok": True,
        "workers": get_all_workers(),
        "summary": get_fleet_summary(),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Portfolio (filtered — strategy_id, worker_id, symbol)
# =============================================================================

@router.get("/api/portfolio/summary", tags=["Portfolio"])
async def portfolio_summary(
    strategy_id: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
):
    portfolio = get_portfolio_summary(
        strategy_id=strategy_id, worker_id=worker_id, symbol=symbol
    )
    return {
        "portfolio": portfolio,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/portfolio/equity-history", tags=["Portfolio"])
async def equity_history():
    history = get_equity_history()
    return {
        "equity_history": history,
        "points": len(history),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/portfolio/trades", tags=["Portfolio"])
async def portfolio_trades(
    strategy_id: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(500),
):
    trades = get_portfolio_trades(
        strategy_id=strategy_id, worker_id=worker_id,
        symbol=symbol, limit=limit,
    )
    return {
        "ok": True,
        "trades": trades,
        "count": len(trades),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/portfolio/performance", tags=["Portfolio"])
async def portfolio_performance(
    strategy_id: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
):
    perf = get_portfolio_performance(
        strategy_id=strategy_id, worker_id=worker_id, symbol=symbol
    )
    return {
        "ok": True,
        "performance": perf,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@router.post("/api/worker/error", tags=["Worker Commands"])
async def worker_error_report(payload: dict = Body(...)):
    """Receive error reports from workers. Logs as event visible in UI."""
    severity = payload.get("severity", "ERROR")
    message = payload.get("message", "Unknown error")
    worker_id = payload.get("worker_id")
    strategy_id = payload.get("strategy_id")
    deployment_id = payload.get("deployment_id")
    symbol = payload.get("symbol")

    level = "ERROR"
    if severity == "CRITICAL":
        level = "ERROR"  # highest level in our event system

    log_event_db(
        category="execution",
        event_type="worker_error",
        message=f"[{severity}] {message}",
        worker_id=worker_id,
        strategy_id=strategy_id,
        deployment_id=deployment_id,
        symbol=symbol,
        data=payload,
        level=level,
    )

    import logging
    logging.getLogger("jinni.worker").error(
        f"[WORKER-ERROR] [{severity}] worker={worker_id} "
        f"dep={deployment_id}: {message}"
    )

    return {"ok": True, "received": True}

@router.post("/api/portfolio/trades/report", tags=["Portfolio"])
async def report_trade(payload: dict = Body(...)):
    """Receive trade report from worker VM. Saves immediately to DB."""
    import logging
    _log = logging.getLogger("jinni.trades")

    mt5_ticket = payload.get("mt5_ticket") or payload.get("ticket")
    is_mt5 = payload.get("mt5_source", False)
    net_pnl = payload.get("net_pnl") or payload.get("profit", 0)
    reason = payload.get("exit_reason", "UNKNOWN")

    _log.info(
        f"[TRADE-IN] {'MT5' if is_mt5 else 'EST'} | "
        f"ticket={mt5_ticket} "
        f"{payload.get('direction', '?')} {payload.get('symbol', '?')} "
        f"pnl={net_pnl} reason={reason} "
        f"worker={payload.get('worker_id', '?')} "
        f"dep={payload.get('deployment_id', '?')}"
    )

    ok = save_trade_db(payload)

    if ok:
        log_event_db(
            "execution", "trade_closed",
            f"{'[MT5]' if is_mt5 else '[EST]'} "
            f"{payload.get('direction', '?')} {payload.get('symbol', '?')} "
            f"ticket={mt5_ticket} pnl={net_pnl} reason={reason}",
            worker_id=payload.get("worker_id"),
            strategy_id=payload.get("strategy_id"),
            deployment_id=payload.get("deployment_id"),
            symbol=payload.get("symbol"),
            data={
                "mt5_ticket": mt5_ticket,
                "profit": payload.get("profit"),
                "commission": payload.get("commission"),
                "swap": payload.get("swap"),
                "net_pnl": net_pnl,
                "exit_reason": reason,
                "mt5_source": is_mt5,
            },
            level="INFO",
        )
    else:
        _log.warning(f"[TRADE-IN] SAVE FAILED for ticket={mt5_ticket}")

    return {"ok": ok, "timestamp": datetime.now(timezone.utc).isoformat()}

# =============================================================================
# Events / Logs
# =============================================================================

@router.get("/api/events", tags=["Events"])
async def get_events(
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    deployment_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200),
):
    events = get_events_list(
        category=category, level=level, worker_id=worker_id,
        deployment_id=deployment_id, search=search, limit=limit,
    )
    return {
        "ok": True,
        "events": events,
        "count": len(events),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Strategies
# =============================================================================

@router.post("/api/grid/strategies/upload", tags=["Strategies"])
async def upload_strategy_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files accepted.")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8.")
    result = upload_strategy(file.filename, text)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/api/grid/strategies", tags=["Strategies"])
async def list_strategies():
    strategies = get_all_strategies()
    for s in strategies:
        s['is_valid'] = bool(s.get('class_name'))
        s['validation_status'] = 'validated' if s['is_valid'] else 'invalid'
    return {
        "ok": True,
        "strategies": strategies,
        "count": len(strategies),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/strategies/{strategy_id}", tags=["Strategies"])
async def get_strategy_detail(strategy_id: str):
    import json as _json
    rec = get_strategy(strategy_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Strategy not found.")

    # Parameters are stored as parameters_json in DB
    params = {}
    raw = rec.get("parameters_json") or rec.get("parameters") or "{}"
    if isinstance(raw, str):
        try:
            params = _json.loads(raw)
        except Exception:
            params = {}
    elif isinstance(raw, dict):
        params = raw

    rec["parameters"] = params
    rec["parameter_count"] = len(params)
    rec["strategy_name"] = rec.get("name", rec.get("strategy_id", ""))
    rec["is_valid"] = bool(rec.get("class_name"))
    rec["validation_status"] = "validated" if rec["is_valid"] else "invalid"
    return {"ok": True, "strategy": rec}


@router.get("/api/grid/strategies/{strategy_id}/file", tags=["Strategies"])
async def get_strategy_file(strategy_id: str):
    content = get_strategy_file_content(strategy_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Strategy file not found.")
    return {"ok": True, "strategy_id": strategy_id, "file_content": content}


@router.post("/api/grid/strategies/{strategy_id}/validate", tags=["Strategies"])
async def validate_strategy_endpoint(strategy_id: str):
    result = validate_strategy(strategy_id)
    if not result["ok"]:
        return {
            "ok": False,
            "strategy_id": strategy_id,
            "valid": False,
            "error": result.get("error", "Unknown validation error"),
        }
    return result


# =============================================================================
# Deployments
# =============================================================================

class DeploymentCreate(BaseModel):
    strategy_id: str
    worker_id: str
    symbol: str
    tick_lookback_value: Optional[int] = 30
    tick_lookback_unit: Optional[str] = "minutes"
    bar_size_points: float
    max_bars_in_memory: Optional[int] = 500
    lot_size: Optional[float] = 0.01
    strategy_parameters: Optional[Dict[str, Any]] = None


@router.post("/api/grid/deployments", tags=["Deployments"])
async def create_deployment_endpoint(payload: DeploymentCreate):
    strat = get_strategy(payload.strategy_id)
    if not strat:
        raise HTTPException(
            status_code=404,
            detail="Strategy not found. Upload it first.",
        )
    result = create_deployment(payload.model_dump())
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result)

    deployment = result["deployment"]
    file_content = get_strategy_file_content(payload.strategy_id)

    # Build command payload for worker
    cmd_payload = {
        "deployment_id": deployment["deployment_id"],
        "strategy_id": deployment["strategy_id"],
        "strategy_file_content": file_content,
        "strategy_class_name": strat.get("class_name"),
        "symbol": deployment["symbol"],
        "tick_lookback_value": deployment["tick_lookback_value"],
        "tick_lookback_unit": deployment["tick_lookback_unit"],
        "bar_size_points": deployment["bar_size_points"],
        "max_bars_in_memory": deployment["max_bars_in_memory"],
        "lot_size": deployment["lot_size"],
        "strategy_parameters": deployment.get("strategy_parameters") or {},
    }
    enqueue_command(payload.worker_id, "deploy_strategy", cmd_payload)
    update_deployment_state(deployment["deployment_id"], "sent_to_worker")

    return {
        "ok": True,
        "deployment_id": deployment["deployment_id"],
        "deployment": deployment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/deployments", tags=["Deployments"])
async def list_deployments():
    deployments = get_all_deployments()
    # Enrich with strategy names for UI display
    try:
        strat_list = get_all_strategies()
        strat_map = {s["strategy_id"]: s for s in strat_list}
        for d in deployments:
            sid = d.get("strategy_id", "")
            strat = strat_map.get(sid, {})
            d["strategy_name"] = strat.get("name", sid)
            d["strategy_version"] = strat.get("version", "")
    except Exception:
        pass  # Don't break listing if enrichment fails
    return {
        "ok": True,
        "deployments": deployments,
        "count": len(deployments),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/deployments/{deployment_id}", tags=["Deployments"])
async def get_deployment_detail(deployment_id: str):
    rec = get_deployment(deployment_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    return {"ok": True, "deployment": rec}


@router.post("/api/grid/deployments/{deployment_id}/stop", tags=["Deployments"])
async def stop_deployment_endpoint(deployment_id: str):
    dep = get_deployment(deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if dep.get("state") in ("stopped", "failed"):
        return {
            "ok": True,
            "deployment": dep,
            "message": "Already stopped/failed.",
        }
    enqueue_command(
        dep["worker_id"], "stop_strategy",
        {"deployment_id": deployment_id},
    )
    result = stop_deployment(deployment_id)
    return result


# =============================================================================
# Worker Commands (poll / ack)
# =============================================================================

@router.get("/api/grid/workers/{worker_id}/commands/poll",
            tags=["Worker Commands"])
async def poll_worker_commands(worker_id: str):
    commands = poll_commands(worker_id)
    return {
        "ok": True,
        "worker_id": worker_id,
        "commands": commands,
        "count": len(commands),
    }


class CommandAck(BaseModel):
    command_id: str


@router.post("/api/grid/workers/{worker_id}/commands/ack",
             tags=["Worker Commands"])
async def ack_worker_command(worker_id: str, payload: CommandAck):
    result = ack_command(worker_id, payload.command_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result)
    return result


# =============================================================================
# Runner Status (worker → mother deployment state sync)
# =============================================================================

class RunnerStatusReport(BaseModel):
    deployment_id: str
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    symbol: Optional[str] = None
    runner_state: str
    bar_size_points: Optional[float] = None
    max_bars_in_memory: Optional[int] = None
    current_bars_count: Optional[int] = 0
    last_signal: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.post("/api/grid/workers/{worker_id}/runner-status",
             tags=["Worker Commands"])
async def report_runner_status(worker_id: str,
                                payload: RunnerStatusReport):
    state_map = {
        "loading_strategy": "loading_strategy",
        "fetching_ticks": "fetching_ticks",
        "generating_initial_bars": "generating_initial_bars",
        "warming_up": "warming_up",
        "running": "running",
        "stopped": "stopped",
        "failed": "failed",
        "idle": "stopped",
    }
    dep_state = state_map.get(payload.runner_state)
    if dep_state:
        update_deployment_state(
            payload.deployment_id, dep_state,
            error=payload.last_error,
        )
    else:
        import logging
        logging.getLogger("jinni.routes").warning(
            f"Unknown runner_state '{payload.runner_state}' from "
            f"{worker_id} (dep={payload.deployment_id})"
        )
    return {"ok": True, "received": True}


# =============================================================================
# System Summary
# =============================================================================

@router.get("/api/system/summary", tags=["System"])
async def system_summary():
    fleet = get_fleet_summary()
    portfolio = get_portfolio_summary()
    total = fleet["total_workers"]
    online = fleet["online_workers"]
    if online > 0:
        system_status = "operational"
    elif total > 0:
        system_status = "degraded"
    else:
        system_status = "no_workers"
    return {
        "total_nodes": total,
        "online_nodes": online,
        "stale_nodes": fleet["stale_workers"],
        "offline_nodes": fleet["offline_workers"],
        "warning_nodes": fleet.get("warning_workers", 0),
        "error_nodes": fleet["error_workers"],
        "total_open_positions": portfolio.get("open_positions", 0),
        "system_status": system_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Settings
# =============================================================================

@router.get("/api/settings", tags=["Settings"])
async def get_settings():
    return {"ok": True, "settings": get_system_settings()}


class SettingsUpdate(BaseModel):
    settings: Dict[str, Any]


@router.put("/api/settings", tags=["Settings"])
async def update_settings(payload: SettingsUpdate):
    result = save_system_settings(payload.settings)
    return {"ok": True, "settings": result}


# =============================================================================
# Admin
# =============================================================================

@router.get("/api/admin/stats", tags=["Admin"])
async def admin_stats():
    return {"ok": True, "stats": admin_get_stats()}


@router.post("/api/admin/strategies/{strategy_id}/delete", tags=["Admin"])
async def admin_delete_strategy_endpoint(strategy_id: str):
    result = admin_delete_strategy(strategy_id)
    return {"ok": True, **result}


@router.post("/api/admin/portfolio/reset", tags=["Admin"])
async def admin_reset_portfolio_endpoint():
    result = admin_reset_portfolio()
    return {"ok": True, **result}


@router.post("/api/admin/trades/clear", tags=["Admin"])
async def admin_clear_trades_endpoint():
    result = admin_clear_trades()
    return {"ok": True, **result}


@router.post("/api/admin/workers/{worker_id}/remove", tags=["Admin"])
async def admin_remove_worker_endpoint(worker_id: str):
    result = admin_remove_worker(worker_id)
    return {"ok": True, **result}


@router.post("/api/admin/workers/stale/remove", tags=["Admin"])
async def admin_remove_stale_workers_endpoint():
    result = admin_remove_stale_workers()
    return {"ok": True, **result}


@router.post("/api/admin/events/clear", tags=["Admin"])
async def admin_clear_events_endpoint():
    result = admin_clear_events()
    return {"ok": True, **result}


class SystemResetConfirm(BaseModel):
    confirm: str


@router.post("/api/admin/system/reset", tags=["Admin"])
async def admin_full_reset_endpoint(payload: SystemResetConfirm):
    if payload.confirm != "RESET_EVERYTHING":
        raise HTTPException(
            status_code=400,
            detail="Must send confirm='RESET_EVERYTHING'",
        )
    result = admin_full_reset()
    return {"ok": True, "cleared": result}


@router.post("/api/admin/emergency-stop", tags=["Admin"])
async def emergency_stop():
    """Stop all strategies + close all positions across all workers."""
    result = emergency_stop_all()
    return result

# =============================================================================
# Charts — Live Bar + Marker Data
# =============================================================================

from app.persistence import (
    save_chart_bars_bulk, get_chart_bars,
    save_chart_markers_bulk, get_chart_markers,
)


@router.get("/api/charts/bars", tags=["Charts"])
async def get_chart_bars_endpoint(
    deployment_id: str = Query(...),
    since_index: int = Query(0),
    limit: int = Query(10000),
):
    bars = get_chart_bars(deployment_id, since_index=since_index, limit=limit)
    return {"ok": True, "bars": bars, "count": len(bars)}


@router.get("/api/charts/markers", tags=["Charts"])
async def get_chart_markers_endpoint(
    deployment_id: str = Query(...),
    since_id: int = Query(0),
    limit: int = Query(5000),
):
    markers = get_chart_markers(deployment_id, since_id=since_id, limit=limit)
    return {"ok": True, "markers": markers, "count": len(markers)}


@router.post("/api/charts/bars", tags=["Charts"])
async def push_chart_bars(payload: dict = Body(...)):
    deployment_id = payload.get("deployment_id")
    bars = payload.get("bars", [])
    if not deployment_id or not bars:
        raise HTTPException(status_code=400, detail="deployment_id and bars required")
    save_chart_bars_bulk(deployment_id, bars)
    return {"ok": True, "saved": len(bars)}


@router.post("/api/charts/markers", tags=["Charts"])
async def push_chart_markers(payload: dict = Body(...)):
    deployment_id = payload.get("deployment_id")
    markers = payload.get("markers", [])
    if not deployment_id or not markers:
        raise HTTPException(status_code=400, detail="deployment_id and markers required")
    save_chart_markers_bulk(deployment_id, markers)
    return {"ok": True, "saved": len(markers)}

# =============================================================================
# Charts — Live Bar + Marker Data
# =============================================================================

from app.persistence import (
    save_chart_bars_bulk, get_chart_bars,
    save_chart_markers_bulk, get_chart_markers,
)


@router.get("/api/charts/bars", tags=["Charts"])
async def get_chart_bars_endpoint(
    deployment_id: str = Query(...),
    since_index: int = Query(0),
    limit: int = Query(10000),
):
    bars = get_chart_bars(deployment_id, since_index=since_index, limit=limit)
    return {"ok": True, "bars": bars, "count": len(bars)}


@router.get("/api/charts/markers", tags=["Charts"])
async def get_chart_markers_endpoint(
    deployment_id: str = Query(...),
    since_id: int = Query(0),
    limit: int = Query(5000),
):
    markers = get_chart_markers(deployment_id, since_id=since_id, limit=limit)
    return {"ok": True, "markers": markers, "count": len(markers)}


@router.post("/api/charts/bars", tags=["Charts"])
async def push_chart_bars(payload: dict = Body(...)):
    deployment_id = payload.get("deployment_id")
    bars = payload.get("bars", [])
    if not deployment_id or not bars:
        raise HTTPException(status_code=400, detail="deployment_id and bars required")
    save_chart_bars_bulk(deployment_id, bars)
    return {"ok": True, "saved": len(bars)}


@router.post("/api/charts/markers", tags=["Charts"])
async def push_chart_markers(payload: dict = Body(...)):
    deployment_id = payload.get("deployment_id")
    markers = payload.get("markers", [])
    if not deployment_id or not markers:
        raise HTTPException(status_code=400, detail="deployment_id and markers required")
    save_chart_markers_bulk(deployment_id, markers)
    return {"ok": True, "saved": len(markers)}

# =============================================================================
# Validation Jobs
# =============================================================================

from app.persistence import (
    save_validation_job, update_validation_progress,
    complete_validation_job, fail_validation_job,
    get_validation_job, get_all_validation_jobs,
    delete_validation_job,
)


class ValidationJobCreate(BaseModel):
    strategy_id: str
    worker_id: str
    symbol: str
    month: int
    year: int = 2026
    lot_size: Optional[float] = 0.01
    bar_size_points: Optional[float] = 100
    max_bars_memory: Optional[int] = 500
    spread_points: Optional[float] = 0
    commission_per_lot: Optional[float] = 0
    strategy_parameters: Optional[Dict[str, Any]] = None


@router.post("/api/validation/jobs", tags=["Validation"])
async def create_validation_job(payload: ValidationJobCreate):
    """Create a new validation job and send to worker."""
    strat = get_strategy(payload.strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found.")

    import uuid
    job_id = "val-" + str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    file_content = get_strategy_file_content(payload.strategy_id)
    if not file_content:
        raise HTTPException(status_code=404,
                            detail="Strategy file content not found.")

    strat_name = strat.get("name", payload.strategy_id)

    # Save to DB
    save_validation_job(job_id, {
        "strategy_id": payload.strategy_id,
        "strategy_name": strat_name,
        "worker_id": payload.worker_id,
        "symbol": payload.symbol,
        "month": payload.month,
        "year": payload.year,
        "lot_size": payload.lot_size,
        "bar_size_points": payload.bar_size_points,
        "max_bars_memory": payload.max_bars_memory,
        "spread_points": payload.spread_points,
        "commission_per_lot": payload.commission_per_lot,
        "state": "queued",
    })

    # Send command to worker
    cmd_payload = {
        "job_id": job_id,
        "strategy_id": payload.strategy_id,
        "strategy_file_content": file_content,
        "strategy_class_name": strat.get("class_name"),
        "strategy_parameters": payload.strategy_parameters or {},
        "symbol": payload.symbol,
        "month": payload.month,
        "year": payload.year,
        "lot_size": payload.lot_size,
        "bar_size_points": payload.bar_size_points,
        "max_bars_memory": payload.max_bars_memory,
        "spread_points": payload.spread_points,
        "commission_per_lot": payload.commission_per_lot,
    }
    enqueue_command(payload.worker_id, "run_validation", cmd_payload)

    log_event_db("validation", "created",
                 f"Validation job {job_id} created: "
                 f"{strat_name} on {payload.symbol} "
                 f"{payload.year}-{payload.month:02d}",
                 worker_id=payload.worker_id,
                 strategy_id=payload.strategy_id,
                 symbol=payload.symbol)

    return {
        "ok": True,
        "job_id": job_id,
        "timestamp": now,
    }


@router.get("/api/validation/jobs", tags=["Validation"])
async def list_validation_jobs(limit: int = Query(50)):
    jobs = get_all_validation_jobs(limit=limit)
    return {
        "ok": True,
        "jobs": jobs,
        "count": len(jobs),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/validation/jobs/{job_id}", tags=["Validation"])
async def get_validation_job_detail(job_id: str):
    job = get_validation_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Validation job not found.")
    return {"ok": True, "job": job}


@router.post("/api/validation/jobs/{job_id}/progress", tags=["Validation"])
async def update_validation_job_progress(job_id: str,
                                          payload: dict = Body(...)):
    progress = payload.get("progress", 0)
    message = payload.get("progress_message", "")
    update_validation_progress(job_id, progress, message)
    return {"ok": True}


@router.post("/api/validation/jobs/{job_id}/results", tags=["Validation"])
async def receive_validation_results(job_id: str,
                                      payload: dict = Body(...)):
    if "error" in payload and payload["error"]:
        fail_validation_job(job_id, payload["error"])
        log_event_db("validation", "failed",
                     f"Validation {job_id} failed: {payload['error']}",
                     level="ERROR")
        return {"ok": True, "state": "failed"}

    results = payload.get("results", {})
    complete_validation_job(job_id, results)

    summary = results.get("summary", {})
    log_event_db("validation", "completed",
                 f"Validation {job_id} complete: "
                 f"{summary.get('total_trades', 0)} trades, "
                 f"net=${summary.get('net_pnl', 0):.2f}",
                 data=summary)

    return {"ok": True, "state": "completed"}


@router.delete("/api/validation/jobs/{job_id}", tags=["Validation"])
async def delete_validation_job_endpoint(job_id: str):
    delete_validation_job(job_id)
    return {"ok": True, "deleted": job_id}


@router.post("/api/validation/jobs/{job_id}/stop", tags=["Validation"])
async def stop_validation_job(job_id: str):
    job = get_validation_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("state") in ("completed", "failed"):
        return {"ok": True, "message": "Already finished."}
    enqueue_command(job["worker_id"], "stop_validation", {"job_id": job_id})
    fail_validation_job(job_id, "Cancelled by user")
    return {"ok": True, "message": "Stop command sent."}