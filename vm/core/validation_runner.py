"""
JINNI GRID — Validation Runner (Thin Orchestrator)
vm/core/validation_runner.py

Fetches historical ticks → creates SimulatedExecutor →
calls StrategyRunner.run_validation() which uses the
EXACT SAME _on_new_bar() as live trading.
"""

from __future__ import annotations

import math
import os
import threading
import traceback
from datetime import datetime, timezone
from typing import Optional


class ValidationRunner:
    """Orchestrates a validation job using the real StrategyRunner engine."""

    def __init__(self, job_config: dict,
                 progress_callback=None,
                 results_callback=None):
        self.job_id = job_config["job_id"]
        self.strategy_id = job_config["strategy_id"]
        self.symbol = job_config["symbol"]
        self.month = int(job_config["month"])
        self.year = int(job_config["year"])
        self.lot_size = float(job_config.get("lot_size", 0.01))
        self.bar_size_points = float(job_config.get("bar_size_points", 100))
        self.max_bars_memory = int(job_config.get("max_bars_memory", 500))
        self.spread_points = float(job_config.get("spread_points", 0))
        self.commission_per_lot = float(job_config.get("commission_per_lot", 0))
        self.strategy_file_content = job_config.get("strategy_file_content", "")
        self.strategy_class_name = job_config.get("strategy_class_name", "")
        self.strategy_parameters = job_config.get("strategy_parameters", {})
        self._job_config = job_config

        self._progress_cb = progress_callback
        self._results_cb = results_callback
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._runner = None

        # Collected from trade_callback
        self._trades = []
        self._equity_snapshots = []

    # ── Lifecycle ────────────────────────────────────────────

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._runner:
            self._runner.stop()
        if self._thread:
            self._thread.join(timeout=30)

    # ── Progress / Results ───────────────────────────────────

    def _report_progress(self, pct: float, msg: str):
        if self._progress_cb:
            try:
                self._progress_cb({
                    "job_id": self.job_id,
                    "progress": round(min(pct, 100), 1),
                    "progress_message": msg,
                })
            except Exception:
                pass

    def _report_results(self, results: dict):
        if self._results_cb:
            try:
                self._results_cb({"job_id": self.job_id, "results": results})
            except Exception as e:
                print(f"[VALIDATION] Results report failed: {e}")

    def _report_error(self, error: str):
        if self._results_cb:
            try:
                self._results_cb({"job_id": self.job_id, "error": error})
            except Exception:
                pass

    # ── Trade Callback (collects trades from StrategyRunner) ─

    def _on_trade(self, record: dict):
        """Called by StrategyRunner when a trade closes — same callback API as live."""
        self._trades.append(record)
        balance = sum(t.get("profit", 0) for t in self._trades)
        print(f"[VALIDATION] Trade #{len(self._trades)}: "
              f"{record.get('direction', '?')} {record.get('symbol', '?')} "
              f"pnl={record.get('profit', 0):.2f} bal={balance:.2f}")

    # ── Main Run ─────────────────────────────────────────────

    def _run(self):
        try:
            self._report_progress(0, "Initializing validation…")
            print(f"[VALIDATION] Job {self.job_id}: "
                  f"{self.strategy_id} on {self.symbol} "
                  f"{self.year}-{self.month:02d}")

            # ── 1. Connect MT5 (for tick data ONLY) ──
            self._report_progress(5, "Connecting to MT5 for tick data…")
            mt5, sym_info = self._init_mt5()
            if mt5 is None:
                return

            point = sym_info.point
            tick_size = sym_info.trade_tick_size or point
            tick_value = sym_info.trade_tick_value or 1.0

            print(f"[VALIDATION] Symbol: point={point} "
                  f"tick_size={tick_size} tick_value={tick_value}")

            # ── 2. Fetch historical ticks ──
            self._report_progress(10, f"Fetching {self.symbol} ticks "
                                  f"for {self.year}-{self.month:02d}…")
            ticks = self._fetch_ticks(mt5)
            if not ticks:
                self._report_error(
                    f"No tick data for {self.symbol} "
                    f"{self.year}-{self.month:02d}")
                return

            total_ticks = len(ticks)
            print(f"[VALIDATION] Fetched {total_ticks:,} ticks")
            self._report_progress(20, f"Got {total_ticks:,} ticks. "
                                  "Starting engine…")

            # ── 3. Create SimulatedExecutor ──
            from trading.sim_executor import SimulatedExecutor
            sim_executor = SimulatedExecutor(
                symbol=self.symbol,
                lot_size=self.lot_size,
                deployment_id=self.job_id,
                point=point,
                tick_size=tick_size,
                tick_value=tick_value,
            )

            # ── 4. Build deployment config (same format as live) ──
            deploy_config = {
                "deployment_id": self.job_id,
                "strategy_id": self.strategy_id,
                "strategy_file_content": self.strategy_file_content,
                "strategy_class_name": self.strategy_class_name,
                "strategy_parameters": self.strategy_parameters,
                "symbol": self.symbol,
                "lot_size": self.lot_size,
                "bar_size_points": self.bar_size_points,
                "max_bars_in_memory": self.max_bars_memory,
                "worker_id": self._job_config.get("worker_id", "validation"),
            }

            # ── 5. Create StrategyRunner in VALIDATION MODE ──
            from core.strategy_worker import StrategyRunner

            self._runner = StrategyRunner(
                deployment_config=deploy_config,
                status_callback=None,
                trade_callback=self._on_trade,
                validation_mode=True,           # ← THE KEY FLAG
            )

            # ── 6. Run validation — feeds ticks through the
            #        SAME _on_new_bar() that runs live ──
            self._report_progress(25, "Running simulation…")

            def progress_bridge(pct, msg):
                # Map runner's 0-100 to our 25-90
                mapped = 25 + (pct / 100) * 65
                self._report_progress(mapped, msg)

            self._runner.run_validation(
                ticks=ticks,
                executor=sim_executor,
                progress_cb=progress_bridge,
            )

            if self._stop_event.is_set():
                self._report_error("Cancelled by user")
                return

            # ── 7. Compute stats from collected trades ──
            self._report_progress(92, "Computing statistics…")
            results = self._compute_results(total_ticks, tick_size, tick_value)
            self._report_progress(100, "Validation complete!")
            self._report_results(results)

            print(f"[VALIDATION] Job {self.job_id} done: "
                  f"{len(self._trades)} trades, "
                  f"net={results['summary']['net_pnl']:.2f}")

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[VALIDATION] FAILED: {e}\n{tb}")
            self._report_error(f"{type(e).__name__}: {e}")

    # ── MT5 Init (for tick data only) ────────────────────────

    def _init_mt5(self):
        try:
            import MetaTrader5 as mt5
        except ImportError:
            self._report_error("MetaTrader5 package not installed")
            return None, None

        if not mt5.initialize():
            self._report_error(f"MT5 init failed: {mt5.last_error()}")
            return None, None

        sym_info = mt5.symbol_info(self.symbol)
        if sym_info is None:
            self._report_error(f"Symbol '{self.symbol}' not found")
            mt5.shutdown()
            return None, None

        if not sym_info.visible:
            mt5.symbol_select(self.symbol, True)

        return mt5, sym_info

    # ── Tick Fetching ────────────────────────────────────────

    def _fetch_ticks(self, mt5):
        from_dt = datetime(self.year, self.month, 1, tzinfo=timezone.utc)
        if self.month == 12:
            to_dt = datetime(self.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            to_dt = datetime(self.year, self.month + 1, 1, tzinfo=timezone.utc)

        raw_ticks = mt5.copy_ticks_range(
            self.symbol, from_dt, to_dt, mt5.COPY_TICKS_ALL)

        if raw_ticks is None or len(raw_ticks) == 0:
            return None

        result = []
        for raw in raw_ticks:
            try:
                ts = int(raw.time) if hasattr(raw, 'time') else int(raw[0])
                bid = float(raw.bid) if hasattr(raw, 'bid') else float(raw[1])
                ask = float(raw.ask) if hasattr(raw, 'ask') else float(raw[2])
                vol = float(raw.volume) if hasattr(raw, 'volume') else 0
            except (ValueError, TypeError, IndexError):
                continue
            price = bid if bid > 0 else ask
            if price <= 0:
                continue
            result.append({"ts": ts, "price": price, "bid": bid,
                           "ask": ask, "volume": vol})

        return result

    # ── Results Computation ──────────────────────────────────

    def _compute_results(self, total_ticks, tick_size, tick_value):
        trades = self._trades
        n = len(trades)

        # Build equity curve from trade sequence
        balance = 0.0
        equity_curve = [{"trade_index": 0, "balance": 0, "equity": 0}]
        for i, t in enumerate(trades):
            pnl = float(t.get("profit", 0) or 0)
            comm = 0.0
            if self.commission_per_lot > 0:
                lot = float(t.get("lot_size", self.lot_size) or self.lot_size)
                comm = round(-self.commission_per_lot * lot * 2, 2)
            net = round(pnl + comm, 2)
            t["commission"] = comm
            t["net_pnl"] = net
            balance = round(balance + net, 2)
            t["balance_after"] = balance
            equity_curve.append({
                "trade_index": i + 1,
                "balance": balance,
                "equity": balance,
            })

        if n == 0:
            return {
                "summary": self._empty_summary(),
                "trades": [],
                "equity_curve": equity_curve,
                "total_ticks": total_ticks,
            }

        profits = [t["net_pnl"] for t in trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]

        gp = round(sum(wins), 2) if wins else 0
        gl = round(sum(losses), 2) if losses else 0
        net = round(gp + gl, 2)
        agl = abs(gl)

        # Max drawdown
        cum, peak, dd_usd, dd_pct = 0.0, 0.0, 0.0, 0.0
        for p in profits:
            cum += p
            if cum > peak:
                peak = cum
            d = peak - cum
            dd_usd = max(dd_usd, d)
            if peak > 0.01:
                dd_pct = max(dd_pct, min((d / peak) * 100, 100.0))

        # Sharpe
        mean = net / n if n else 0
        if n > 1:
            var = sum((p - mean) ** 2 for p in profits) / (n - 1)
            std = math.sqrt(var) if var > 0 else 0
            sharpe = round(mean / std * math.sqrt(252), 2) if std > 0 else 0
        else:
            sharpe = 0

        # Sortino
        down = [p for p in profits if p < 0]
        if down:
            dvar = sum(p ** 2 for p in down) / len(down)
            dstd = math.sqrt(dvar) if dvar > 0 else 0
            sortino = round(mean / dstd * math.sqrt(252), 2) if dstd > 0 else 0
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

        bars_list = [int(t.get("bars_held", 0) or 0) for t in trades]
        pf = round(gp / agl, 2) if agl > 0 else (999.99 if gp > 0 else 0)
        rf = round(net / dd_usd, 2) if dd_usd > 0 else 0

        summary = {
            "total_trades": n,
            "wins": len(wins),
            "losses": len(losses),
            "gross_profit": gp,
            "gross_loss": gl,
            "net_pnl": net,
            "win_rate": round(len(wins) / n * 100, 1) if n else 0,
            "profit_factor": pf,
            "expectancy": round(net / n, 2) if n else 0,
            "avg_trade": round(net / n, 2) if n else 0,
            "avg_winner": round(gp / len(wins), 2) if wins else 0,
            "avg_loser": round(gl / len(losses), 2) if losses else 0,
            "best_trade": round(max(profits), 2),
            "worst_trade": round(min(profits), 2),
            "max_drawdown_pct": round(dd_pct, 2),
            "max_drawdown_usd": round(dd_usd, 2),
            "recovery_factor": rf,
            "sharpe_estimate": sharpe,
            "sortino_estimate": sortino,
            "avg_bars_held": round(sum(bars_list) / n, 1) if n else 0,
            "max_consec_wins": mcw,
            "max_consec_losses": mcl,
        }

        return {
            "summary": summary,
            "trades": trades,
            "equity_curve": equity_curve,
            "total_ticks": total_ticks,
        }

    def _empty_summary(self):
        return {k: 0 for k in (
            "total_trades", "wins", "losses", "gross_profit", "gross_loss",
            "net_pnl", "win_rate", "profit_factor", "expectancy",
            "avg_trade", "avg_winner", "avg_loser", "best_trade",
            "worst_trade", "max_drawdown_pct", "max_drawdown_usd",
            "recovery_factor", "sharpe_estimate", "sortino_estimate",
            "avg_bars_held", "max_consec_wins", "max_consec_losses",
        )}