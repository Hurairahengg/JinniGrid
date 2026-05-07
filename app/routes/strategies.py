"""
JINNI Grid - Strategy + Deployment + Command Endpoints
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.services.strategy_registry import (
    upload_strategy, get_all_strategies, get_strategy,
    get_strategy_file_content, validate_strategy,
)
from app.services.deployment_registry import (
    create_deployment, get_all_deployments, get_deployment,
    update_deployment_state, stop_deployment,
)
from app.services.command_queue import (
    enqueue_command, poll_commands, ack_command,
)

router = APIRouter(prefix="/api/grid", tags=["Strategies"])


# ── Strategy Endpoints ──────────────────────────────────────────────

@router.post("/strategies/upload")
async def upload_strategy_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files accepted.")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 text.")
    result = upload_strategy(file.filename, text)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/strategies")
async def list_strategies():
    return {
        "ok": True,
        "strategies": get_all_strategies(),
        "count": len(get_all_strategies()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy_detail(strategy_id: str):
    rec = get_strategy(strategy_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Strategy not found.")
    return {"ok": True, "strategy": rec}


@router.get("/strategies/{strategy_id}/file")
async def get_strategy_file(strategy_id: str):
    """Return raw .py content — used by workers to fetch strategy code."""
    content = get_strategy_file_content(strategy_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Strategy file not found.")
    return {"ok": True, "strategy_id": strategy_id, "file_content": content}


@router.post("/strategies/{strategy_id}/validate")
async def validate_strategy_endpoint(strategy_id: str):
    result = validate_strategy(strategy_id)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result)
    return result


# ── Deployment Endpoints ────────────────────────────────────────────

class DeploymentCreate(BaseModel):
    strategy_id: str
    worker_id: str
    symbol: str
    tick_lookback_value: Optional[int] = 30
    tick_lookback_unit: Optional[str] = "minutes"
    bar_size_points: float
    max_bars_in_memory: Optional[int] = 500
    lot_size: Optional[float] = 0.01
    strategy_parameters: Optional[Dict[str, Any]] = {}


@router.post("/deployments")
async def create_deployment_endpoint(payload: DeploymentCreate):
    # Verify strategy exists
    strat = get_strategy(payload.strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found. Upload it first.")

    # Create deployment record
    result = create_deployment(payload.model_dump())
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result)

    deployment = result["deployment"]

    # Fetch strategy file content for the worker
    file_content = get_strategy_file_content(payload.strategy_id)

    # Enqueue deploy command for the worker
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
        "strategy_parameters": deployment["strategy_parameters"],
    }
    enqueue_command(payload.worker_id, "deploy_strategy", cmd_payload)

    # Update deployment state
    update_deployment_state(deployment["deployment_id"], "sent_to_worker")

    return {
        "ok": True,
        "deployment_id": deployment["deployment_id"],
        "deployment": deployment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/deployments")
async def list_deployments():
    return {
        "ok": True,
        "deployments": get_all_deployments(),
        "count": len(get_all_deployments()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/deployments/{deployment_id}")
async def get_deployment_detail(deployment_id: str):
    rec = get_deployment(deployment_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    return {"ok": True, "deployment": rec}


@router.post("/deployments/{deployment_id}/stop")
async def stop_deployment_endpoint(deployment_id: str):
    dep = get_deployment(deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    # Enqueue stop command for the worker
    enqueue_command(dep["worker_id"], "stop_strategy", {
        "deployment_id": deployment_id,
    })

    result = stop_deployment(deployment_id)
    return result


# ── Worker Command Endpoints ────────────────────────────────────────

@router.get("/workers/{worker_id}/commands/poll")
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


@router.post("/workers/{worker_id}/commands/ack")
async def ack_worker_command(worker_id: str, payload: CommandAck):
    result = ack_command(worker_id, payload.command_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result)
    return result


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


@router.post("/workers/{worker_id}/runner-status")
async def report_runner_status(worker_id: str, payload: RunnerStatusReport):
    """Worker reports its runner state. Mother updates deployment accordingly."""
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
            payload.deployment_id,
            dep_state,
            error=payload.last_error,
        )
    return {"ok": True, "received": True}