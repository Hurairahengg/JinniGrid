"""JINNI Grid - Portfolio Endpoints  app/routes/portfolio.py"""
from datetime import datetime, timezone
from fastapi import APIRouter
from app.services.mock_data import get_portfolio_summary, get_equity_history

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])

@router.get("/summary")
async def portfolio_summary():
    return {"portfolio": get_portfolio_summary(), "timestamp": datetime.now(timezone.utc).isoformat()}

@router.get("/equity-history")
async def equity_history():
    h = get_equity_history()
    return {"equity_history": h, "points": len(h), "timestamp": datetime.now(timezone.utc).isoformat()}
