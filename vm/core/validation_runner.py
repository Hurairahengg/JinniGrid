"""
JINNI GRID — Validation Runner (Backtester)
vm/core/validation_runner.py

Runs a strategy against historical tick data using the SAME engine logic
as live trading. Produces trade history, equity curve, and statistics.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
import statistics
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.strategy_worker import RangeBarEngine, BaseStrategy, StrategyContext
from trading.execution import (
    validate_signal, compute_sl, compute_tp,
    PositionState, build_trade_record,
    SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE,
    SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT,
)
from trading.indicators import IndicatorEngine


class ValidationRunner:
    """
    Backtest engine reusing the live trading pipeline identically.
    Fetches historical ticks from MT5, builds range bars, runs strategy,
    simulates trades with SL/TP, and produces a full report.
    """

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

        self._progress_cb = progress_callback
        self._results_cb = results_callback
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._trades: List[dict] = []
        self._equity_curve: List[dict] = []
        self._trade_counter = 0

        # MT5 symbol metrics — set during init
        self._tick_size = 0.00001
        self._tick_value = 1.0
        self._point = 0.00001

    # ── Lifecycle ────────────────────────────────────────────

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=30)

    # ── Reporting ────────────────────────────────────────────

    def _report_progress(self, pct: float, msg: str):
        if self._progress_cb:
            try:
                self._progress_cb({
                    "job_id": self.job_id,
                    "progress": round(min(pct, 100), 1),
                    "progress_message": msg,
                })
            except Exception as e:
                print(f"[VALIDATION] Progress report failed: {e}")

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
            except Exception as e:
                print(f"[VALIDATION] Error report failed: {e}")

    # ── Main Run ─────────────────────────────────────────────

    def _run(self):
        try:
            self._report_progress(0, "Initializing validation…")
            print(f"[VALIDATION] Starting job {self.job_id}: "
                  f"{self.strategy_id} on {self.symbol} "
                  f"{self.year}-{self.month:02d}")

            # 1 — Load strategy
            self._report_progress(5, "Loading strategy…")
            strategy = self._load_strategy()
            if strategy is None:
                return

            # 2 — Connect MT5
            self._report_progress(10, "Connecting to MT5…")
            mt5, sym_info = self._init_mt5()
            if mt5 is None:
                return

            # Store symbol metrics
            self._point = sym_info.point
            ts = sym_info.trade_tick_size
            tv = sym_info.trade_tick_value
            self._tick_size = ts if ts > 0 else self._point
            self._tick_value = tv if tv > 0 else 1.0

            print(f"[VALIDATION] Symbol info: point={self._point} "
                  f"tick_size={self._tick_size} tick_value={self._tick_value}")

            # 3 — Fetch ticks
            self._report_progress(15, f"Fetching tick data for "
                                  f"{self.symbol} {self.year}-{self.month:02d}…")
            ticks = self._fetch_ticks(mt5)
            if ticks is None or len(ticks) == 0:
                self._report_error(
                    f"No tick data for {self.symbol} "
                    f"in {self.year}-{self.month:02d}")
                return

            total_ticks = len(ticks)
            print(f"[VALIDATION] Fetched {total_ticks:,} ticks")
            self._report_progress(25, f"Fetched {total_ticks:,} ticks. "
                                  "Running simulation…")

            # 4 — Simulate
            self._simulate(strategy, ticks, sym_info)

            if self._stop_event.is_set():
                self._report_error("Validation cancelled by user")
                return

            # 5 — Compute & report
            self._report_progress(95, "Computing statistics…")
            results = self._compute_results(total_ticks)
            self._report_progress(100, "Validation complete!")
            self._report_results(results)

            print(f"[VALIDATION] Job {self.job_id} done: "
                  f"{len(self._trades)} trades, "
                  f"net={results['summary']['net_pnl']:.2f}")

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[VALIDATION] FAILED: {e}\n{tb}")
            self._report_error(f"{type(e).__name__}: {e}")

    # ── Strategy Loading ─────────────────────────────────────

    def _load_strategy(self):
        tmp_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "validation_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f"strat_{self.job_id}.py")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(self.strategy_file_content)

            spec = importlib.util.spec_from_file_location(
                f"val_strat_{self.job_id}", tmp_path)
            mod = importlib.util.module_from_spec(spec)
            mod.BaseStrategy = BaseStrategy
            mod.__builtins__ = __builtins__
            spec.loader.exec_module(mod)

            cls = getattr(mod, self.strategy_class_name, None)
            if cls is None:
                self._report_error(
                    f"Class '{self.strategy_class_name}' not found")
                return None

            instance = cls()
            if self.strategy_parameters:
                for k, v in self.strategy_parameters.items():
                    if hasattr(instance, k):
                        setattr(instance, k, v)

            print(f"[VALIDATION] Strategy loaded: {self.strategy_class_name}")
            return instance

        except Exception as e:
            self._report_error(f"Strategy load failed: {e}")
            return None
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    # ── MT5 Init ─────────────────────────────────────────────

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
            self._report_error(f"Symbol '{self.symbol}' not found in MT5")
            mt5.shutdown()
            return None, None

        if not sym_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                self._report_error(
                    f"Failed to enable symbol '{self.symbol}' in MT5")
                mt5.shutdown()
                return None, None

        return mt5, sym_info

    # ── Tick Fetching ────────────────────────────────────────

    def _fetch_ticks(self, mt5):
        from_dt = datetime(self.year, self.month, 1, tzinfo=timezone.utc)
        if self.month == 12:
            to_dt = datetime(self.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            to_dt = datetime(self.year, self.month + 1, 1, tzinfo=timezone.utc)

        print(f"[VALIDATION] Fetching ticks: {self.symbol} "
              f"from {from_dt.isoformat()} to {to_dt.isoformat()}")

        ticks = mt5.copy_ticks_range(
            self.symbol, from_dt, to_dt, mt5.COPY_TICKS_ALL)

        if ticks is None or len(ticks) == 0:
            err = mt5.last_error()
            print(f"[VALIDATION] No ticks returned. MT5 error: {err}")
            return None

        result = []
        for raw in ticks:
            try:
                ts = int(raw.time) if hasattr(raw, 'time') else int(raw[0])
                bid = float(raw.bid) if hasattr(raw, 'bid') else float(raw[1])
                ask = float(raw.ask) if hasattr(raw, 'ask') else float(raw[2])
                vol = float(raw.volume) if hasattr(raw, 'volume') else float(
                    raw[5] if len(raw) > 5 else 0)
            except (ValueError, TypeError, IndexError):
                continue
            price = bid if bid > 0 else ask
            if price <= 0:
                continue
            result.append({"ts": ts, "price": price, "bid": bid,
                           "ask": ask, "volume": vol})

        return result

    # ── Simulation Engine ────────────────────────────────────

    def _simulate(self, strategy, ticks: list, sym_info):
        """
        Full backtester using the SAME engine logic as live:
          - RangeBarEngine builds bars from ticks
          - Strategy runs on_bar() per completed bar
          - Signal-on-close, execute-on-next-open model
          - SL/TP checked every bar (high/low)
          - MA cross exits
        """
        total_ticks = len(ticks)
        params = strategy.validate_parameters(self.strategy_parameters)
        ctx = StrategyContext(bars=[], params=params)
        ctx.state = {}

        indicator_defs = strategy.build_indicators(params)
        ind_engine = IndicatorEngine(indicator_defs)
        min_lb = getattr(strategy, "min_lookback", 0) or 0

        # Init strategy
        try:
            strategy.on_init(ctx)
        except Exception as e:
            self._report_error(f"on_init() failed: {e}")
            return

        # Build all bars first (identical to live: tick → RangeBarEngine)
        bar_engine = RangeBarEngine(
            bar_size_points=self.bar_size_points,
            max_bars=self.max_bars_memory,
            on_bar=None,
            debug=False,
        )

        # Feed ALL ticks to generate the bar series
        report_every = max(1, total_ticks // 20)
        for i, tick in enumerate(ticks):
            if self._stop_event.is_set():
                return
            bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])
            if i > 0 and i % report_every == 0:
                pct = 25 + (i / total_ticks) * 40
                self._report_progress(pct,
                    f"Building bars… {bar_engine.total_bars_emitted} bars "
                    f"from {i:,}/{total_ticks:,} ticks")

        all_bars = list(bar_engine.bars)
        total_bars = len(all_bars)
        print(f"[VALIDATION] Generated {total_bars} bars "
              f"from {total_ticks:,} ticks")

        if total_bars < 2:
            self._report_error(
                f"Only {total_bars} bars generated. "
                f"Bar size {self.bar_size_points} may be too large "
                f"for {self.symbol}.")
            return

        self._report_progress(65, f"Simulating {total_bars} bars…")

        # Simulation state
        position: Optional[PositionState] = None
        pending_signal: Optional[dict] = None
        active_meta: Optional[dict] = None
        prev_indicators: dict = {}
        absolute_bar_idx = -1
        balance = 0.0
        peak_balance = 0.0
        equity_curve = []

        report_every_bar = max(1, total_bars // 30)

        for bar_idx in range(total_bars):
            if self._stop_event.is_set():
                return

            absolute_bar_idx += 1
            bar = all_bars[bar_idx]
            bar_slice = all_bars[:bar_idx + 1]

            ctx._bars = bar_slice
            ctx._bar_offset = len(bar_slice) - 1
            ctx._index = absolute_bar_idx
            ctx._prev_indicators = dict(prev_indicators)
            ctx.balance = balance

            if position and position.has_position:
                ctx._position = position
            else:
                ctx._position = PositionState()

            # Update indicators
            ind_engine.update(bar_slice, ctx)

            # ═══ STEP 1: Execute pending entry ═══
            just_entered = False
            if pending_signal is not None and not ctx._position.has_position:
                direction = pending_signal["direction"]
                fill_price = float(bar["open"])

                # Apply spread for shorts
                if direction == "short" and self.spread_points > 0:
                    fill_price += self.spread_points * self._point

                # Compute SL
                sl_level = None
                risk_pts = None
                sl_mode = pending_signal.get("sl_mode")

                if sl_mode == "fixed":
                    pts = float(pending_signal.get("sl_pts", 0) or 0)
                    if pts > 0:
                        sl_level = round(
                            (fill_price - pts) if direction == "long"
                            else (fill_price + pts), 5)
                        risk_pts = pts
                elif sl_mode == "ma_snapshot":
                    ma_val = pending_signal.get("sl_ma_val")
                    if ma_val is not None:
                        fma = float(ma_val)
                        if direction == "long" and fma < fill_price:
                            sl_level = round(fma, 5)
                            risk_pts = round(abs(fill_price - sl_level), 5)
                        elif direction == "short" and fma > fill_price:
                            sl_level = round(fma, 5)
                            risk_pts = round(abs(fill_price - sl_level), 5)
                elif pending_signal.get("sl") is not None:
                    sl_level = round(float(pending_signal["sl"]), 5)
                    risk_pts = round(abs(fill_price - sl_level), 5)

                # Validate SL
                if sl_level is not None:
                    if direction == "long" and sl_level >= fill_price:
                        sl_level = None; risk_pts = None
                    elif direction == "short" and sl_level <= fill_price:
                        sl_level = None; risk_pts = None
                if risk_pts is not None and risk_pts <= 0:
                    sl_level = None; risk_pts = None

                # Compute TP
                tp_level = None
                tp_mode = pending_signal.get("tp_mode")
                if tp_mode == "r_multiple":
                    r = float(pending_signal.get("tp_r", 1.0) or 1.0)
                    if risk_pts and risk_pts > 0:
                        if direction == "long":
                            tp_level = round(fill_price + risk_pts * r, 5)
                        else:
                            tp_level = round(fill_price - risk_pts * r, 5)
                elif pending_signal.get("tp") is not None:
                    tp_level = round(float(pending_signal["tp"]), 5)

                # Validate TP
                if tp_level is not None:
                    if direction == "long" and tp_level <= fill_price:
                        tp_level = None
                    elif direction == "short" and tp_level >= fill_price:
                        tp_level = None

                position = PositionState(
                    has_position=True,
                    direction=direction,
                    entry_price=fill_price,
                    sl=sl_level, tp=tp_level,
                    size=self.lot_size,
                    entry_bar=absolute_bar_idx,
                )
                active_meta = {
                    "entry_bar": absolute_bar_idx,
                    "entry_time": bar["time"],
                    "entry_price": fill_price,
                    "direction": direction,
                    "sl": sl_level, "tp": tp_level,
                    "engine_sl_ma_key": pending_signal.get("engine_sl_ma_key"),
                    "engine_tp_ma_key": pending_signal.get("engine_tp_ma_key"),
                }
                ctx._position = position
                just_entered = True
                pending_signal = None

            # ═══ STEP 2: Check SL/TP on current bar H/L ═══
            if (ctx._position.has_position and active_meta
                    and not just_entered):
                pos = ctx._position
                closed = False
                close_price = None
                close_reason = None
                h = float(bar["high"])
                l = float(bar["low"])

                if pos.direction == "long":
                    if pos.sl and l <= pos.sl:
                        close_price = pos.sl
                        close_reason = "SL_HIT"
                        closed = True
                    elif pos.tp and h >= pos.tp:
                        close_price = pos.tp
                        close_reason = "TP_HIT"
                        closed = True
                elif pos.direction == "short":
                    if pos.sl and h >= pos.sl:
                        close_price = pos.sl
                        close_reason = "SL_HIT"
                        closed = True
                    elif pos.tp and l <= pos.tp:
                        close_price = pos.tp
                        close_reason = "TP_HIT"
                        closed = True

                if closed:
                    balance = self._close_trade(
                        active_meta, close_price, close_reason,
                        absolute_bar_idx, bar, balance)
                    position = PositionState()
                    ctx._position = position
                    active_meta = None

            # ═══ STEP 3: MA cross exits (skip entry bar) ═══
            if (ctx._position.has_position and active_meta
                    and not just_entered):
                ma_closed = self._check_ma_exit(
                    ctx, active_meta, bar, absolute_bar_idx, balance)
                if ma_closed is not None:
                    balance = ma_closed
                    position = PositionState()
                    ctx._position = position
                    active_meta = None

            # ═══ STEP 4: Warmup gate ═══
            if absolute_bar_idx < min_lb:
                prev_indicators = dict(ctx._indicators)
                continue

            # ═══ STEP 5: Call strategy.on_bar() ═══
            try:
                raw_signal = strategy.on_bar(ctx)
            except Exception as exc:
                print(f"[VALIDATION] on_bar error at bar "
                      f"{absolute_bar_idx}: {exc}")
                prev_indicators = dict(ctx._indicators)
                continue

            action = validate_signal(raw_signal, absolute_bar_idx)
            sig = action.get("signal")

            # ═══ STEP 6: Handle CLOSE ═══
            closed_position = False
            if ((sig == SIGNAL_CLOSE or action.get("close"))
                    and ctx._position.has_position):
                reason = action.get("close_reason", "strategy_close")
                close_px = float(bar["close"])
                if ctx._position.direction == "short" and self.spread_points > 0:
                    close_px += self.spread_points * self._point
                balance = self._close_trade(
                    active_meta, close_px, reason,
                    absolute_bar_idx, bar, balance)
                position = PositionState()
                ctx._position = position
                active_meta = None
                closed_position = True

                # Re-call for flip
                try:
                    raw2 = strategy.on_bar(ctx)
                    act2 = validate_signal(raw2, absolute_bar_idx)
                    s2 = act2.get("signal")
                    if s2 in (SIGNAL_BUY, SIGNAL_SELL):
                        pending_signal = {
                            "direction": "long" if s2 == SIGNAL_BUY else "short",
                            **{k: act2.get(k) for k in (
                                "sl", "tp", "sl_mode", "sl_pts", "sl_ma_key",
                                "sl_ma_val", "tp_mode", "tp_r",
                                "engine_sl_ma_key", "engine_tp_ma_key")},
                        }
                except Exception:
                    pass

            elif sig == SIGNAL_CLOSE_LONG:
                if (ctx._position.has_position
                        and ctx._position.direction == "long"):
                    close_px = float(bar["close"])
                    balance = self._close_trade(
                        active_meta, close_px, "strategy_close_long",
                        absolute_bar_idx, bar, balance)
                    position = PositionState()
                    ctx._position = position
                    active_meta = None
                    closed_position = True

            elif sig == SIGNAL_CLOSE_SHORT:
                if (ctx._position.has_position
                        and ctx._position.direction == "short"):
                    close_px = float(bar["close"])
                    if self.spread_points > 0:
                        close_px += self.spread_points * self._point
                    balance = self._close_trade(
                        active_meta, close_px, "strategy_close_short",
                        absolute_bar_idx, bar, balance)
                    position = PositionState()
                    ctx._position = position
                    active_meta = None
                    closed_position = True

            # ═══ STEP 7: BUY/SELL → store PENDING ═══
            if not closed_position:
                if sig in (SIGNAL_BUY, SIGNAL_SELL):
                    if not ctx._position.has_position:
                        pending_signal = {
                            "direction": "long" if sig == SIGNAL_BUY else "short",
                            **{k: action.get(k) for k in (
                                "sl", "tp", "sl_mode", "sl_pts", "sl_ma_key",
                                "sl_ma_val", "tp_mode", "tp_r",
                                "engine_sl_ma_key", "engine_tp_ma_key")},
                        }

            # ═══ STEP 8: Track equity ═══
            floating = 0.0
            if ctx._position.has_position and active_meta:
                ep = active_meta["entry_price"]
                cp = float(bar["close"])
                if ctx._position.direction == "long":
                    floating = self._compute_pnl(ep, cp, "long")
                else:
                    floating = self._compute_pnl(ep, cp, "short")

            equity = balance + floating
            if balance > peak_balance:
                peak_balance = balance
            ctx.equity = equity

            # Snapshot every N bars
            if bar_idx % max(1, total_bars // 500) == 0 or bar_idx == total_bars - 1:
                equity_curve.append({
                    "bar_index": absolute_bar_idx,
                    "timestamp": bar["time"],
                    "balance": round(balance, 2),
                    "equity": round(equity, 2),
                    "floating_pnl": round(floating, 2),
                    "trades": len(self._trades),
                })

            prev_indicators = dict(ctx._indicators)

            if bar_idx > 0 and bar_idx % report_every_bar == 0:
                pct = 65 + (bar_idx / total_bars) * 30
                self._report_progress(pct,
                    f"Bar {bar_idx}/{total_bars} | "
                    f"Trades: {len(self._trades)} | "
                    f"P&L: ${balance:.2f}")

        # Close any open position at end
        if ctx._position.has_position and active_meta:
            close_px = float(all_bars[-1]["close"])
            if ctx._position.direction == "short" and self.spread_points > 0:
                close_px += self.spread_points * self._point
            balance = self._close_trade(
                active_meta, close_px, "END_OF_DATA",
                absolute_bar_idx, all_bars[-1], balance)

        # Final equity point
        equity_curve.append({
            "bar_index": absolute_bar_idx,
            "timestamp": all_bars[-1]["time"] if all_bars else 0,
            "balance": round(balance, 2),
            "equity": round(balance, 2),
            "floating_pnl": 0.0,
            "trades": len(self._trades),
        })

        self._equity_curve = equity_curve
        print(f"[VALIDATION] Simulation done: {len(self._trades)} trades, "
              f"balance=${balance:.2f}")

    # ── Trade Helpers ────────────────────────────────────────

    def _compute_pnl(self, entry: float, exit_: float,
                     direction: str) -> float:
        """Compute PnL in account currency using symbol metrics."""
        if direction == "long":
            pts = exit_ - entry
        else:
            pts = entry - exit_

        # PnL = (points / tick_size) * tick_value * lots
        ticks_moved = pts / self._tick_size if self._tick_size > 0 else 0
        pnl = ticks_moved * self._tick_value * self.lot_size
        return round(pnl, 2)

    def _close_trade(self, meta: dict, close_price: float,
                     reason: str, bar_idx: int, bar: dict,
                     current_balance: float) -> float:
        """Record a trade and return updated balance."""
        self._trade_counter += 1
        direction = meta["direction"]
        entry_price = meta["entry_price"]

        profit = self._compute_pnl(entry_price, close_price, direction)

        # Commission
        comm = 0.0
        if self.commission_per_lot > 0:
            comm = round(-self.commission_per_lot * self.lot_size * 2, 2)

        net_pnl = round(profit + comm, 2)
        new_balance = round(current_balance + net_pnl, 2)

        bars_held = max(0, bar_idx - meta.get("entry_bar", bar_idx))

        record = {
            "trade_id": self._trade_counter,
            "symbol": self.symbol,
            "direction": direction,
            "lot_size": self.lot_size,
            "entry_price": round(entry_price, 5),
            "exit_price": round(close_price, 5),
            "entry_bar": meta.get("entry_bar", 0),
            "exit_bar": bar_idx,
            "entry_time": meta.get("entry_time", 0),
            "exit_time": bar.get("time", 0),
            "profit": profit,
            "commission": comm,
            "net_pnl": net_pnl,
            "exit_reason": reason,
            "sl": meta.get("sl"),
            "tp": meta.get("tp"),
            "bars_held": bars_held,
            "balance_after": new_balance,
        }
        self._trades.append(record)
        return new_balance

    def _check_ma_exit(self, ctx, meta: dict, bar: dict,
                       bar_idx: int, balance: float):
        """Check MA cross exits. Returns new balance if closed, else None."""
        pos = ctx._position
        if not pos.has_position:
            return None
        close_price = float(bar["close"])
        direction = pos.direction

        for ma_key_field in ("engine_tp_ma_key", "engine_sl_ma_key"):
            ma_key = meta.get(ma_key_field)
            if not ma_key:
                continue
            ma_val = ctx.indicators.get(ma_key)
            if ma_val is None:
                continue

            trigger = False
            if direction == "long" and close_price < ma_val:
                trigger = True
            elif direction == "short" and close_price > ma_val:
                trigger = True

            if trigger:
                reason = ("MA_TP_EXIT" if "tp" in ma_key_field
                          else "MA_SL_EXIT")
                exit_px = close_price
                if direction == "short" and self.spread_points > 0:
                    exit_px += self.spread_points * self._point
                new_bal = self._close_trade(
                    meta, exit_px, reason, bar_idx, bar, balance)
                return new_bal

        return None

    # ── Results Computation ──────────────────────────────────

    def _compute_results(self, total_ticks: int) -> dict:
        trades = self._trades
        n = len(trades)

        if n == 0:
            return {
                "summary": self._empty_summary(),
                "trades": [],
                "equity_curve": self._equity_curve,
                "total_ticks": total_ticks,
                "total_bars": len(self._equity_curve),
            }

        profits = [t["net_pnl"] for t in trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]
        bars_list = [t.get("bars_held", 0) for t in trades]

        gp = round(sum(wins), 2)
        gl = round(sum(losses), 2)
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
                dp = min((d / peak) * 100, 100.0)
                dd_pct = max(dd_pct, dp)

        # Sharpe
        mean = net / n
        var = sum((p - mean) ** 2 for p in profits) / (n - 1) if n > 1 else 0
        std = math.sqrt(var) if var > 0 else 0
        sharpe = round(mean / std * math.sqrt(252), 2) if std > 0 else 0

        # Sortino
        down = [p for p in profits if p < 0]
        if down and len(down) > 1:
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
            "equity_curve": self._equity_curve,
            "total_ticks": total_ticks,
            "total_bars": len(self._equity_curve),
        }

    def _empty_summary(self) -> dict:
        return {
            "total_trades": 0, "wins": 0, "losses": 0,
            "gross_profit": 0, "gross_loss": 0, "net_pnl": 0,
            "win_rate": 0, "profit_factor": 0, "expectancy": 0,
            "avg_trade": 0, "avg_winner": 0, "avg_loser": 0,
            "best_trade": 0, "worst_trade": 0,
            "max_drawdown_pct": 0, "max_drawdown_usd": 0,
            "recovery_factor": 0, "sharpe_estimate": 0,
            "sortino_estimate": 0, "avg_bars_held": 0,
            "max_consec_wins": 0, "max_consec_losses": 0,
        }