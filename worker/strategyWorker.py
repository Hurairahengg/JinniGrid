"""
JINNI GRID — Combined Worker Runtime
worker/strategyWorker.py

Uses:
  worker/indicators.py  — HMA/WMA/SMA/EMA precompute + IndicatorEngine
  worker/execution.py   — ExecutionLogger, MT5Executor, signal validation,
                           SL/TP computation, trade records, PositionState
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
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from worker.indicators import IndicatorEngine, precompute_indicator_series
from worker.execution import (
    SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE,
    SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT, VALID_SIGNALS,
    PositionState, ExecutionLogger, MT5Executor,
    validate_signal, compute_sl, compute_tp, build_trade_record,
)


# =============================================================================
# Strategy Base Class
# =============================================================================

class BaseStrategy(ABC):
    strategy_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0"
    min_lookback: int = 0

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id, "name": self.name or self.strategy_id,
            "description": self.description or "", "version": self.version,
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

class StrategyContext:
    def __init__(self, bars: list, params: dict,
                 position: Optional[PositionState] = None):
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

def _make_bar(time_: int, open_: float, high_: float, low_: float,
              close_: float, volume_: float) -> dict:
    return {
        "time": int(time_), "open": round(open_, 5), "high": round(high_, 5),
        "low": round(low_, 5), "close": round(close_, 5),
        "volume": round(volume_, 2),
    }


class RangeBarEngine:
    def __init__(self, bar_size_points: float, max_bars: int = 500,
                 on_bar: Optional[Callable[[dict], None]] = None):
        self.range_size = float(bar_size_points)
        self.max_bars = max_bars
        self._on_bar = on_bar
        self.trend = 0
        self.bar: Optional[dict] = None
        self.bars: deque = deque(maxlen=max_bars)
        self._last_emitted_ts: Optional[int] = None
        self.total_ticks = 0
        self.total_bars_emitted = 0

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
        self.bar = {"time": ts, "open": price, "high": price,
                    "low": price, "close": price, "volume": volume}

    def process_tick(self, ts: int, price: float, volume: float = 0.0) -> None:
        self.total_ticks += 1
        if self.bar is None:
            self._start_bar(ts, price, volume)
            return
        p, rs = price, self.range_size
        self.bar["volume"] += volume

        while True:
            o = self.bar["open"]
            if self.trend == 0:
                up_t, dn_t = o + rs, o - rs
                if p >= up_t:
                    self.bar["high"] = max(self.bar["high"], up_t)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = up_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.trend = 1
                    self.bar = {"time": ts, "open": up_t, "high": up_t,
                                "low": up_t, "close": up_t, "volume": 0.0}
                    continue
                if p <= dn_t:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], dn_t)
                    self.bar["close"] = dn_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.trend = -1
                    self.bar = {"time": ts, "open": dn_t, "high": dn_t,
                                "low": dn_t, "close": dn_t, "volume": 0.0}
                    continue
                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break
            if self.trend == 1:
                cont_t, rev_t = o + rs, o - (2 * rs)
                if p >= cont_t:
                    self.bar["high"] = max(self.bar["high"], cont_t)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = cont_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.bar = {"time": ts, "open": cont_t, "high": cont_t,
                                "low": cont_t, "close": cont_t, "volume": 0.0}
                    continue
                if p <= rev_t:
                    ro, rc = o - rs, o - (2 * rs)
                    h_ = max(self.bar["high"], o)
                    l_ = min(self.bar["low"], rc)
                    self._emit(_make_bar(self.bar["time"], ro, h_, l_, rc,
                               self.bar["volume"]))
                    self.trend = -1
                    self.bar = {"time": ts, "open": rc, "high": rc,
                                "low": rc, "close": rc, "volume": 0.0}
                    continue
                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break
            if self.trend == -1:
                cont_t, rev_t = o - rs, o + (2 * rs)
                if p <= cont_t:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], cont_t)
                    self.bar["close"] = cont_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.bar = {"time": ts, "open": cont_t, "high": cont_t,
                                "low": cont_t, "close": cont_t, "volume": 0.0}
                    continue
                if p >= rev_t:
                    ro, rc = o + rs, o + (2 * rs)
                    h_ = max(self.bar["high"], rc)
                    l_ = min(self.bar["low"], o)
                    self._emit(_make_bar(self.bar["time"], ro, h_, l_, rc,
                               self.bar["volume"]))
                    self.trend = 1
                    self.bar = {"time": ts, "open": rc, "high": rc,
                                "low": rc, "close": rc, "volume": 0.0}
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
# MT5 Tick Normalizer + Connector
# =============================================================================

def _tick_field(raw, field: str, default: float = 0.0) -> float:
    try:
        return float(raw[field])
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    try:
        return float(getattr(raw, field))
    except (AttributeError, TypeError, ValueError):
        pass
    return default


def normalize_tick(raw) -> Optional[dict]:
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
    return {"ts": ts, "time_msc": time_msc, "price": price,
            "bid": bid, "ask": ask, "last": last, "volume": volume}


def _import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


def init_mt5() -> Tuple[bool, str]:
    mt5 = _import_mt5()
    if mt5 is None:
        return False, "MetaTrader5 package not installed."
    if not mt5.initialize():
        return False, f"MT5 initialize() failed: {mt5.last_error()}"
    info = mt5.terminal_info()
    if info is None:
        return False, "MT5 terminal_info() returned None."
    account = mt5.account_info()
    acct_str = f" | account={account.login} broker={account.company}" if account else ""
    print(f"[MT5] Connected: {info.name}{acct_str}")
    return True, "ok"


def shutdown_mt5() -> None:
    mt5 = _import_mt5()
    if mt5:
        mt5.shutdown()


def get_mt5_account_info() -> Optional[dict]:
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


def fetch_historical_ticks(symbol, lookback_value, lookback_unit):
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
    print(f"[MT5] Fetching ticks: {symbol} from {from_time.isoformat()}")
    ticks = mt5.copy_ticks_range(symbol, from_time, now, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        return None, f"No ticks for {symbol}. MT5 error: {mt5.last_error()}"
    result, skipped = [], 0
    for raw_tick in ticks:
        n = normalize_tick(raw_tick)
        if n is None:
            skipped += 1
            continue
        result.append({"ts": n["ts"], "price": n["price"], "volume": n["volume"]})
    if not result:
        return None, f"All {len(ticks)} ticks had no valid price."
    print(f"[MT5] Got {len(result)} ticks for {symbol} (skipped {skipped})")
    return result, "ok"


def stream_live_ticks(symbol, poll_interval=0.05):
    mt5 = _import_mt5()
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed.")
    cursor_time = datetime.now(timezone.utc)
    last_tick_msc = 0
    while True:
        ticks = mt5.copy_ticks_from(symbol, cursor_time, 1000, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            for raw_tick in ticks:
                n = normalize_tick(raw_tick)
                if n is None:
                    continue
                if n["time_msc"] <= last_tick_msc:
                    continue
                last_tick_msc = n["time_msc"]
                yield {"ts": n["ts"], "price": n["price"], "volume": n["volume"]}
            last_ts = _tick_field(ticks[-1], "time", 0.0)
            if last_ts > 0:
                cursor_time = datetime.fromtimestamp(int(last_ts), tz=timezone.utc)
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

def load_strategy_from_source(source_code: str, class_name: str,
                              strategy_id: str) -> Tuple[Optional[object], Optional[str]]:
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
            available = [k for k in dir(module) if not k.startswith("_")]
            return None, f"Class '{class_name}' not found. Available: {available}"
        instance = klass()
        if not hasattr(instance, "on_bar"):
            return None, f"Class '{class_name}' has no on_bar() method."
        print(f"[LOADER] Strategy loaded: {class_name} (id={strategy_id})")
        return instance, None
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[LOADER] Failed: {exc}\n{tb}")
        return None, f"{type(exc).__name__}: {exc}"


def _ensure_base_importable():
    current_module = sys.modules[__name__]
    sys.modules["base_strategy"] = current_module
    sys.modules["worker.base_strategy"] = current_module
    if "backend" not in sys.modules:
        bm = types.ModuleType("backend")
        bm.__path__ = []
        sys.modules["backend"] = bm
    if "backend.strategies" not in sys.modules:
        sm = types.ModuleType("backend.strategies")
        sm.__path__ = []
        sys.modules["backend.strategies"] = sm
    sys.modules["backend.strategies.base"] = current_module


# =============================================================================
# Strategy Runner
# =============================================================================

class StrategyRunner:
    def __init__(self, deployment_config: dict, status_callback=None):
        self.config = deployment_config
        self._status_callback = status_callback

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
        self.strategy_parameters: dict = deployment_config.get("strategy_parameters") or {}

        self._strategy = None
        self._ctx: Optional[StrategyContext] = None
        self._bar_engine: Optional[RangeBarEngine] = None
        self._executor: Optional[MT5Executor] = None
        self._exec_log: Optional[ExecutionLogger] = None
        self._indicator_engine: Optional[IndicatorEngine] = None
        self._runner_state: str = "idle"
        self._last_signal: Optional[dict] = None
        self._last_error: Optional[str] = None
        self._started_at: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._bar_index: int = 0

        # MT5 info
        self._mt5_state: Optional[str] = None
        self._mt5_broker: Optional[str] = None
        self._mt5_account_id: Optional[str] = None
        self._mt5_server: Optional[str] = None
        self._mt5_balance: Optional[float] = None
        self._mt5_equity: Optional[float] = None

        # Pipeline counters
        self._total_ticks_ingested: int = 0
        self._total_bars_produced: int = 0
        self._on_bar_call_count: int = 0
        self._signal_count: int = 0
        self._warmup_signal_count: int = 0
        self._last_bar_time: Optional[int] = None
        self._current_price: Optional[float] = None
        self._trade_counter: int = 0

        # Active trade tracking (for MA-cross exit + trade records)
        self._active_trade_meta: Optional[dict] = None

    # ── Diagnostics ─────────────────────────────────────────

    def get_diagnostics(self) -> dict:
        exec_stats = self._exec_log.get_stats() if self._exec_log else {}
        open_count = self._executor.get_open_count() if self._executor else 0
        floating = self._executor.get_floating_pnl() if self._executor else 0.0

        if self._executor and self._executor._mt5:
            try:
                acct = self._executor._mt5.account_info()
                if acct:
                    self._mt5_balance = float(acct.balance)
                    self._mt5_equity = float(acct.equity)
            except Exception:
                pass

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
                self._bar_engine.current_bars_count if self._bar_engine else 0
            ),
            "on_bar_calls": self._on_bar_call_count,
            "signal_count": self._signal_count,
            "warmup_signals": self._warmup_signal_count,
            "last_bar_time": self._last_bar_time,
            "current_price": self._current_price,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "open_positions_count": open_count,
            "floating_pnl": floating,
            "trade_count": self._trade_counter,
            **{f"exec_{k}": v for k, v in exec_stats.items()},
        }

    # ── Status Reporting ────────────────────────────────────

    def _report_status(self):
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
        for attempt in range(3):
            try:
                self._status_callback(status)
                return
            except Exception as exc:
                print(f"[RUNNER] Status report attempt {attempt + 1}/3 failed: {exc}")
                if attempt < 2:
                    time.sleep(1.0)

    def _set_state(self, state: str, error: str = None):
        self._runner_state = state
        if error:
            self._last_error = error
        print(f"[RUNNER] {self.deployment_id} -> {state}"
              + (f" (error: {error})" if error else ""))
        self._report_status()

    # ── MT5 Info ────────────────────────────────────────────

    def _capture_mt5_info(self):
        info = mt5_connector.get_mt5_account_info()
        if info:
            self._mt5_state = "connected"
            self._mt5_broker = info.get("broker")
            self._mt5_account_id = info.get("login")
            self._mt5_server = info.get("server")
            self._mt5_balance = info.get("balance")
            self._mt5_equity = info.get("equity")
            print(f"[RUNNER] MT5 info: broker={self._mt5_broker} "
                  f"account={self._mt5_account_id} balance={self._mt5_balance}")
        else:
            self._mt5_state = "connected_no_account"

    # ── Position Refresh ────────────────────────────────────

    def _refresh_position(self):
        if self._executor:
            pos = self._executor.get_position_state()
            if self._active_trade_meta and pos.has_position:
                pos.entry_bar = self._active_trade_meta.get("entry_bar")
            self._ctx.position = pos

    # ── Pipeline Log ────────────────────────────────────────

    def _log_pipeline(self, label: str = ""):
        c = f" [{label}]" if label else ""
        exec_s = self._exec_log.get_stats() if self._exec_log else {}
        pos_n = self._executor.get_open_count() if self._executor else 0
        print(
            f"[PIPELINE]{c} dep={self.deployment_id} | "
            f"ticks={self._total_ticks_ingested} "
            f"bars={self._total_bars_produced} "
            f"on_bar={self._on_bar_call_count} "
            f"signals={self._signal_count} "
            f"buys={exec_s.get('buys_filled', 0)} "
            f"sells={exec_s.get('sells_filled', 0)} "
            f"closes={exec_s.get('closes_filled', 0)} "
            f"ma_exits={exec_s.get('ma_cross_exits', 0)} "
            f"positions={pos_n} "
            f"trades={self._trade_counter} "
            f"price={self._current_price}"
        )

    # ── MA-Cross Exit Check ─────────────────────────────────

    def _check_ma_cross_exit(self, bar: dict) -> bool:
        """
        Check if any engine-level MA cross exit triggers.
        Matches JINNI ZERO backtester _check_exit() MA cross logic.
        Returns True if a position was closed.
        """
        if not self._active_trade_meta:
            return False

        pos = self._ctx.position
        if not pos.has_position:
            return False

        close_price = float(bar.get("close", 0))
        direction = pos.direction

        # Check TP MA cross
        tp_ma_key = self._active_trade_meta.get("engine_tp_ma_key")
        if tp_ma_key:
            tp_ma_val = self._ctx.indicators.get(tp_ma_key)
            if tp_ma_val is not None:
                if direction == "long" and close_price < tp_ma_val:
                    self._exec_log.log_ma_cross_exit(tp_ma_key, direction,
                                                     tp_ma_val, close_price)
                    self._close_and_record("MA_TP_EXIT", bar)
                    return True
                if direction == "short" and close_price > tp_ma_val:
                    self._exec_log.log_ma_cross_exit(tp_ma_key, direction,
                                                     tp_ma_val, close_price)
                    self._close_and_record("MA_TP_EXIT", bar)
                    return True

        # Check SL MA cross
        sl_ma_key = self._active_trade_meta.get("engine_sl_ma_key")
        if sl_ma_key:
            sl_ma_val = self._ctx.indicators.get(sl_ma_key)
            if sl_ma_val is not None:
                if direction == "long" and close_price < sl_ma_val:
                    self._exec_log.log_ma_cross_exit(sl_ma_key, direction,
                                                     sl_ma_val, close_price)
                    self._close_and_record("MA_SL_EXIT", bar)
                    return True
                if direction == "short" and close_price > sl_ma_val:
                    self._exec_log.log_ma_cross_exit(sl_ma_key, direction,
                                                     sl_ma_val, close_price)
                    self._close_and_record("MA_SL_EXIT", bar)
                    return True

        return False

    # ── Close + Record Trade ────────────────────────────────

    def _close_and_record(self, reason: str, bar: dict):
        """Close all positions and write trade record to ctx._trades."""
        pos = self._ctx.position
        if not pos.has_position:
            return

        results = self._executor.close_all_positions()
        self._exec_log.log_close(results, reason=reason)

        # Build trade record
        meta = self._active_trade_meta or {}
        for r in results:
            if r.get("success"):
                self._trade_counter += 1
                record = build_trade_record(
                    trade_id=self._trade_counter,
                    direction=pos.direction or "long",
                    entry_price=pos.entry_price or 0,
                    entry_bar=meta.get("entry_bar", self._bar_index),
                    entry_time=meta.get("entry_time", bar.get("time", 0)),
                    exit_price=r.get("price", 0),
                    exit_bar=self._bar_index,
                    exit_time=bar.get("time", 0),
                    exit_reason=reason,
                    sl=pos.sl,
                    tp=pos.tp,
                    lot_size=pos.size or self.lot_size,
                    ticket=r.get("ticket"),
                    profit=r.get("profit", 0),
                )
                self._ctx._trades.append(record)
                print(f"[TRADE #{self._trade_counter}] {record['direction'].upper()} "
                      f"entry={record['entry_price']} exit={record['exit_price']} "
                      f"reason={reason} profit={record.get('profit', 0):.2f}")

        self._active_trade_meta = None
        self._refresh_position()

    # ── Bar Callback ────────────────────────────────────────

    def _on_new_bar(self, bar: dict):
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

        # Update indicators
        if self._indicator_engine:
            self._indicator_engine.update(bars_list, self._ctx)

        # Refresh real position from MT5
        self._refresh_position()

        # Check engine-level MA cross exits BEFORE calling strategy
        if self._ctx.position.has_position:
            if self._check_ma_cross_exit(bar):
                # Position was closed by MA cross — strategy will see flat
                self._refresh_position()

        min_lb = getattr(self._strategy, "min_lookback", 0) or 0
        if self._ctx.index < min_lb:
            return

        self._on_bar_call_count += 1

        try:
            raw_signal = self._strategy.on_bar(self._ctx)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[RUNNER] on_bar() error: {exc}\n{tb}")
            self._set_state("failed", f"on_bar error: {type(exc).__name__}: {exc}")
            self._stop_event.set()
            return

        action = validate_signal(raw_signal, self._bar_index)
        self._handle_signal(action, bar)

        if self._on_bar_call_count % 50 == 0:
            self._log_pipeline("LIVE_BAR")

    # ── Signal Handling + Execution ─────────────────────────

    def _handle_signal(self, action: dict, bar: dict):
        sig = action.get("signal")
        if sig not in VALID_SIGNALS:
            return

        pos = self._ctx.position

        self._exec_log.log_signal(
            sig, self._bar_index, self._last_bar_time,
            self._current_price, pos,
        )

        # ── HOLD ────────────────────────────────────────
        if sig == SIGNAL_HOLD:
            self._exec_log.log_hold()
            if "update_sl" in action or "update_tp" in action:
                self._handle_modify(action)
            return

        # ── CLOSE variants ──────────────────────────────
        if sig == SIGNAL_CLOSE or action.get("close"):
            if not pos.has_position:
                self._exec_log.log_skip("CLOSE", "no position")
                return
            reason = action.get("close_reason", "strategy_close")
            self._close_and_record(reason, bar)
            self._signal_count += 1
            self._last_signal = action
            return

        if sig == SIGNAL_CLOSE_LONG:
            if not pos.has_position or pos.direction != "long":
                self._exec_log.log_skip("CLOSE_LONG", "no long position")
                return
            self._close_and_record("strategy_close_long", bar)
            self._signal_count += 1
            self._last_signal = action
            return

        if sig == SIGNAL_CLOSE_SHORT:
            if not pos.has_position or pos.direction != "short":
                self._exec_log.log_skip("CLOSE_SHORT", "no short position")
                return
            self._close_and_record("strategy_close_short", bar)
            self._signal_count += 1
            self._last_signal = action
            return

        # ── BUY / SELL ──────────────────────────────────
        if sig not in (SIGNAL_BUY, SIGNAL_SELL):
            return

        self._signal_count += 1
        self._last_signal = action
        direction = "long" if sig == SIGNAL_BUY else "short"

        # Already in same direction
        if pos.has_position and pos.direction == direction:
            self._exec_log.log_skip(sig, f"already {direction}")
            return

        # In opposite direction — close first
        if pos.has_position:
            self._close_and_record("reverse", bar)

        # Compute SL from signal (ma_snapshot, fixed, or direct)
        entry_estimate = self._current_price or float(bar.get("close", 0))
        sl_price = compute_sl(action, entry_estimate, direction)
        tp_price = compute_tp(action, entry_estimate, sl_price, direction)

        # Validate SL/TP sanity
        if sl_price is not None:
            if direction == "long" and sl_price >= entry_estimate:
                print(f"[EXEC] WARNING: Long SL {sl_price} >= entry {entry_estimate}, clearing SL")
                sl_price = None
            elif direction == "short" and sl_price <= entry_estimate:
                print(f"[EXEC] WARNING: Short SL {sl_price} <= entry {entry_estimate}, clearing SL")
                sl_price = None

        if tp_price is not None:
            if direction == "long" and tp_price <= entry_estimate:
                print(f"[EXEC] WARNING: Long TP {tp_price} <= entry {entry_estimate}, clearing TP")
                tp_price = None
            elif direction == "short" and tp_price >= entry_estimate:
                print(f"[EXEC] WARNING: Short TP {tp_price} >= entry {entry_estimate}, clearing TP")
                tp_price = None

        comment = action.get("comment", f"JG_{sig}")

        # Execute
        if sig == SIGNAL_BUY:
            result = self._executor.open_buy(sl=sl_price, tp=tp_price, comment=comment)
        else:
            result = self._executor.open_sell(sl=sl_price, tp=tp_price, comment=comment)

        self._exec_log.log_open(sig, result, sl_price, tp_price)

        if result.get("success"):
            fill_price = result.get("price", entry_estimate)

            # Recompute TP from actual fill price for R-multiple
            if action.get("tp_mode") == "r_multiple" and sl_price is not None:
                real_risk = abs(fill_price - sl_price)
                r = float(action.get("tp_r", 1.0))
                if real_risk > 0:
                    if direction == "long":
                        tp_price = round(fill_price + real_risk * r, 5)
                    else:
                        tp_price = round(fill_price - real_risk * r, 5)
                    # Modify TP on the position
                    mod_result = self._executor.modify_sl_tp(
                        result["ticket"], sl=sl_price, tp=tp_price
                    )
                    self._exec_log.log_modify(mod_result, sl=sl_price, tp=tp_price)

            # Store trade metadata for MA-cross exits + trade records
            self._active_trade_meta = {
                "entry_bar": self._bar_index,
                "entry_time": bar.get("time", 0),
                "entry_price": fill_price,
                "direction": direction,
                "sl": sl_price,
                "tp": tp_price,
                "ticket": result.get("ticket"),
                "engine_sl_ma_key": action.get("engine_sl_ma_key"),
                "engine_tp_ma_key": action.get("engine_tp_ma_key"),
            }

        self._refresh_position()
        self._report_status()

    def _handle_modify(self, action: dict):
        pos = self._ctx.position
        if not pos.has_position or not pos.ticket:
            self._exec_log.log_skip("MODIFY", "no position")
            return
        new_sl = action.get("update_sl")
        new_tp = action.get("update_tp")
        result = self._executor.modify_sl_tp(pos.ticket, sl=new_sl, tp=new_tp)
        self._exec_log.log_modify(result, sl=new_sl, tp=new_tp)
        self._refresh_position()

    # ── Lifecycle ───────────────────────────────────────────

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
            print(f"[RUNNER] FATAL: {self.deployment_id}:\n{tb}")
            self._set_state("failed", f"{type(exc).__name__}: {exc}")
            try:
                mt5_connector.shutdown_mt5()
            except Exception:
                pass

    def _run_lifecycle(self):
        self._started_at = datetime.now(timezone.utc).isoformat()

        # Phase 1: Load Strategy
        self._set_state("loading_strategy")
        strategy_instance, load_error = load_strategy_from_source(
            self.source_code, self.class_name, self.strategy_id,
        )
        if load_error:
            self._set_state("failed", f"Strategy load failed: {load_error}")
            return
        self._strategy = strategy_instance
        params = self._strategy.validate_parameters(self.strategy_parameters)
        self._ctx = StrategyContext(bars=[], params=params)

        # Build indicator engine from strategy declarations
        indicator_defs = self._strategy.build_indicators(params)
        self._indicator_engine = IndicatorEngine(indicator_defs)

        try:
            self._strategy.on_init(self._ctx)
        except Exception as exc:
            self._set_state("failed", f"on_init() failed: {type(exc).__name__}: {exc}")
            return
        print(f"[RUNNER] Strategy loaded: {self.class_name} | "
              f"min_lookback={getattr(self._strategy, 'min_lookback', 0)} | "
              f"indicators={len(indicator_defs)} | params={params}")

        # Phase 2: Init MT5
        ok, msg = mt5_connector.init_mt5()
        if not ok:
            self._set_state("failed", f"MT5 init failed: {msg}")
            return
        self._capture_mt5_info()

        # Phase 2b: Create executor + logger
        self._executor = MT5Executor(self.symbol, self.lot_size, self.deployment_id)
        self._exec_log = ExecutionLogger(self.deployment_id, self.symbol)

        # Phase 3: Fetch Historical Ticks
        self._set_state("fetching_ticks")
        ticks, tick_err = mt5_connector.fetch_historical_ticks(
            self.symbol, self.tick_lookback_value, self.tick_lookback_unit,
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
            on_bar=None,
        )
        for tick in ticks:
            self._bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])

        initial_count = self._bar_engine.current_bars_count
        self._total_bars_produced = self._bar_engine.total_bars_emitted
        if self._bar_engine.bars:
            self._last_bar_time = self._bar_engine.bars[-1].get("time")

        print(f"[RUNNER] Initial bars: {initial_count} "
              f"(total emitted: {self._total_bars_produced}) "
              f"(from {len(ticks)} ticks, bar_size={self.bar_size_points}pt)")

        if initial_count == 0:
            self._set_state("failed",
                f"No bars from {len(ticks)} ticks. "
                f"bar_size_points={self.bar_size_points} may be too large for {self.symbol}.")
            mt5_connector.shutdown_mt5()
            return

        self._log_pipeline("INITIAL_BARS")

        # Phase 5: Warm Up (signals logged, NOT executed)
        self._set_state("warming_up")
        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        min_lb = getattr(self._strategy, "min_lookback", 0) or 0

        for i in range(len(bars_list)):
            if self._stop_event.is_set():
                return
            self._ctx.index = i
            self._bar_index = i

            # Compute indicators for warmup bars
            if self._indicator_engine:
                warmup_slice = bars_list[:i + 1]
                self._indicator_engine.update(warmup_slice, self._ctx)

            self._refresh_position()

            if i < min_lb:
                continue

            self._on_bar_call_count += 1
            try:
                raw_signal = self._strategy.on_bar(self._ctx)
                if raw_signal:
                    s = raw_signal.get("signal")
                    if s in (SIGNAL_BUY, SIGNAL_SELL, SIGNAL_CLOSE,
                             SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT):
                        self._warmup_signal_count += 1
                        print(f"[RUNNER] Warmup signal #{self._warmup_signal_count} "
                              f"at bar {i}: {s} (NOT executed)")
            except Exception as exc:
                print(f"[RUNNER] Warmup on_bar error at bar {i}: {exc}")

        print(f"[RUNNER] Warmup complete. on_bar calls: {self._on_bar_call_count} | "
              f"warmup signals: {self._warmup_signal_count} (all skipped)")
        self._log_pipeline("WARMUP_DONE")

        # Phase 6: Live Tick Loop (signals ARE executed)
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
                self._bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])
                if live_tick_count % 5000 == 0:
                    self._log_pipeline("LIVE_TICK")
        except Exception as exc:
            if not self._stop_event.is_set():
                tb = traceback.format_exc()
                print(f"[RUNNER] Live loop error: {exc}\n{tb}")
                self._set_state("failed", f"Live loop error: {type(exc).__name__}: {exc}")
        finally:
            self._log_pipeline("SHUTDOWN")
            mt5_connector.shutdown_mt5()
            self._mt5_state = "disconnected"
            if not self._stop_event.is_set():
                self._set_state("stopped")