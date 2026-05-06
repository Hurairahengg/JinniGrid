"""JINNI Grid - Health Check Endpoint app/routes/health.py"""
from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import Config

router = APIRouter(prefix="/api", tags=["Health"])

@router.get("/health")
async def health_check():
    app_config = Config.get_app_config()
    return {
        "status": "ok",
        "service": app_config["name"],
        "version": app_config["version"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
