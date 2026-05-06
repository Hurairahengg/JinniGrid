"""JINNI Grid - Grid Fleet Endpoints app/routes/grid.py"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.worker_registry import process_heartbeat, get_all_workers, get_fleet_summary

router = APIRouter(prefix="/api/Grid", tags=["Grid"])


class HeartbeatPayload(BaseModel):
    worker_id: str
    worker_name: Optional[str] = None
    host: Optional[str] = None
    state: Optional[str] = "online"
    agent_version: Optional[str] = None
    mt5_state: Optional[str] = None
    account_id: Optional[str] = None
    broker: Optional[str] = None
    active_strategies: Optional[List[str]] = []
    open_positions_count: Optional[int] = 0
    floating_pnl: Optional[float] = None
    errors: Optional[List[str]] = []


@router.post("/workers/heartbeat")
async def worker_heartbeat(payload: HeartbeatPayload):
    if not payload.worker_id or not payload.worker_id.strip():
        raise HTTPException(status_code=422, detail={
            "ok": False, "error": "worker_id is required and must be a non-empty string"
        })
    return process_heartbeat(payload.model_dump())


@router.get("/workers")
async def list_workers():
    return {
        "ok": True,
        "workers": get_all_workers(),
        "summary": get_fleet_summary(),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
