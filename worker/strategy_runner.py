"""
JINNI GRID — Strategy Runner
Orchestrates: strategy load → tick fetch → bar generation → strategy execution loop.
Reports status back to Mother Server.
"""
from __future__ import annotations
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from worker.range_bar_engine import RangeBarEngine
from worker.strategy_loader import load_strategy_from_source
from worker.strategy_context import StrategyContext, PositionState
from worker import mt5_connector

VALID_SIGNALS = {"BUY", "SELL", "HOLD", "CLOSE", None}


class StrategyRunner:
    """
    Full lifecycle runner for a single deployment on a worker.

    Phases:
        1. load strategy from source
        2. init MT5
        3. fetch historical ticks → generate initial bars
        4. warm up strategy (run on_bar for lookback bars without acting)
        5. live loop: stream ticks → bar engine → on_bar → handle signal
    """

    def __init__(self, deployment_config: dict, status_callback=None):
        self.config = deployment_config
        self._status_callback = status_callback

        # Extracted config
        self.deployment_id: str = deployment_config["deployment_id"]
        self.strategy_id: str = deployment_config["strategy_id"]
        self.class_name: str = deployment_config.get("strategy_class_name", "")
        self.source_code: str = deployment_config.get("strategy_file_content", "")
        self.symbol: str = deployment_config["symbol"]
        self.tick_lookback_value: int = deployment_config.get("tick_lookback_value", 30)
        self.tick_lookback_unit: str = deployment_config.get("tick_lookback_unit", "minutes")
        self.bar_size_points: float = deployment_config["bar_size_points"]
        self.max_bars: int = deployment_config.get("max_bars_in_memory", 500)
        self.lot_size: float = deployment_config.get("lot_size", 0.01)
        self.strategy_parameters: dict = deployment_config.get("strategy_parameters", {})

        # Runtime state
        self._strategy = None
        self._ctx: Optional[StrategyContext] = None
        self._bar_engine: Optional[RangeBarEngine] = None
        self._runner_state: str = "idle"
        self._last_signal: Optional[dict] = None
        self._last_error: Optional[str] = None
        self._started_at: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._bar_index: int = 0

    # ── Status Reporting ────────────────────────────────────────

    def _report_status(self):
        """Push current runner status via callback."""
        if not self._status_callback:
            return
        status = {
            "deployment_id": self.deployment_id,
            "strategy_id": self.strategy_id,
            "strategy_name": getattr(self._strategy, "name", None) if self._strategy else None,
            "symbol": self.symbol,
            "runner_state": self._runner_state,
            "bar_size_points": self.bar_size_points,
            "max_bars_in_memory": self.max_bars,
            "current_bars_count": self._bar_engine.current_bars_count if self._bar_engine else 0,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._status_callback(status)
        except Exception as e:
            print(f"[RUNNER] Status report failed: {e}")

    def _set_state(self, state: str, error: str = None):
        self._runner_state = state
        if error:
            self._last_error = error
        print(f"[RUNNER] {self.deployment_id} → {state}" + (f" (error: {error})" if error else ""))
        self._report_status()

    # ── New bar callback from engine ────────────────────────────

    def _on_new_bar(self, bar: dict):
        """Called by RangeBarEngine when a bar completes."""
        if self._stop_event.is_set():
            return
        if self._strategy is None or self._ctx is None:
            return

        # Update context with current bars from engine
        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        self._ctx.index = len(bars_list) - 1
        self._bar_index = self._ctx.index

        # Skip if below min_lookback
        min_lb = getattr(self._strategy, "min_lookback", 0) or 0
        if self._ctx.index < min_lb:
            return

        try:
            signal = self._strategy.on_bar(self._ctx)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[RUNNER] on_bar() error: {e}\n{tb}")
            self._set_state("failed", f"on_bar error: {e}")
            self._stop_event.set()
            return

        self._handle_signal(signal)

    def _handle_signal(self, signal: Optional[dict]):
        """Process signal returned by strategy."""
        if signal is None:
            return

        action = signal.get("signal")
        if action not in VALID_SIGNALS:
            print(f"[RUNNER] Invalid signal: {action}")
            return

        if action == "HOLD":
            # Check for dynamic SL/TP updates
            if "update_sl" in signal or "update_tp" in signal:
                self._last_signal = signal
                print(f"[RUNNER] SL/TP update: {signal}")
            return

        # Real signal detected
        self._last_signal = signal
        print(f"[RUNNER] Signal: {action} | symbol={self.symbol} | details={signal}")

        # Execution layer does not exist yet — log and report
        if action in ("BUY", "SELL"):
            print(f"[RUNNER] {action} signal detected. Execution layer not implemented — signal logged only.")
        elif action == "CLOSE":
            print(f"[RUNNER] CLOSE signal detected. Execution layer not implemented — signal logged only.")

        self._report_status()

    # ── Main Run Sequence ───────────────────────────────────────

    def start(self):
        """Start runner in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the runner to stop."""
        self._stop_event.set()
        self._set_state("stopped")
        if self._thread:
            self._thread.join(timeout=10)

    def _run(self):
        """Full lifecycle: load → ticks → bars → live loop."""
        self._started_at = datetime.now(timezone.utc).isoformat()

        # ── Phase 1: Load Strategy ──────────────────────────────
        self._set_state("loading_strategy")
        strategy_instance, load_error = load_strategy_from_source(
            self.source_code, self.class_name, self.strategy_id
        )
        if load_error:
            self._set_state("failed", f"Strategy load failed: {load_error}")
            return
        self._strategy = strategy_instance

        # Validate and apply parameters
        params = self._strategy.validate_parameters(self.strategy_parameters)

        # Initialize context
        self._ctx = StrategyContext(bars=[], params=params)
        try:
            self._strategy.on_init(self._ctx)
        except Exception as e:
            self._set_state("failed", f"on_init() failed: {e}")
            return

        # ── Phase 2: Init MT5 ──────────────────────────────────
        ok, msg = mt5_connector.init_mt5()
        if not ok:
            self._set_state("failed", f"MT5 init failed: {msg}")
            return

        # ── Phase 3: Fetch Historical Ticks ────────────────────
        self._set_state("fetching_ticks")
        ticks, tick_err = mt5_connector.fetch_historical_ticks(
            self.symbol, self.tick_lookback_value, self.tick_lookback_unit
        )
        if ticks is None:
            self._set_state("failed", f"Tick fetch failed: {tick_err}")
            mt5_connector.shutdown_mt5()
            return

        if len(ticks) == 0:
            self._set_state("failed", "No ticks returned from MT5.")
            mt5_connector.shutdown_mt5()
            return

        print(f"[RUNNER] Fetched {len(ticks)} historical ticks for {self.symbol}")

        # ── Phase 4: Generate Initial Bars ─────────────────────
        self._set_state("generating_initial_bars")

        # Create bar engine WITHOUT the live callback first
        # (we don't want on_bar firing during warmup)
        self._bar_engine = RangeBarEngine(
            bar_size_points=self.bar_size_points,
            max_bars=self.max_bars,
            on_bar=None,  # no callback during initial generation
        )

        for tick in ticks:
            self._bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])

        initial_count = self._bar_engine.current_bars_count
        print(f"[RUNNER] Initial bars generated: {initial_count} (from {len(ticks)} ticks)")

        if initial_count == 0:
            self._set_state("failed", "No bars generated from historical ticks. Check bar_size_points.")
            mt5_connector.shutdown_mt5()
            return

        # ── Phase 5: Warm Up Strategy ──────────────────────────
        self._set_state("warming_up")

        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list

        min_lb = getattr(self._strategy, "min_lookback", 0) or 0

        for i in range(len(bars_list)):
            if self._stop_event.is_set():
                return
            self._ctx.index = i
            self._bar_index = i
            if i < min_lb:
                continue
            try:
                signal = self._strategy.on_bar(self._ctx)
                # During warmup we log signals but don't act
                if signal and signal.get("signal") in ("BUY", "SELL", "CLOSE"):
                    print(f"[RUNNER] Warmup signal at bar {i}: {signal.get('signal')} (not acted upon)")
            except Exception as e:
                print(f"[RUNNER] Warmup on_bar error at bar {i}: {e}")

        print(f"[RUNNER] Warmup complete. Strategy ready.")

        # ── Phase 6: Live Tick Loop ────────────────────────────
        self._set_state("running")

        # Now attach the live callback
        self._bar_engine._on_bar = self._on_new_bar

        try:
            for tick in mt5_connector.stream_live_ticks(self.symbol):
                if self._stop_event.is_set():
                    break
                self._bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])
        except Exception as e:
            if not self._stop_event.is_set():
                tb = traceback.format_exc()
                print(f"[RUNNER] Live loop error: {e}\n{tb}")
                self._set_state("failed", f"Live loop error: {e}")
        finally:
            mt5_connector.shutdown_mt5()
            if not self._stop_event.is_set():
                self._set_state("stopped")