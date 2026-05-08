"""
JINNI GRID — Portfolio / Trade Ledger
worker/portfolio.py

Persistent trade history + rolling stats + equity tracking.
SQLite-backed, one DB per worker in data/portfolio_{worker_id}.db.

API:
  ledger = TradeLedger(worker_id)
  ledger.add_trade(trade_record)
  ledger.get_all_trades()
  ledger.get_summary()
  ledger.get_equity_curve()
  ledger.export_summary()
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class TradeLedger:
    """Persistent trade ledger for a single worker."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self._lock = threading.Lock()
        os.makedirs(DATA_DIR, exist_ok=True)
        self._db_path = os.path.join(DATA_DIR, f"portfolio_{worker_id}.db")
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                deployment_id TEXT,
                strategy_id TEXT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_bar INTEGER,
                exit_bar INTEGER,
                entry_time INTEGER,
                exit_time INTEGER,
                exit_reason TEXT,
                sl_level REAL,
                tp_level REAL,
                lot_size REAL DEFAULT 0.01,
                ticket INTEGER,
                points_pnl REAL DEFAULT 0.0,
                profit REAL DEFAULT 0.0,
                bars_held INTEGER DEFAULT 0,
                status TEXT DEFAULT 'open',
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                data_json TEXT
            );

            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                balance REAL,
                equity REAL,
                floating_pnl REAL,
                open_positions INTEGER DEFAULT 0,
                cumulative_pnl REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
            CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
        """)
        conn.commit()
        conn.close()

    # ── Trade Management ────────────────────────────────────

    def add_trade(self, record: dict, deployment_id: str = None,
                  strategy_id: str = None) -> int:
        """Add a closed trade record. Returns the DB row ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute("""
                    INSERT INTO trades (trade_id, deployment_id, strategy_id, symbol,
                        direction, entry_price, exit_price, entry_bar, exit_bar,
                        entry_time, exit_time, exit_reason, sl_level, tp_level,
                        lot_size, ticket, points_pnl, profit, bars_held,
                        status, opened_at, closed_at, data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.get("id"), deployment_id, strategy_id,
                    record.get("symbol", ""), record.get("direction", ""),
                    record.get("entry_price", 0), record.get("exit_price"),
                    record.get("entry_bar"), record.get("exit_bar"),
                    record.get("entry_time"), record.get("exit_time"),
                    record.get("exit_reason"), record.get("sl_level"),
                    record.get("tp_level"), record.get("lot_size", 0.01),
                    record.get("ticket"), record.get("points_pnl", 0),
                    record.get("profit", 0), record.get("bars_held", 0),
                    "closed", now, now,
                    json.dumps(record, default=str),
                ))
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def record_equity_snapshot(self, balance: float, equity: float,
                               floating_pnl: float, open_positions: int):
        """Periodic equity snapshot for curve building."""
        now = datetime.now(timezone.utc).isoformat()
        cum = self._get_cumulative_pnl()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    INSERT INTO equity_snapshots (timestamp, balance, equity,
                        floating_pnl, open_positions, cumulative_pnl)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (now, balance, equity, floating_pnl, open_positions, cum))
                conn.commit()
            finally:
                conn.close()

    def _get_cumulative_pnl(self) -> float:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(profit), 0.0) as total FROM trades WHERE status='closed'"
            ).fetchone()
            return float(row["total"]) if row else 0.0
        finally:
            conn.close()

    # ── Queries ─────────────────────────────────────────────

    def get_all_trades(self, limit: int = 500, symbol: str = None,
                       strategy_id: str = None) -> List[dict]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM trades WHERE status='closed'"
            params = []
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            if strategy_id:
                query += " AND strategy_id = ?"
                params.append(strategy_id)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_open_trades(self) -> List[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='open' ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_equity_curve(self, limit: int = 1000) -> List[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM equity_snapshots ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()

    def get_summary(self) -> dict:
        """Compute rolling stats from closed trades."""
        conn = self._get_conn()
        try:
            trades = conn.execute(
                "SELECT direction, profit, points_pnl, bars_held, exit_reason "
                "FROM trades WHERE status='closed' ORDER BY id"
            ).fetchall()

            if not trades:
                return {
                    "total_trades": 0, "wins": 0, "losses": 0,
                    "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                    "avg_winner": 0.0, "avg_loser": 0.0,
                    "best_trade": 0.0, "worst_trade": 0.0,
                    "avg_bars_held": 0.0, "longs": 0, "shorts": 0,
                    "avg_r": 0.0, "profit_factor": 0.0,
                }

            profits = [float(t["profit"]) for t in trades]
            wins = [p for p in profits if p > 0]
            losses = [p for p in profits if p <= 0]
            bars_list = [int(t["bars_held"]) for t in trades]
            longs = sum(1 for t in trades if t["direction"] == "long")
            shorts = sum(1 for t in trades if t["direction"] == "short")

            gross_profit = sum(wins) if wins else 0.0
            gross_loss = abs(sum(losses)) if losses else 0.0

            return {
                "total_trades": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
                "total_pnl": round(sum(profits), 2),
                "avg_pnl": round(sum(profits) / len(trades), 2) if trades else 0.0,
                "avg_winner": round(sum(wins) / len(wins), 2) if wins else 0.0,
                "avg_loser": round(sum(losses) / len(losses), 2) if losses else 0.0,
                "best_trade": round(max(profits), 2) if profits else 0.0,
                "worst_trade": round(min(profits), 2) if profits else 0.0,
                "avg_bars_held": round(sum(bars_list) / len(bars_list), 1) if bars_list else 0.0,
                "longs": longs,
                "shorts": shorts,
                "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0,
            }
        finally:
            conn.close()

    def export_summary(self) -> dict:
        """Full export for API/UI consumption."""
        return {
            "worker_id": self.worker_id,
            "stats": self.get_summary(),
            "recent_trades": self.get_all_trades(limit=50),
            "equity_curve": self.get_equity_curve(limit=500),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }