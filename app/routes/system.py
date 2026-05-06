"""JINNI Grid - System Summary"""
from datetime import datetime, timezone
from fastapi import APIRouter
from app.services.worker_registry import get_fleet_summary
from app.services.mock_data import get_portfolio_summary

router = APIRouter(prefix="/api/system", tags=["System"])

@router.get("/summary")
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
        "total_nodes": total, "online_nodes": online,
        "stale_nodes": fleet["stale_workers"], "offline_nodes": fleet["offline_workers"],
        "warning_nodes": fleet["warning_workers"], "error_nodes": fleet["error_workers"],
        "total_open_positions": portfolio["open_positions"],
        "system_status": system_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
