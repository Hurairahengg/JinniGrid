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


@router.post("/api/portfolio/trades/report", tags=["Portfolio"])
async def report_trade(payload: dict = Body(...)):
    """Receive trade report from worker VM. Saves immediately to DB."""
    ok = save_trade_db(payload)
    if ok:
        log_event_db(
            "execution", "trade_closed",
            f"{payload.get('direction', '?')} {payload.get('symbol', '?')} "
            f"profit={payload.get('profit', 0)}",
            worker_id=payload.get("worker_id"),
            strategy_id=payload.get("strategy_id"),
            deployment_id=payload.get("deployment_id"),
            symbol=payload.get("symbol"),
            data=payload, level="INFO",
        )
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
    rec = get_strategy(strategy_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Strategy not found.")
    # Ensure parameters is a dict
    params = rec.get("parameters", {})
    if isinstance(params, str):
        try:
            import json
            params = json.loads(params)
        except Exception:
            params = {}
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