"""
JINNI Grid - Mock Data Service
Portfolio and equity curve only. Fleet data is real (worker_registry). 
app/services/mock_data.py
"""
import random
from datetime import datetime, timedelta, timezone

def get_portfolio_summary() -> dict:
    return {
        "total_balance": 248750.00, "total_equity": 251320.45,
        "floating_pnl": 2570.45, "daily_pnl": 1847.30,
        "open_positions": 12, "realized_pnl": 18432.60,
        "margin_usage": 34.7, "win_rate": 68.5,
    }

def get_equity_history() -> list:
    rng = random.Random(42)
    points = []
    start = datetime(2026, 2, 5, tzinfo=timezone.utc)
    val = 200000.0
    for i in range(90):
        d = start + timedelta(days=i)
        val += (rng.random() - 0.42) * 2000
        if val < 180000: val = 180000.0
        points.append({"timestamp": d.strftime("%Y-%m-%d"), "equity": round(val, 2)})
    return points
