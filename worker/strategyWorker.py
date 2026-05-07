"""
JINNI GRID — Combined Worker Runtime
worker/strategyWorker.py

"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import threading
import time
import traceback
import types
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple


# =============================================================================
# Strategy Base Class
# =============================================================================

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_CLOSE = "CLOSE"
VALID_SIGNALS = {SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE, None}


class BaseStrategy(ABC):
    strategy_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0"
    min_lookback: int = 0

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": self.name or self.strategy_id,
            "description": self.description or "",
            "version": self.version,
            "min_lookback": self.min_lookback,
            "parameters": self.get_parameter_schema(),
        }

    def get_parameter_schema(self) -> Dict[str, Any]:
        return getattr(self, "parameters", {})

    def get_default_parameters(self) -> Dict[str, Any]:
        schema = self.get_parameter_schema()
        defaults = {}

        for key, spec in schema.items():
            if isinstance(spec, dict) and "default" in spec:
                defaults[key] = spec["default"]

        return defaults

    def validate_parameters(self, raw_params: Dict[str, Any]) -> Dict[str, Any]:
        params = dict(self.get_default_parameters())

        for key, value in (raw_params or {}).items():
            params[key] = value

        return params

    def build_indicators(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def on_init(self, ctx: Any) -> None:
        pass

    def on_end(self, ctx: Any) -> None:
        pass

    @abstractmethod
    def on_bar(self, ctx: Any) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Strategy must implement on_bar()")


# =============================================================================
# Strategy Context
# =============================================================================

@dataclass
class PositionState:
    """Read-only position snapshot passed to strategies."""

    has_position: bool = False
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    size: Optional[float] = None
    entry_bar: Optional[int] = None


class StrategyContext:
    """
    The ctx object strategies receive in on_bar(ctx).
    Read-only except ctx.state, which is a mutable dict persisting across bars.
    """

    def __init__(
        self,
        bars: list,
        params: dict,
        position: Optional[PositionState] = None,
    ):
        self._bars = bars
        self._params = params
        self._position = position or PositionState()
        self._index: int = 0
        self._trades: list = []
        self._equity: float = 0.0
        self._balance: float = 0.0
        self._indicators: dict = {}
        self._ind_series: dict = {}
        self.state: dict = {}

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, val: int):
        self._index = val

    @property
    def bar(self) -> dict:
        if 0 <= self._index < len(self._bars):
            return self._bars[self._index]
        return {}

    @property
    def bars(self) -> list:
        return self._bars

    @property
    def indicators(self) -> dict:
        return self._indicators

    @property
    def ind_series(self) -> dict:
        return self._ind_series

    @property
    def position(self) -> PositionState:
        return self._position

    @position.setter
    def position(self, val: PositionState):
        self._position = val

    @property
    def params(self) -> dict:
        return self._params

    @property
    def trades(self) -> list:
        return self._trades

    @property
    def equity(self) -> float:
        return self._equity

    @equity.setter
    def equity(self, val: float):
        self._equity = val

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, val: float):
        self._balance = val


# =============================================================================
# Range Bar Engine
# =============================================================================

def _make_bar(
    time_: int,
    open_: float,
    high_: float,
    low_: float,
    close_: float,
    volume_: float,
) -> dict:
    return {
        "time": int(time_),
        "open": round(open_, 5),
        "high": round(high_, 5),
        "low": round(low_, 5),
        "close": round(close_, 5),
        "volume": round(volume_, 2),
    }


class RangeBarEngine:
    def __init__(
        self,
        bar_size_points: float,
        max_bars: int = 500,
        on_bar: Optional[Callable[[dict], None]] = None,
    ):
        self.range_size: float = float(bar_size_points)
        self.max_bars: int = max_bars
        self._on_bar: Optional[Callable[[dict], None]] = on_bar

        self.trend: int = 0
        self.bar: Optional[dict] = None

        self.bars: deque = deque(maxlen=max_bars)
        self._last_emitted_ts: Optional[int] = None

        self.total_ticks: int = 0
        self.total_bars_emitted: int = 0

    @property
    def current_bars_count(self) -> int:
        return len(self.bars)

    def _emit(self, bar_dict: dict) -> None:
        ts = int(bar_dict["time"])

        if self._last_emitted_ts is not None and ts <= self._last_emitted_ts:
            ts = self._last_emitted_ts + 1

        bar_dict["time"] = ts
        self._last_emitted_ts = ts

        self.bars.append(bar_dict)
        self.total_bars_emitted += 1

        if self._on_bar:
            self._on_bar(bar_dict)

    def _start_bar(self, ts: int, price: float, volume: float) -> None:
        self.bar = {
            "time": ts,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
        }

    def process_tick(self, ts: int, price: float, volume: float = 0.0) -> None:
        self.total_ticks += 1

        if self.bar is None:
            self._start_bar(ts, price, volume)
            return

        p = price
        rs = self.range_size

        self.bar["volume"] += volume

        while True:
            o = self.bar["open"]

            if self.trend == 0:
                up_target = o + rs
                down_target = o - rs

                if p >= up_target:
                    self.bar["high"] = max(self.bar["high"], up_target)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = up_target
                    self._emit(_make_bar(
                        self.bar["time"], self.bar["open"],
                        self.bar["high"], self.bar["low"],
                        self.bar["close"], self.bar["volume"],
                    ))
                    self.trend = 1
                    new_open = up_target
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                if p <= down_target:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], down_target)
                    self.bar["close"] = down_target
                    self._emit(_make_bar(
                        self.bar["time"], self.bar["open"],
                        self.bar["high"], self.bar["low"],
                        self.bar["close"], self.bar["volume"],
                    ))
                    self.trend = -1
                    new_open = down_target
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break

            if self.trend == 1:
                cont_target = o + rs
                rev_target = o - (2 * rs)

                if p >= cont_target:
                    self.bar["high"] = max(self.bar["high"], cont_target)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = cont_target
                    self._emit(_make_bar(
                        self.bar["time"], self.bar["open"],
                        self.bar["high"], self.bar["low"],
                        self.bar["close"], self.bar["volume"],
                    ))
                    new_open = cont_target
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                if p <= rev_target:
                    rev_open = o - rs
                    rev_close = o - (2 * rs)
                    high_ = max(self.bar["high"], o)
                    low_ = min(self.bar["low"], rev_close)
                    self._emit(_make_bar(
                        self.bar["time"], rev_open, high_,
                        low_, rev_close, self.bar["volume"],
                    ))
                    self.trend = -1
                    new_open = rev_close
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break

            if self.trend == -1:
                cont_target = o - rs
                rev_target = o + (2 * rs)

                if p <= cont_target:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], cont_target)
                    self.bar["close"] = cont_target
                    self._emit(_make_bar(
                        self.bar["time"], self.bar["open"],
                        self.bar["high"], self.bar["low"],
                        self.bar["close"], self.bar["volume"],
                    ))
                    new_open = cont_target
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                if p >= rev_target:
                    rev_open = o + rs
                    rev_close = o + (2 * rs)
                    high_ = max(self.bar["high"], rev_close)
                    low_ = min(self.bar["low"], o)
                    self._emit(_make_bar(
                        self.bar["time"], rev_open, high_,
                        low_, rev_close, self.bar["volume"],
                    ))
                    self.trend = 1
                    new_open = rev_close
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break

    def reset(self) -> None:
        self.trend = 0
        self.bar = None
        self.bars.clear()
        self._last_emitted_ts = None
        self.total_ticks = 0
        self.total_bars_emitted = 0


# =============================================================================
# MT5 Tick Normalizer
# =============================================================================

def _tick_field(raw, field: str, default: float = 0.0) -> float:
    """
    Safely read a numeric field from an MT5 tick.

    MT5's copy_ticks_range / copy_ticks_from return numpy structured arrays.
    Each row is a numpy.void — fields must be accessed via raw['field'],
    NOT raw.field (which raises AttributeError on numpy.void).
    """
    try:
        val = float(raw[field])
        return val
    except (KeyError, IndexError, TypeError, ValueError):
        pass

    try:
        val = float(getattr(raw, field))
        return val
    except (AttributeError, TypeError, ValueError):
        pass

    return default


def normalize_tick(raw) -> Optional[dict]:
    """
    Convert a raw MT5 tick (numpy.void or object) into a clean dict.

    Returns:
        {"ts": int, "time_msc": int, "price": float, "bid": float,
         "ask": float, "last": float, "volume": float}
        or None if the tick has no usable price.
    """
    ts_val = _tick_field(raw, "time", -1.0)
    if ts_val < 0:
        return None
    ts = int(ts_val)

    time_msc_val = _tick_field(raw, "time_msc", -1.0)
    time_msc = int(time_msc_val) if time_msc_val >= 0 else ts * 1000

    bid = _tick_field(raw, "bid", 0.0)
    ask = _tick_field(raw, "ask", 0.0)
    last = _tick_field(raw, "last", 0.0)
    volume = _tick_field(raw, "volume", 0.0)

    price = bid if bid > 0 else (last if last > 0 else ask)

    if price <= 0:
        return None

    return {
        "ts": ts,
        "time_msc": time_msc,
        "price": price,
        "bid": bid,
        "ask": ask,
        "last": last,
        "volume": volume,
    }


# =============================================================================
# MT5 Connector
# =============================================================================

def _import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


def init_mt5() -> Tuple[bool, str]:
    mt5 = _import_mt5()

    if mt5 is None:
        return False, "MetaTrader5 package not installed. pip install MetaTrader5"

    if not mt5.initialize():
        err = mt5.last_error()
        return False, f"MT5 initialize() failed: {err}"

    info = mt5.terminal_info()

    if info is None:
        return False, "MT5 terminal_info() returned None."

    account = mt5.account_info()
    acct_str = ""

    if account:
        acct_str = f" | account={account.login} broker={account.company}"

    print(f"[MT5] Connected: {info.name}{acct_str}")
    return True, "ok"


def shutdown_mt5() -> None:
    mt5 = _import_mt5()

    if mt5:
        mt5.shutdown()


def get_mt5_account_info() -> Optional[dict]:
    """
    Query MT5 for current account info.
    Returns dict with login, broker, server, balance, equity
    or None if MT5 is not connected.
    """
    mt5 = _import_mt5()
    if mt5 is None:
        return None

    account = mt5.account_info()
    if account is None:
        return None

    terminal = mt5.terminal_info()

    return {
        "login": str(account.login),
        "broker": str(account.company) if account.company else None,
        "server": str(account.server) if account.server else None,
        "balance": float(account.balance),
        "equity": float(account.equity),
        "terminal": str(terminal.name) if terminal else None,
    }


def fetch_historical_ticks(
    symbol: str,
    lookback_value: int,
    lookback_unit: str,
) -> Tuple[Optional[list], str]:
    mt5 = _import_mt5()

    if mt5 is None:
        return None, "MetaTrader5 package not installed."

    now = datetime.now(timezone.utc)

    if lookback_unit == "minutes":
        from_time = now - timedelta(minutes=lookback_value)
    elif lookback_unit == "hours":
        from_time = now - timedelta(hours=lookback_value)
    elif lookback_unit == "days":
        from_time = now - timedelta(days=lookback_value)
    else:
        return None, f"Invalid lookback_unit: {lookback_unit}"

    symbol_info = mt5.symbol_info(symbol)

    if symbol_info is None:
        return None, f"Symbol '{symbol}' not found in MT5."

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            return None, f"Failed to enable symbol '{symbol}' in MT5."

    print(
        f"[MT5] Fetching ticks: {symbol} "
        f"from {from_time.isoformat()} to {now.isoformat()}"
    )

    ticks = mt5.copy_ticks_range(symbol, from_time, now, mt5.COPY_TICKS_ALL)

    if ticks is None or len(ticks) == 0:
        err = mt5.last_error()
        return None, f"No ticks returned for {symbol}. MT5 error: {err}"

    result = []
    skipped = 0

    try:
        for raw_tick in ticks:
            normalized = normalize_tick(raw_tick)
            if normalized is None:
                skipped += 1
                continue
            result.append({
                "ts": normalized["ts"],
                "price": normalized["price"],
                "volume": normalized["volume"],
            })
    except Exception as exc:
        tb = traceback.format_exc()
        return None, (
            f"Tick processing error for {symbol}: "
            f"{type(exc).__name__}: {exc}\n{tb}"
        )

    if skipped > 0:
        print(f"[MT5] Skipped {skipped} ticks with no valid price for {symbol}")

    if len(result) == 0:
        return None, (
            f"All {len(ticks)} ticks for {symbol} had no valid price "
            f"(bid/ask/last all <= 0). Skipped: {skipped}"
        )

    print(f"[MT5] Got {len(result)} usable ticks for {symbol} (skipped {skipped})")
    return result, "ok"


def stream_live_ticks(symbol: str, poll_interval: float = 0.05):
    mt5 = _import_mt5()

    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed.")

    cursor_time = datetime.now(timezone.utc)
    last_tick_msc = 0

    while True:
        ticks = mt5.copy_ticks_from(symbol, cursor_time, 1000, mt5.COPY_TICKS_ALL)

        if ticks is not None and len(ticks) > 0:
            for raw_tick in ticks:
                normalized = normalize_tick(raw_tick)

                if normalized is None:
                    continue

                if normalized["time_msc"] <= last_tick_msc:
                    continue

                last_tick_msc = normalized["time_msc"]

                yield {
                    "ts": normalized["ts"],
                    "price": normalized["price"],
                    "volume": normalized["volume"],
                }

            last_ts = _tick_field(ticks[-1], "time", 0.0)
            if last_ts > 0:
                cursor_time = datetime.fromtimestamp(
                    int(last_ts), tz=timezone.utc
                )

        time.sleep(poll_interval)


class _MT5ConnectorFacade:
    init_mt5 = staticmethod(init_mt5)
    shutdown_mt5 = staticmethod(shutdown_mt5)
    fetch_historical_ticks = staticmethod(fetch_historical_ticks)
    stream_live_ticks = staticmethod(stream_live_ticks)
    get_mt5_account_info = staticmethod(get_mt5_account_info)


mt5_connector = _MT5ConnectorFacade()


# =============================================================================
# Strategy Loader
# =============================================================================

def load_strategy_from_source(
    source_code: str,
    class_name: str,
    strategy_id: str,
) -> Tuple[Optional[object], Optional[str]]:
    try:
        _ensure_base_importable()
    except Exception as exc:
        return None, f"Failed to prepare base imports: {exc}"

    module_name = f"jinni_strategy_{strategy_id}"

    try:
        tmp_dir = tempfile.mkdtemp(prefix="jinni_strat_")
        tmp_path = os.path.join(tmp_dir, f"{module_name}.py")

        with open(tmp_path, "w", encoding="utf-8") as file:
            file.write(source_code)

        spec = importlib.util.spec_from_file_location(module_name, tmp_path)

        if spec is None or spec.loader is None:
            return None, "Failed to create module spec."

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        klass = getattr(module, class_name, None)

        if klass is None:
            available = [key for key in dir(module) if not key.startswith("_")]
            return None, f"Class '{class_name}' not found. Available: {available}"

        instance = klass()

        if not hasattr(instance, "on_bar"):
            return None, f"Class '{class_name}' has no on_bar() method."

        print(f"[LOADER] Strategy loaded: {class_name} (id={strategy_id})")
        return instance, None

    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[LOADER] Failed to load strategy: {exc}\n{tb}")
        return None, f"{type(exc).__name__}: {exc}"


def _ensure_base_importable():
    current_module = sys.modules[__name__]

    sys.modules["base_strategy"] = current_module
    sys.modules["worker.base_strategy"] = current_module

    if "backend" not in sys.modules:
        backend_module = types.ModuleType("backend")
        backend_module.__path__ = []
        sys.modules["backend"] = backend_module

    if "backend.strategies" not in sys.modules:
        strategies_module = types.ModuleType("backend.strategies")
        strategies_module.__path__ = []
        sys.modules["backend.strategies"] = strategies_module

    sys.modules["backend.strategies.base"] = current_module


# =============================================================================
# Strategy Runner
# =============================================================================

class StrategyRunner:
    """
    Full lifecycle runner for a single deployment on a worker.

    Phases:
        1. load strategy from source
        2. init MT5
        3. fetch historical ticks and generate initial bars
        4. warm up strategy
        5. live loop
    """

    def __init__(self, deployment_config: dict, status_callback=None):
        self.config = deployment_config
        self._status_callback = status_callback

        self.deployment_id: str = deployment_config["deployment_id"]
        self.strategy_id: str = deployment_config["strategy_id"]
        self.class_name: str = deployment_config.get("strategy_class_name", "")
        self.source_code: str = deployment_config.get("strategy_file_content", "")
        self.symbol: str = deployment_config["symbol"]
        self.tick_lookback_value: int = deployment_config.get("tick_lookback_value", 30)
        self.tick_lookback_unit: str = deployment_config.get(
            "tick_lookback_unit",
            "minutes",
        )
        self.bar_size_points: float = deployment_config["bar_size_points"]
        self.max_bars: int = deployment_config.get("max_bars_in_memory", 500)
        self.lot_size: float = deployment_config.get("lot_size", 0.01)
        self.strategy_parameters: dict = deployment_config.get(
            "strategy_parameters",
            {},
        )

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

        # ── MT5 account info (populated after init) ─────────
        self._mt5_state: Optional[str] = None
        self._mt5_broker: Optional[str] = None
        self._mt5_account_id: Optional[str] = None
        self._mt5_server: Optional[str] = None
        self._mt5_balance: Optional[float] = None
        self._mt5_equity: Optional[float] = None

        # ── Pipeline counters ───────────────────────────────
        self._total_ticks_ingested: int = 0
        self._total_bars_produced: int = 0
        self._on_bar_call_count: int = 0
        self._signal_count: int = 0
        self._warmup_signal_count: int = 0
        self._last_bar_time: Optional[int] = None
        self._current_price: Optional[float] = None
        self._pipeline_log_interval: int = 5000  # log every N ticks

    # -------------------------------------------------------------------------
    # Diagnostics — read by worker_agent for heartbeat
    # -------------------------------------------------------------------------

    def get_diagnostics(self) -> dict:
        """Return a snapshot of all runner state for the heartbeat payload."""
        return {
            "runner_state": self._runner_state,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "mt5_state": self._mt5_state,
            "broker": self._mt5_broker,
            "account_id": self._mt5_account_id,
            "mt5_server": self._mt5_server,
            "mt5_balance": self._mt5_balance,
            "mt5_equity": self._mt5_equity,
            "total_ticks": self._total_ticks_ingested,
            "total_bars": self._total_bars_produced,
            "current_bars_in_memory": (
                self._bar_engine.current_bars_count
                if self._bar_engine else 0
            ),
            "on_bar_calls": self._on_bar_call_count,
            "signal_count": self._signal_count,
            "warmup_signals": self._warmup_signal_count,
            "last_bar_time": self._last_bar_time,
            "current_price": self._current_price,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
        }

    # -------------------------------------------------------------------------
    # Pipeline Logging
    # -------------------------------------------------------------------------

    def _log_pipeline(self, context: str = ""):
        """Print pipeline status to console."""
        ctx_str = f" [{context}]" if context else ""
        print(
            f"[PIPELINE]{ctx_str} deployment={self.deployment_id} | "
            f"ticks={self._total_ticks_ingested} "
            f"bars={self._total_bars_produced} "
            f"on_bar_calls={self._on_bar_call_count} "
            f"signals={self._signal_count} "
            f"price={self._current_price} "
            f"state={self._runner_state}"
        )

    # -------------------------------------------------------------------------
    # Status Reporting
    # -------------------------------------------------------------------------

    def _report_status(self):
        if not self._status_callback:
            return

        status = {
            "deployment_id": self.deployment_id,
            "strategy_id": self.strategy_id,
            "strategy_name": getattr(self._strategy, "name", None)
            if self._strategy
            else None,
            "symbol": self.symbol,
            "runner_state": self._runner_state,
            "bar_size_points": self.bar_size_points,
            "max_bars_in_memory": self.max_bars,
            "current_bars_count": self._bar_engine.current_bars_count
            if self._bar_engine
            else 0,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        for attempt in range(3):
            try:
                self._status_callback(status)
                return
            except Exception as exc:
                print(
                    f"[RUNNER] Status report attempt {attempt + 1}/3 failed: {exc}"
                )
                if attempt < 2:
                    time.sleep(1.0)

        print(
            f"[RUNNER] WARNING: Status report FAILED after 3 attempts | "
            f"deployment={self.deployment_id} state={self._runner_state}"
        )

    def _set_state(self, state: str, error: str = None):
        self._runner_state = state

        if error:
            self._last_error = error

        print(
            f"[RUNNER] {self.deployment_id} → {state}"
            + (f" (error: {error})" if error else "")
        )

        self._report_status()

    # -------------------------------------------------------------------------
    # MT5 Info Capture
    # -------------------------------------------------------------------------

    def _capture_mt5_info(self):
        """Query MT5 for account info and store it locally."""
        info = mt5_connector.get_mt5_account_info()
        if info:
            self._mt5_state = "connected"
            self._mt5_broker = info.get("broker")
            self._mt5_account_id = info.get("login")
            self._mt5_server = info.get("server")
            self._mt5_balance = info.get("balance")
            self._mt5_equity = info.get("equity")
            print(
                f"[RUNNER] MT5 info captured: broker={self._mt5_broker} "
                f"account={self._mt5_account_id} server={self._mt5_server} "
                f"balance={self._mt5_balance}"
            )
        else:
            self._mt5_state = "connected_no_account"
            print("[RUNNER] MT5 connected but account_info() returned None")

    # -------------------------------------------------------------------------
    # Bar Callback
    # -------------------------------------------------------------------------

    def _on_new_bar(self, bar: dict):
        """Called by RangeBarEngine when a bar completes."""
        self._total_bars_produced += 1
        self._last_bar_time = bar.get("time")

        if self._stop_event.is_set():
            return

        if self._strategy is None or self._ctx is None:
            return

        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        self._ctx.index = len(bars_list) - 1
        self._bar_index = self._ctx.index

        min_lb = getattr(self._strategy, "min_lookback", 0) or 0

        if self._ctx.index < min_lb:
            return

        self._on_bar_call_count += 1

        try:
            signal = self._strategy.on_bar(self._ctx)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[RUNNER] on_bar() error: {exc}\n{tb}")
            self._set_state("failed", f"on_bar error: {type(exc).__name__}: {exc}")
            self._stop_event.set()
            return

        self._handle_signal(signal)

        # Log every 50 bars during live
        if self._on_bar_call_count % 50 == 0:
            self._log_pipeline("LIVE_BAR")

    def _handle_signal(self, signal: Optional[dict]):
        if signal is None:
            return

        action = signal.get("signal")

        if action not in VALID_SIGNALS:
            print(f"[RUNNER] Invalid signal: {action}")
            return

        if action == SIGNAL_HOLD:
            if "update_sl" in signal or "update_tp" in signal:
                self._last_signal = signal
                print(f"[RUNNER] SL/TP update: {signal}")
            return

        self._last_signal = signal

        if action in (SIGNAL_BUY, SIGNAL_SELL, SIGNAL_CLOSE):
            self._signal_count += 1

        print(
            f"[RUNNER] Signal #{self._signal_count}: {action} | "
            f"symbol={self.symbol} | bar_index={self._bar_index} | "
            f"details={signal}"
        )

        if action in (SIGNAL_BUY, SIGNAL_SELL):
            print(
                f"[RUNNER] *** {action} signal detected. "
                "Execution layer not implemented — signal logged only. ***"
            )
        elif action == SIGNAL_CLOSE:
            print(
                "[RUNNER] *** CLOSE signal detected. "
                "Execution layer not implemented — signal logged only. ***"
            )

        self._report_status()

    # -------------------------------------------------------------------------
    # Main Lifecycle
    # -------------------------------------------------------------------------

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._set_state("stopped")

        if self._thread:
            self._thread.join(timeout=10)

    def _run(self):
        try:
            self._run_lifecycle()
        except Exception as exc:
            tb = traceback.format_exc()
            error_msg = f"{type(exc).__name__}: {exc}"
            print(
                f"[RUNNER] FATAL unhandled exception in deployment "
                f"{self.deployment_id}:\n{tb}"
            )
            self._set_state("failed", error_msg)

            try:
                mt5_connector.shutdown_mt5()
            except Exception:
                pass

    def _run_lifecycle(self):
        self._started_at = datetime.now(timezone.utc).isoformat()

        # Phase 1: Load Strategy
        self._set_state("loading_strategy")

        strategy_instance, load_error = load_strategy_from_source(
            self.source_code,
            self.class_name,
            self.strategy_id,
        )

        if load_error:
            self._set_state("failed", f"Strategy load failed: {load_error}")
            return

        self._strategy = strategy_instance

        params = self._strategy.validate_parameters(self.strategy_parameters)

        self._ctx = StrategyContext(bars=[], params=params)

        try:
            self._strategy.on_init(self._ctx)
        except Exception as exc:
            self._set_state(
                "failed",
                f"on_init() failed: {type(exc).__name__}: {exc}",
            )
            return

        print(
            f"[RUNNER] Strategy loaded: {self.class_name} | "
            f"min_lookback={getattr(self._strategy, 'min_lookback', 0)} | "
            f"params={params}"
        )

        # Phase 2: Init MT5
        ok, msg = mt5_connector.init_mt5()

        if not ok:
            self._set_state("failed", f"MT5 init failed: {msg}")
            return

        # Capture MT5 account info immediately after init
        self._capture_mt5_info()

        # Phase 3: Fetch Historical Ticks
        self._set_state("fetching_ticks")

        ticks, tick_err = mt5_connector.fetch_historical_ticks(
            self.symbol,
            self.tick_lookback_value,
            self.tick_lookback_unit,
        )

        if ticks is None:
            self._set_state("failed", f"Tick fetch failed: {tick_err}")
            mt5_connector.shutdown_mt5()
            return

        if len(ticks) == 0:
            self._set_state("failed", "No ticks returned from MT5.")
            mt5_connector.shutdown_mt5()
            return

        self._total_ticks_ingested = len(ticks)
        self._current_price = ticks[-1]["price"]
        print(f"[RUNNER] Fetched {len(ticks)} historical ticks for {self.symbol}")

        # Phase 4: Generate Initial Bars
        self._set_state("generating_initial_bars")

        self._bar_engine = RangeBarEngine(
            bar_size_points=self.bar_size_points,
            max_bars=self.max_bars,
            on_bar=None,  # no callback during initial generation
        )

        for tick in ticks:
            self._bar_engine.process_tick(
                tick["ts"],
                tick["price"],
                tick["volume"],
            )

        initial_count = self._bar_engine.current_bars_count
        self._total_bars_produced = self._bar_engine.total_bars_emitted

        if self._bar_engine.bars:
            self._last_bar_time = self._bar_engine.bars[-1].get("time")

        print(
            f"[RUNNER] Initial bars generated: {initial_count} "
            f"(total emitted: {self._total_bars_produced}) "
            f"(from {len(ticks)} ticks, bar_size={self.bar_size_points}pt)"
        )

        if initial_count == 0:
            self._set_state(
                "failed",
                f"No bars generated from {len(ticks)} historical ticks. "
                f"bar_size_points={self.bar_size_points} may be too large "
                f"for the price range of {self.symbol}.",
            )
            mt5_connector.shutdown_mt5()
            return

        self._log_pipeline("INITIAL_BARS")

        # Phase 5: Warm Up Strategy
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

            self._on_bar_call_count += 1

            try:
                signal = self._strategy.on_bar(self._ctx)

                if signal and signal.get("signal") in (
                    SIGNAL_BUY,
                    SIGNAL_SELL,
                    SIGNAL_CLOSE,
                ):
                    self._warmup_signal_count += 1
                    print(
                        f"[RUNNER] Warmup signal #{self._warmup_signal_count} "
                        f"at bar {i}: {signal.get('signal')} (not acted upon)"
                    )
            except Exception as exc:
                print(f"[RUNNER] Warmup on_bar error at bar {i}: {exc}")

        print(
            f"[RUNNER] Warmup complete. "
            f"on_bar calls: {self._on_bar_call_count} | "
            f"warmup signals: {self._warmup_signal_count}"
        )
        self._log_pipeline("WARMUP_DONE")

        # Phase 6: Live Tick Loop
        self._set_state("running")

        self._bar_engine._on_bar = self._on_new_bar
        live_tick_count = 0

        try:
            for tick in mt5_connector.stream_live_ticks(self.symbol):
                if self._stop_event.is_set():
                    break

                self._total_ticks_ingested += 1
                self._current_price = tick["price"]
                live_tick_count += 1

                self._bar_engine.process_tick(
                    tick["ts"],
                    tick["price"],
                    tick["volume"],
                )

                # Periodic pipeline log
                if live_tick_count % self._pipeline_log_interval == 0:
                    self._log_pipeline("LIVE_TICK")

        except Exception as exc:
            if not self._stop_event.is_set():
                tb = traceback.format_exc()
                print(f"[RUNNER] Live loop error: {exc}\n{tb}")
                self._set_state(
                    "failed",
                    f"Live loop error: {type(exc).__name__}: {exc}",
                )

        finally:
            self._log_pipeline("SHUTDOWN")
            mt5_connector.shutdown_mt5()
            self._mt5_state = "disconnected"

            if not self._stop_event.is_set():
                self._set_state("stopped")