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
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from trading.indicators import IndicatorEngine, precompute_indicator_series
from trading.execution import (
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
    """
    Strategy execution context — backtester-compatible.

    ctx.index:           absolute monotonic bar counter (never resets, never wraps)
    ctx.bar:             current bar dict (OHLCV)
    ctx.bars:            rolling bar window (deque snapshot, use negative indexing for lookback)
    ctx.indicators:      current bar indicator values {key: float}
    ctx.ind_series:      full indicator series {key: [float]} over current bar window
    ctx.prev_indicators: previous bar's indicator values (backtester compat)
    ctx.position:        PositionState (has_position, direction, sl_level, tp_level, etc.)
    ctx.params:          strategy parameters
    ctx.state:           mutable dict — persists across bars (strategy's scratch space)
    ctx.trades:          closed trade records (read-only list)
    ctx.equity:          current mark-to-market equity
    ctx.balance:         current realized balance
    """

    def __init__(self, bars: list, params: dict,
                 position: Optional[PositionState] = None):
        self._bars = bars
        self._params = params
        self._position = position or PositionState()
        self._index: int = 0
        self._bar_offset: int = 0
        self._trades: list = []
        self._equity: float = 0.0
        self._balance: float = 0.0
        self._indicators: dict = {}
        self._ind_series: dict = {}
        self._prev_indicators: dict = {}
        self.state: dict = {}

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, val: int):
        self._index = val

    @property
    def bar(self) -> dict:
        if 0 <= self._bar_offset < len(self._bars):
            return self._bars[self._bar_offset]
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
    def prev_indicators(self) -> dict:
        return self._prev_indicators

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
                 on_bar: Optional[Callable[[dict], None]] = None,
                 debug: bool = False):
        self.range_size = float(bar_size_points)
        self.max_bars = max_bars
        self._on_bar = on_bar
        self.debug = debug
        self.trend = 0
        self.bar: Optional[dict] = None
        self.bars: deque = deque(maxlen=max_bars)
        self._last_emitted_ts: Optional[int] = None
        self.total_ticks = 0
        self.total_bars_emitted = 0

    @property
    def current_bars_count(self) -> int:
        return len(self.bars)

    def _snap_to_grid(self, price: float) -> float:
        level = round(price / self.range_size)
        return round(level * self.range_size, 5)

    def _emit(self, bar_dict: dict) -> None:
        ts = int(bar_dict["time"])
        if self._last_emitted_ts is not None and ts <= self._last_emitted_ts:
            ts = self._last_emitted_ts + 1
        bar_dict["time"] = ts
        self._last_emitted_ts = ts
        self.bars.append(bar_dict)
        self.total_bars_emitted += 1
        if self.debug and self._on_bar is None:
            if self.total_bars_emitted <= 5 or self.total_bars_emitted % 100 == 0:
                d = "UP" if bar_dict["close"] > bar_dict["open"] else "DN"
                print(f"[RENKO] BAR #{self.total_bars_emitted} {d} | "
                      f"O={bar_dict['open']:.5f} H={bar_dict['high']:.5f} "
                      f"L={bar_dict['low']:.5f} C={bar_dict['close']:.5f} "
                      f"| trend={self.trend}")
        if self._on_bar:
            self._on_bar(bar_dict)

    def _start_bar(self, ts: int, price: float, volume: float) -> None:
        snapped = self._snap_to_grid(price)
        self.bar = {"time": ts, "open": snapped, "high": snapped,
                    "low": snapped, "close": snapped, "volume": volume}
        if self.debug:
            print(f"[RENKO] Start bar: raw_price={price:.5f} "
                  f"snapped_open={snapped:.5f} grid_size={self.range_size}")

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
                up_t = round(o + rs, 5)
                dn_t = round(o - rs, 5)
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
                cont_t = round(o + rs, 5)
                rev_t = round(o - (2 * rs), 5)
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
                    ro = round(o - rs, 5)
                    rc = round(o - (2 * rs), 5)
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
                cont_t = round(o - rs, 5)
                rev_t = round(o + (2 * rs), 5)
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
                    ro = round(o + rs, 5)
                    rc = round(o + (2 * rs), 5)
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
# ★ FIX: MT5 Deal History Fetcher (inline, no external module needed)
# =============================================================================

def fetch_closed_position_from_mt5(position_ticket: int, symbol: str,
                                    max_retries: int = 5,
                                    retry_delay_ms: int = 300) -> Optional[dict]:
    mt5 = _import_mt5()
    if mt5 is None:
        print("[MT5] MetaTrader5 not installed — cannot fetch deal history")
        return None

    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_INOUT = 2
    DEAL_TYPE_BUY = 0
    DEAL_TYPE_SELL = 1
    DEAL_REASON_CLIENT = 0
    DEAL_REASON_MOBILE = 1
    DEAL_REASON_WEB = 2
    DEAL_REASON_EXPERT = 3
    DEAL_REASON_SL = 4
    DEAL_REASON_TP = 5
    DEAL_REASON_SO = 6

    for attempt in range(max_retries):
        try:
            now = datetime.now(timezone.utc)
            start = now - timedelta(hours=24)
            deals = mt5.history_deals_get(start, now, position=position_ticket)

            if deals is None or len(deals) == 0:
                if attempt < max_retries - 1:
                    delay = retry_delay_ms / 1000.0
                    print(f"[MT5] Deal history empty for ticket {position_ticket}, "
                          f"retry {attempt + 2}/{max_retries} in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[MT5] No deals found for ticket {position_ticket} "
                          f"after {max_retries} attempts")
                    return None

            entry_deal = None
            exit_deal = None
            all_deals = list(deals)

            for deal in all_deals:
                if deal.entry == DEAL_ENTRY_IN:
                    entry_deal = deal
                elif deal.entry == DEAL_ENTRY_OUT:
                    exit_deal = deal
                elif deal.entry == DEAL_ENTRY_INOUT:
                    exit_deal = deal

            if exit_deal is None:
                for deal in all_deals:
                    if deal.profit != 0 and deal != entry_deal:
                        exit_deal = deal
                        break

            if exit_deal is None:
                if attempt < max_retries - 1:
                    delay = retry_delay_ms / 1000.0
                    print(f"[MT5] No exit deal yet for ticket {position_ticket}, "
                          f"retry {attempt + 2}/{max_retries} in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[MT5] No exit deal found for ticket {position_ticket} "
                          f"after {max_retries} attempts. Deals found: {len(all_deals)}")
                    return None

            if entry_deal is not None:
                direction = "long" if entry_deal.type == DEAL_TYPE_BUY else "short"
                entry_price = entry_deal.price
                entry_time_unix = entry_deal.time
            else:
                direction = "short" if exit_deal.type == DEAL_TYPE_BUY else "long"
                entry_price = 0.0
                entry_time_unix = exit_deal.time

            exit_price = exit_deal.price
            exit_time_unix = exit_deal.time
            profit = round(exit_deal.profit, 2)
            commission_total = 0.0
            swap_total = 0.0
            fee_total = 0.0
            deal_tickets = []

            for deal in all_deals:
                commission_total += deal.commission
                swap_total += deal.swap
                if hasattr(deal, 'fee'):
                    fee_total += deal.fee
                deal_tickets.append(deal.ticket)

            commission_total = round(commission_total, 2)
            swap_total = round(swap_total, 2)
            fee_total = round(fee_total, 2)
            net_pnl = round(profit + commission_total + swap_total + fee_total, 2)

            exit_reason = "UNKNOWN"
            if hasattr(exit_deal, 'reason'):
                reason_code = exit_deal.reason
                if reason_code == DEAL_REASON_SL:
                    exit_reason = "SL_HIT"
                elif reason_code == DEAL_REASON_TP:
                    exit_reason = "TP_HIT"
                elif reason_code == DEAL_REASON_SO:
                    exit_reason = "STOP_OUT"
                elif reason_code == DEAL_REASON_EXPERT:
                    exit_reason = "EA_CLOSE"
                elif reason_code in (DEAL_REASON_CLIENT, DEAL_REASON_MOBILE,
                                      DEAL_REASON_WEB):
                    exit_reason = "MANUAL_CLOSE"
                else:
                    exit_reason = f"REASON_{reason_code}"

            entry_time_iso = datetime.fromtimestamp(
                entry_time_unix, tz=timezone.utc
            ).isoformat() if entry_time_unix else None
            exit_time_iso = datetime.fromtimestamp(
                exit_time_unix, tz=timezone.utc
            ).isoformat() if exit_time_unix else None

            lot_size = exit_deal.volume if exit_deal.volume > 0 else (
                entry_deal.volume if entry_deal and entry_deal.volume > 0 else 0
            )

            mt5_comment = ""
            if hasattr(exit_deal, 'comment') and exit_deal.comment:
                mt5_comment = str(exit_deal.comment)

            print(f"[MT5] Deal history fetched for ticket {position_ticket}: "
                  f"profit={profit} comm={commission_total} swap={swap_total} "
                  f"net={net_pnl} reason={exit_reason} deals={len(all_deals)}")

            return {
                "symbol": symbol,
                "direction": direction,
                "lot_size": lot_size,
                "entry_price": round(entry_price, 5),
                "exit_price": round(exit_price, 5),
                "entry_time": entry_time_iso,
                "exit_time": exit_time_iso,
                "entry_time_unix": entry_time_unix,
                "exit_time_unix": exit_time_unix,
                "profit": profit,
                "commission": commission_total,
                "swap": swap_total,
                "fee": fee_total,
                "net_pnl": net_pnl,
                "exit_reason": exit_reason,
                "mt5_deal_tickets": deal_tickets,
                "mt5_comment": mt5_comment,
            }

        except Exception as e:
            print(f"[MT5] Error fetching deal history for ticket {position_ticket}: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay_ms / 1000.0)
            else:
                traceback.print_exc()
                return None

    return None


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
        module.BaseStrategy = BaseStrategy  # ← inject before exec
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
# Strategy Runner — RECODED to match engine_core.py backtester 1:1
#
# Execution model: signal-on-close, execute-on-next-open
#   Bar N:   strategy sees completed bar → returns BUY → stored as PENDING
#   Bar N+1: _on_new_bar fires → pending executed via MT5 at market
#            → SL/TP computed from actual fill price
#            → entry bar immune to MA cross exits
#
# This matches the backtester's 7-step per-bar loop exactly.
#
# ★ VALIDATION MODE: When validation_mode=True:
#   - Uses SimulatedExecutor instead of MT5Executor
#   - Skips MT5 deal history (uses estimated fallback path)
#   - run_validation() feeds historical ticks through the SAME _on_new_bar()
#   - Zero logic changes to the execution pipeline
# =============================================================================

class StrategyRunner:

    def __init__(self, deployment_config, status_callback=None, trade_callback=None,
                 validation_mode=False, debug: bool = True):
        self.config = deployment_config
        self._status_callback = status_callback
        self._trade_callback = trade_callback
        self.debug = debug

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
        self.worker_id: str = deployment_config.get("worker_id", "")

        # ★ Validation mode flag
        self._validation_mode = validation_mode

        self._deployment_id: str = self.deployment_id
        self._strategy_id: str = self.strategy_id
        self._worker_id: str = self.worker_id

        # ★ Config loading — safe for validation mode (no config.yaml needed)
        self._mother_url = ""
        if not validation_mode:
            try:
                self._mother_url = __import__("yaml").safe_load(
                    open("config.yaml"))["mother_server"]["url"]
            except Exception:
                self._mother_url = ""

        self._unreported_trades: list = []

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

        # ★ CHART: data buffers (flushed by worker_agent)
        self._chart_bar_buffer: list = []
        self._chart_marker_buffer: list = []
        self._chart_bar_lock = threading.Lock()
        self._chart_marker_lock = threading.Lock()

        # Backtester-aligned execution state
        self._absolute_bar_counter: int = -1
        self._prev_indicators: dict = {}

        # Active trade tracking
        self._active_trade_meta: Optional[dict] = None

        # Backtester-aligned pending signal + entry bar immunity
        self._pending_signal: Optional[dict] = None
        self._just_entered_this_bar: bool = False

    # ─────────────────────────────────────────────────────────
    # Diagnostics
    # ─────────────────────────────────────────────────────────

    def get_diagnostics(self) -> dict:
        exec_stats = self._exec_log.get_stats() if self._exec_log else {}
        open_count = self._executor.get_open_count() if self._executor else 0
        floating = self._executor.get_floating_pnl() if self._executor else 0.0

        if self._executor and not self._validation_mode:
            try:
                mt5_mod = getattr(self._executor, '_mt5', None)
                if mt5_mod:
                    acct = mt5_mod.account_info()
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
            "pending_signal": (
                self._pending_signal.get("direction")
                if self._pending_signal else None
            ),
            **{f"exec_{k}": v for k, v in exec_stats.items()},
            "account_balance": self._mt5_balance,
            "account_equity": self._mt5_equity,
        }

    # ─────────────────────────────────────────────────────────
    # Status / Trade Reporting
    # ─────────────────────────────────────────────────────────

    def _report_status(self):
        if not self._status_callback:
            return
        status = {
            "deployment_id": self.deployment_id,
            "strategy_id": self.strategy_id,
            "strategy_name": (getattr(self._strategy, "name", None)
                              if self._strategy else None),
            "symbol": self.symbol,
            "runner_state": self._runner_state,
            "bar_size_points": self.bar_size_points,
            "max_bars_in_memory": self.max_bars,
            "current_bars_count": (self._bar_engine.current_bars_count
                                   if self._bar_engine else 0),
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

    def _report_trade(self, record: dict):
        # ★ In validation mode, use trade_callback directly (no HTTP)
        if self._validation_mode:
            if self._trade_callback:
                try:
                    self._trade_callback(record)
                except Exception as e:
                    print(f"[RUNNER] Validation trade callback failed: {e}")
            return

        mother_url = self._mother_url
        if not mother_url:
            print("[RUNNER] No mother URL configured — trade not reported")
            return
        url = f"{mother_url}/api/portfolio/trades/report"
        payload = {}
        for k, v in record.items():
            if v is None:
                payload[k] = None
            elif isinstance(v, (list, dict)):
                payload[k] = v
            else:
                try:
                    payload[k] = float(v) if isinstance(v, (int, float)) else str(v)
                except (ValueError, TypeError):
                    payload[k] = str(v)
        payload.setdefault("deployment_id", self._deployment_id)
        payload.setdefault("strategy_id", self._strategy_id)
        payload.setdefault("worker_id", self._worker_id)
        payload.setdefault("symbol", self.symbol)

        # Also call trade_callback if set (for worker_agent local ledger)
        if self._trade_callback:
            try:
                self._trade_callback(record)
            except Exception as e:
                print(f"[RUNNER] Trade callback failed: {e}")

        def _send():
            last_err = None
            for attempt in range(5):
                try:
                    resp = requests.post(url, json=payload, timeout=8)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("ok"):
                            print(f"[RUNNER] Trade #{record.get('trade_id', '?')} "
                                  f"reported to mother (attempt {attempt + 1})")
                            return
                        else:
                            last_err = f"Server returned ok=false: {data}"
                    else:
                        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                except requests.exceptions.ConnectionError as e:
                    last_err = f"Connection error: {e}"
                except requests.exceptions.Timeout:
                    last_err = "Timeout"
                except Exception as e:
                    last_err = str(e)
                wait = 0.5 * (attempt + 1)
                print(f"[RUNNER] Trade report attempt {attempt + 1} failed: "
                      f"{last_err}. Retry in {wait}s...")
                time.sleep(wait)
            print(f"[RUNNER] CRITICAL: Failed to report trade after 5 attempts: "
                  f"{last_err}")
            self._unreported_trades.append(payload)
        t = threading.Thread(target=_send, daemon=True)
        t.start()

    def retry_unreported_trades(self):
        if not self._unreported_trades:
            return
        mother_url = self._mother_url
        if not mother_url:
            return
        url = f"{mother_url}/api/portfolio/trades/report"
        remaining = []
        for payload in self._unreported_trades:
            try:
                resp = requests.post(url, json=payload, timeout=5)
                if resp.status_code == 200 and resp.json().get("ok"):
                    print(f"[RUNNER] Retried trade #{payload.get('trade_id', '?')} "
                          f"reported successfully")
                else:
                    remaining.append(payload)
            except Exception:
                remaining.append(payload)
        self._unreported_trades = remaining

    def _set_state(self, state: str, error: str = None):
        self._runner_state = state
        if error:
            self._last_error = error
        print(f"[RUNNER] {self.deployment_id} -> {state}"
              + (f" (error: {error})" if error else ""))
        self._report_status()

    # ─────────────────────────────────────────────────────────
    # MT5 Info / Position Refresh / Pipeline Log
    # ─────────────────────────────────────────────────────────

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

    def _refresh_position(self):
        if self._executor:
            pos = self._executor.get_position_state()
            if self._active_trade_meta and pos.has_position:
                pos.entry_bar = self._active_trade_meta.get("entry_bar")
                pos.bars_held = max(0, self._bar_index - (
                    pos.entry_bar or self._bar_index))
                close_price = self._current_price or 0.0
                if pos.entry_price and close_price > 0:
                    if pos.direction == "long":
                        pos.unrealized_pts = round(
                            close_price - pos.entry_price, 5)
                    elif pos.direction == "short":
                        pos.unrealized_pts = round(
                            pos.entry_price - close_price, 5)
                    pos.unrealized_pnl = round(pos.profit or 0.0, 2)
            self._ctx.position = pos

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
            f"pending={'YES' if self._pending_signal else 'no'} "
            f"price={self._current_price}"
        )

    # ─────────────────────────────────────────────────────────
    # MA-Cross Exit Check
    # ─────────────────────────────────────────────────────────

    def _check_ma_cross_exit(self, bar: dict) -> bool:
        if not self._active_trade_meta:
            return False
        pos = self._ctx.position
        if not pos.has_position:
            return False
        close_price = float(bar.get("close", 0))
        direction = pos.direction

        tp_ma_key = self._active_trade_meta.get("engine_tp_ma_key")
        if tp_ma_key:
            tp_ma_val = self._ctx.indicators.get(tp_ma_key)
            if tp_ma_val is not None:
                if direction == "long" and close_price < tp_ma_val:
                    self._exec_log.log_ma_cross_exit(
                        tp_ma_key, direction, tp_ma_val, close_price)
                    self._close_and_record("MA_TP_EXIT", bar)
                    return True
                if direction == "short" and close_price > tp_ma_val:
                    self._exec_log.log_ma_cross_exit(
                        tp_ma_key, direction, tp_ma_val, close_price)
                    self._close_and_record("MA_TP_EXIT", bar)
                    return True

        sl_ma_key = self._active_trade_meta.get("engine_sl_ma_key")
        if sl_ma_key:
            sl_ma_val = self._ctx.indicators.get(sl_ma_key)
            if sl_ma_val is not None:
                if direction == "long" and close_price < sl_ma_val:
                    self._exec_log.log_ma_cross_exit(
                        sl_ma_key, direction, sl_ma_val, close_price)
                    self._close_and_record("MA_SL_EXIT", bar)
                    return True
                if direction == "short" and close_price > sl_ma_val:
                    self._exec_log.log_ma_cross_exit(
                        sl_ma_key, direction, sl_ma_val, close_price)
                    self._close_and_record("MA_SL_EXIT", bar)
                    return True
        return False

    # ─────────────────────────────────────────────────────────
    # Close + Record / Broker Close
    # ★ VALIDATION MODE: skip MT5 deal history fetch
    # ─────────────────────────────────────────────────────────

    def _close_and_record(self, reason: str, bar: dict):
        pos = self._ctx.position
        if not pos.has_position:
            return
        results = self._executor.close_all_positions()
        self._exec_log.log_close(results, reason=reason)
        meta = self._active_trade_meta or {}
        for r in results:
            if r.get("success"):
                self._trade_counter += 1
                ticket = r.get("ticket") or meta.get("ticket")

                # ★ Skip MT5 history in validation mode
                mt5_record = None
                if ticket and not self._validation_mode:
                    mt5_record = fetch_closed_position_from_mt5(
                        position_ticket=ticket, symbol=self.symbol,
                        max_retries=5, retry_delay_ms=300)

                if mt5_record:
                    record = {
                        "mt5_ticket": ticket,
                        "trade_id": self._trade_counter,
                        "deployment_id": self._deployment_id,
                        "strategy_id": self._strategy_id,
                        "worker_id": self._worker_id,
                        "symbol": mt5_record["symbol"],
                        "direction": mt5_record["direction"],
                        "lot_size": mt5_record["lot_size"],
                        "entry_price": mt5_record["entry_price"],
                        "exit_price": mt5_record["exit_price"],
                        "entry_time": mt5_record["entry_time"],
                        "exit_time": mt5_record["exit_time"],
                        "entry_time_unix": mt5_record.get("entry_time_unix"),
                        "exit_time_unix": mt5_record.get("exit_time_unix"),
                        "profit": mt5_record["profit"],
                        "commission": mt5_record["commission"],
                        "swap": mt5_record["swap"],
                        "fee": mt5_record.get("fee", 0),
                        "net_pnl": mt5_record["net_pnl"],
                        "exit_reason": reason,
                        "mt5_exit_reason": mt5_record["exit_reason"],
                        "mt5_source": True,
                        "entry_bar": meta.get("entry_bar", self._bar_index),
                        "exit_bar": self._bar_index,
                        "bars_held": max(0, self._bar_index - meta.get(
                            "entry_bar", self._bar_index)),
                        "mt5_deal_tickets": mt5_record.get(
                            "mt5_deal_tickets", []),
                        "mt5_comment": mt5_record.get("mt5_comment", ""),
                        "sl": meta.get("sl") or pos.sl,
                        "tp": meta.get("tp") or pos.tp,
                    }
                    print(f"[TRADE #{self._trade_counter}] MT5 CONFIRMED | "
                          f"ticket={ticket} {mt5_record['direction'].upper()} "
                          f"entry={mt5_record['entry_price']:.5f} "
                          f"exit={mt5_record['exit_price']:.5f} "
                          f"profit={mt5_record['profit']:.2f} "
                          f"comm={mt5_record['commission']:.2f} "
                          f"swap={mt5_record['swap']:.2f} "
                          f"net={mt5_record['net_pnl']:.2f} "
                          f"reason={reason}")
                    self._ctx._trades.append(record)
                    self._report_trade(record)

                    # ★ CHART: Buffer exit marker (MT5 branch)
                    _exit_mt = "exit_tp" if "TP" in reason else (
                               "exit_sl" if "SL" in reason else (
                               "exit_ma" if "MA" in reason else "exit_strategy"))
                    with self._chart_marker_lock:
                        self._chart_marker_buffer.append({
                            "marker_type": _exit_mt,
                            "time": int(bar.get("time", 0)),
                            "price": record.get("exit_price", 0),
                            "bar_index": self._bar_index,
                            "side": record.get("direction"),
                            "label": reason,
                        })

                else:
                    # ★ Build record manually with correct field names
                    exit_profit = r.get("profit", 0)
                    entry_price = pos.entry_price or meta.get("entry_price", 0)
                    exit_price = r.get("price", 0)
                    direction = pos.direction or meta.get("direction", "long")
                    entry_bar = meta.get("entry_bar", self._bar_index)
                    bars_held = max(0, self._bar_index - entry_bar)
                    sl_val = meta.get("sl") or pos.sl
                    tp_val = meta.get("tp") or pos.tp

                    record = {
                        "trade_id": self._trade_counter,
                        "deployment_id": self._deployment_id,
                        "strategy_id": self._strategy_id,
                        "worker_id": self._worker_id,
                        "symbol": self.symbol,
                        "direction": direction,
                        "lot_size": pos.size or self.lot_size,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "entry_bar": entry_bar,
                        "exit_bar": self._bar_index,
                        "entry_time": meta.get("entry_time", bar.get("time", 0)),
                        "exit_time": bar.get("time", 0),
                        "exit_reason": reason,
                        "sl": sl_val,
                        "tp": tp_val,
                        "ticket": ticket,
                        "profit": round(float(exit_profit), 2),
                        "commission": 0.0,
                        "swap": 0.0,
                        "fee": 0.0,
                        "net_pnl": round(float(exit_profit), 2),
                        "bars_held": bars_held,
                        "mt5_source": False,
                    }
                    print(f"[TRADE #{self._trade_counter}] "
                          f"{'SIM' if self._validation_mode else 'FALLBACK'} | "
                          f"{direction.upper()} "
                          f"entry={entry_price} exit={exit_price} "
                          f"sl={sl_val} tp={tp_val} "
                          f"reason={reason} profit={exit_profit:.2f}")
                    self._ctx._trades.append(record)
                    self._report_trade(record)

                    # ★ CHART: Buffer exit marker (fallback branch)
                    _exit_mt = "exit_tp" if "TP" in reason else (
                               "exit_sl" if "SL" in reason else (
                               "exit_ma" if "MA" in reason else "exit_strategy"))
                    with self._chart_marker_lock:
                        self._chart_marker_buffer.append({
                            "marker_type": _exit_mt,
                            "time": int(bar.get("time", 0)),
                            "price": record.get("exit_price", 0),
                            "bar_index": self._bar_index,
                            "side": record.get("direction"),
                            "label": reason,
                        })

        self._active_trade_meta = None
        self._refresh_position()

    def _handle_broker_close(self, bar: dict):
        meta = self._active_trade_meta
        if not meta:
            return
        ticket = meta.get("ticket")

        if not ticket:
            print(f"[RUNNER] WARNING: No ticket — recording with estimates.")
            self._trade_counter += 1
            record = {
                "trade_id": self._trade_counter,
                "deployment_id": self._deployment_id,
                "strategy_id": self._strategy_id,
                "worker_id": self._worker_id,
                "symbol": self.symbol,
                "direction": meta.get("direction", "long"),
                "lot_size": self.lot_size,
                "entry_price": meta.get("entry_price", 0),
                "exit_price": self._current_price or float(bar.get("close", 0)),
                "entry_bar": meta.get("entry_bar", self._bar_index),
                "exit_bar": self._bar_index,
                "entry_time": meta.get("entry_time", bar.get("time", 0)),
                "exit_time": bar.get("time", 0),
                "exit_reason": "BROKER_CLOSE_NO_TICKET",
                "sl": meta.get("sl"),
                "tp": meta.get("tp"),
                "ticket": None,
                "profit": 0.0,
                "commission": 0.0,
                "swap": 0.0,
                "fee": 0.0,
                "net_pnl": 0.0,
                "bars_held": max(0, self._bar_index - meta.get("entry_bar", self._bar_index)),
                "mt5_source": False,
            }
            self._ctx._trades.append(record)
            self._report_trade(record)

            # ★ CHART: Buffer exit marker (no-ticket broker close)
            with self._chart_marker_lock:
                self._chart_marker_buffer.append({
                    "marker_type": "exit_sl",
                    "time": int(bar.get("time", 0)),
                    "price": record["exit_price"],
                    "bar_index": self._bar_index,
                    "side": record["direction"],
                    "label": "BROKER_CLOSE_NO_TICKET",
                })

            self._active_trade_meta = None
            self._exec_log.closes_filled += 1
            return

        print(f"[RUNNER] Position {ticket} closed — fetching history...")

        # ★ VALIDATION MODE: Get close info from SimulatedExecutor
        if self._validation_mode:
            close_info = None
            if hasattr(self._executor, 'get_broker_close_info'):
                close_info = self._executor.get_broker_close_info(ticket)

            self._trade_counter += 1
            direction = meta.get("direction", "long")
            entry_price = meta.get("entry_price", 0)
            entry_bar = meta.get("entry_bar", self._bar_index)
            bars_held = max(0, self._bar_index - entry_bar)

            if close_info:
                exit_price = close_info["price"]
                exit_profit = close_info["profit"]
                exit_reason = close_info.get("reason", "BROKER_CLOSE")
                sl_val = close_info.get("sl", meta.get("sl"))
                tp_val = close_info.get("tp", meta.get("tp"))
            else:
                exit_price = self._current_price or float(bar.get("close", 0))
                exit_profit = 0.0
                exit_reason = "BROKER_CLOSE_ESTIMATED"
                sl_val = meta.get("sl")
                tp_val = meta.get("tp")

            record = {
                "trade_id": self._trade_counter,
                "deployment_id": self._deployment_id,
                "strategy_id": self._strategy_id,
                "worker_id": self._worker_id,
                "symbol": self.symbol,
                "direction": direction,
                "lot_size": self.lot_size,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "entry_bar": entry_bar,
                "exit_bar": self._bar_index,
                "entry_time": meta.get("entry_time", bar.get("time", 0)),
                "exit_time": bar.get("time", 0),
                "exit_reason": exit_reason,
                "sl": sl_val,
                "tp": tp_val,
                "ticket": ticket,
                "profit": exit_profit,
                "commission": 0.0,
                "swap": 0.0,
                "fee": 0.0,
                "net_pnl": round(exit_profit, 2),
                "bars_held": bars_held,
                "mt5_source": False,
            }

            print(f"[TRADE #{self._trade_counter}] SIM BROKER | "
                  f"ticket={ticket} {direction.upper()} "
                  f"entry={entry_price:.5f} exit={exit_price:.5f} "
                  f"sl={sl_val} tp={tp_val} "
                  f"profit={exit_profit:.2f} reason={exit_reason}")

            self._ctx._trades.append(record)
            self._report_trade(record)

            # ★ CHART: Buffer exit marker (sim broker close)
            _exit_mt = "exit_tp" if "TP" in exit_reason else (
                       "exit_sl" if "SL" in exit_reason else "exit_strategy")
            with self._chart_marker_lock:
                self._chart_marker_buffer.append({
                    "marker_type": _exit_mt,
                    "time": int(bar.get("time", 0)),
                    "price": exit_price,
                    "bar_index": self._bar_index,
                    "side": direction,
                    "label": exit_reason,
                })

            self._active_trade_meta = None
            self._exec_log.closes_filled += 1
            return

        # ★ LIVE MODE: Fetch MT5 deal history (unchanged)
        mt5_record = fetch_closed_position_from_mt5(
            position_ticket=ticket, symbol=self.symbol,
            max_retries=5, retry_delay_ms=300)

        if mt5_record is None:
            print(f"[RUNNER] WARNING: MT5 history unavailable for {ticket}.")
            self._trade_counter += 1
            entry_price = meta.get("entry_price", 0)
            exit_price = self._current_price or float(bar.get("close", 0))
            direction = meta.get("direction", "long")
            mt5 = _import_mt5()
            contract_size = 100000
            if mt5:
                try:
                    sym_info = mt5.symbol_info(self.symbol)
                    if sym_info and sym_info.trade_contract_size:
                        contract_size = sym_info.trade_contract_size
                except Exception:
                    pass
            if direction == "long":
                points_pnl = exit_price - entry_price
            else:
                points_pnl = entry_price - exit_price
            estimated_profit = round(points_pnl * self.lot_size * contract_size, 2)

            record = {
                "trade_id": self._trade_counter,
                "deployment_id": self._deployment_id,
                "strategy_id": self._strategy_id,
                "worker_id": self._worker_id,
                "symbol": self.symbol,
                "direction": direction,
                "lot_size": self.lot_size,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "entry_bar": meta.get("entry_bar", self._bar_index),
                "exit_bar": self._bar_index,
                "entry_time": meta.get("entry_time", bar.get("time", 0)),
                "exit_time": bar.get("time", 0),
                "exit_reason": "BROKER_CLOSE_ESTIMATED",
                "sl": meta.get("sl"),
                "tp": meta.get("tp"),
                "ticket": ticket,
                "profit": estimated_profit,
                "commission": 0.0,
                "swap": 0.0,
                "fee": 0.0,
                "net_pnl": estimated_profit,
                "bars_held": max(0, self._bar_index - meta.get("entry_bar", self._bar_index)),
                "mt5_source": False,
            }
            self._ctx._trades.append(record)
            self._report_trade(record)

            # ★ CHART: Buffer exit marker (live estimated)
            with self._chart_marker_lock:
                self._chart_marker_buffer.append({
                    "marker_type": "exit_sl",
                    "time": int(bar.get("time", 0)),
                    "price": exit_price,
                    "bar_index": self._bar_index,
                    "side": direction,
                    "label": "BROKER_CLOSE_ESTIMATED",
                })

            print(f"[TRADE #{self._trade_counter}] ESTIMATED | "
                  f"ticket={ticket} {direction.upper()} "
                  f"entry={entry_price:.5f} exit={exit_price:.5f} "
                  f"profit={estimated_profit:.2f}")
            self._active_trade_meta = None
            self._exec_log.closes_filled += 1
            return

        self._trade_counter += 1
        record = {
            "mt5_ticket": ticket,
            "trade_id": self._trade_counter,
            "deployment_id": self._deployment_id,
            "strategy_id": self._strategy_id,
            "worker_id": self._worker_id,
            "symbol": mt5_record["symbol"],
            "direction": mt5_record["direction"],
            "lot_size": mt5_record["lot_size"],
            "entry_price": mt5_record["entry_price"],
            "exit_price": mt5_record["exit_price"],
            "entry_time": mt5_record["entry_time"],
            "exit_time": mt5_record["exit_time"],
            "profit": mt5_record["profit"],
            "commission": mt5_record["commission"],
            "swap": mt5_record["swap"],
            "fee": mt5_record.get("fee", 0),
            "net_pnl": mt5_record["net_pnl"],
            "exit_reason": mt5_record["exit_reason"],
            "mt5_source": True,
            "entry_bar": meta.get("entry_bar", 0),
            "exit_bar": self._bar_index,
            "bars_held": max(0, self._bar_index - meta.get("entry_bar", 0)),
            "mt5_deal_tickets": mt5_record.get("mt5_deal_tickets", []),
            "mt5_comment": mt5_record.get("mt5_comment", ""),
            "sl": meta.get("sl"),
            "tp": meta.get("tp"),
        }
        self._ctx._trades.append(record)
        self._report_trade(record)

        # ★ CHART: Buffer exit marker (live MT5 confirmed)
        _exit_mt = "exit_tp" if "TP" in mt5_record["exit_reason"] else (
                   "exit_sl" if "SL" in mt5_record["exit_reason"] else "exit_strategy")
        with self._chart_marker_lock:
            self._chart_marker_buffer.append({
                "marker_type": _exit_mt,
                "time": int(bar.get("time", 0)),
                "price": mt5_record["exit_price"],
                "bar_index": self._bar_index,
                "side": mt5_record["direction"],
                "label": mt5_record["exit_reason"],
            })

        print(f"[TRADE #{self._trade_counter}] MT5 CONFIRMED | "
              f"ticket={ticket} {mt5_record['direction'].upper()} "
              f"entry={mt5_record['entry_price']:.5f} "
              f"exit={mt5_record['exit_price']:.5f} "
              f"profit={mt5_record['profit']:.2f} "
              f"comm={mt5_record['commission']:.2f} "
              f"net={mt5_record['net_pnl']:.2f} "
              f"reason={mt5_record['exit_reason']}")
        self._active_trade_meta = None
        self._exec_log.closes_filled += 1

    # =================================================================
    # Process Pending Entry — Backtester Step 1
    # =================================================================

    def _process_pending_entry(self, bar: dict) -> bool:
        if self._pending_signal is None:
            return False

        pos = self._ctx.position
        if pos.has_position:
            print(f"[EXEC] Pending consumed: already in position")
            self._pending_signal = None
            return False

        pending = self._pending_signal
        self._pending_signal = None

        direction = pending["direction"]
        sig = SIGNAL_BUY if direction == "long" else SIGNAL_SELL

        # ★ VALIDATION: fill at bar OPEN (matches backtester exactly)
        # LIVE: fill at current market price (broker fills at market)
        if self._validation_mode:
            entry_estimate = float(bar.get("open", self._current_price or 0))
            if hasattr(self._executor, 'set_next_fill_price'):
                self._executor.set_next_fill_price(entry_estimate)
        else:
            entry_estimate = self._current_price or float(bar.get("close", 0))

        # ── Compute initial SL for order placement ──────────
        initial_sl = None
        sl_mode = pending.get("sl_mode")

        if sl_mode == "fixed":
            pts = float(pending.get("sl_pts", 0) or 0)
            if pts > 0:
                initial_sl = round(
                    (entry_estimate - pts) if direction == "long"
                    else (entry_estimate + pts), 5)
        elif sl_mode == "ma_snapshot":
            ma_val = pending.get("sl_ma_val")
            if ma_val is not None:
                fma = float(ma_val)
                if direction == "long" and fma < entry_estimate:
                    initial_sl = round(fma, 5)
                elif direction == "short" and fma > entry_estimate:
                    initial_sl = round(fma, 5)
        elif pending.get("sl") is not None:
            initial_sl = round(float(pending["sl"]), 5)

        # Validate initial SL direction
        if initial_sl is not None:
            if direction == "long" and initial_sl >= entry_estimate:
                print(f"[EXEC] Pending SKIPPED: Long SL {initial_sl:.5f} >= "
                      f"fill {entry_estimate:.5f} — invalid after fill")
                initial_sl = None
            elif direction == "short" and initial_sl <= entry_estimate:
                print(f"[EXEC] Pending SKIPPED: Short SL {initial_sl:.5f} <= "
                      f"fill {entry_estimate:.5f} — invalid after fill")
                initial_sl = None

        # ★ VALIDATION: If strategy requires SL (has sl field) but SL
        # is invalid at fill price, skip the entire entry.
        if self._validation_mode and pending.get("sl") is not None and initial_sl is None:
            print(f"[EXEC] Pending SKIPPED: SL invalid at bar open "
                  f"{entry_estimate:.5f} — no entry")
            return False

        # ── Place order ─────────────────────────────────────
        comment = pending.get("comment", f"JG_{sig}")

        if sig == SIGNAL_BUY:
            result = self._executor.open_buy(
                sl=initial_sl, tp=None, comment=comment)
        else:
            result = self._executor.open_sell(
                sl=initial_sl, tp=None, comment=comment)

        self._exec_log.log_open(sig, result, initial_sl, None)

        if not result.get("success"):
            print(f"[EXEC] Pending entry FAILED: {result}")
            return False

        fill_price = result.get("price", entry_estimate)

        # ── Recompute SL from actual fill (backtester-exact) ─
        sl_level = None
        risk_pts = None

        if sl_mode == "fixed":
            pts = float(pending.get("sl_pts", 0) or 0)
            if pts > 0:
                sl_level = round(
                    (fill_price - pts) if direction == "long"
                    else (fill_price + pts), 5)
                risk_pts = pts
        elif sl_mode == "ma_snapshot":
            ma_val = pending.get("sl_ma_val")
            if ma_val is not None:
                fma = float(ma_val)
                if direction == "long" and fma < fill_price:
                    sl_level = round(fma, 5)
                    risk_pts = round(abs(fill_price - sl_level), 5)
                elif direction == "short" and fma > fill_price:
                    sl_level = round(fma, 5)
                    risk_pts = round(abs(fill_price - sl_level), 5)
        elif pending.get("sl") is not None:
            sl_level = round(float(pending["sl"]), 5)
            risk_pts = round(abs(fill_price - sl_level), 5)

        # Validate SL from actual fill
        if sl_level is not None:
            if direction == "long" and sl_level >= fill_price:
                sl_level = None
                risk_pts = None
            elif direction == "short" and sl_level <= fill_price:
                sl_level = None
                risk_pts = None

        if risk_pts is not None and risk_pts <= 0:
            sl_level = None
            risk_pts = None

        # ── Compute TP from fill (backtester-exact) ─────────
        tp_level = None
        tp_mode = pending.get("tp_mode")

        if tp_mode == "r_multiple":
            r = float(pending.get("tp_r", 1.0) or 1.0)
            if risk_pts and risk_pts > 0:
                if direction == "long":
                    tp_level = round(fill_price + risk_pts * r, 5)
                else:
                    tp_level = round(fill_price - risk_pts * r, 5)
        elif pending.get("tp") is not None:
            tp_level = round(float(pending["tp"]), 5)

        # Validate TP
        if tp_level is not None:
            if direction == "long" and tp_level <= fill_price:
                tp_level = None
            elif direction == "short" and tp_level >= fill_price:
                tp_level = None

        # ── Modify position with final SL/TP ────────────────
        ticket = result.get("ticket")
        if ticket and (sl_level != initial_sl or tp_level is not None):
            mod_result = self._executor.modify_sl_tp(
                ticket, sl=sl_level, tp=tp_level)
            self._exec_log.log_modify(
                mod_result, sl=sl_level, tp=tp_level)

        print(f"[EXEC] PENDING EXECUTED: {direction.upper()} "
              f"fill={fill_price:.5f} SL={sl_level} TP={tp_level} "
              f"risk={risk_pts} R={pending.get('tp_r')}")

        # ── Store active trade metadata ─────────────────────
        self._active_trade_meta = {
            "entry_bar": self._bar_index,
            "entry_time": bar.get("time", 0),
            "entry_price": fill_price,
            "direction": direction,
            "sl": sl_level,
            "tp": tp_level,
            "ticket": ticket,
            "engine_sl_ma_key": pending.get("engine_sl_ma_key"),
            "engine_tp_ma_key": pending.get("engine_tp_ma_key"),
        }

        self._just_entered_this_bar = True

        # ★ CHART: Buffer entry marker
        with self._chart_marker_lock:
            self._chart_marker_buffer.append({
                "marker_type": "entry_long" if direction == "long" else "entry_short",
                "time": int(bar.get("time", 0)),
                "price": fill_price,
                "bar_index": self._bar_index,
                "side": direction,
                "label": f"{'BUY' if direction == 'long' else 'SELL'} {fill_price:.5f}",
                "metadata": {"sl": sl_level, "tp": tp_level, "ticket": ticket},
            })

        self._signal_count += 1
        self._refresh_position()
        self._report_status()
        return True

    # =================================================================
    # Store Pending Signal — Backtester Step 6
    # =================================================================

    def _store_pending_signal(self, action: dict, bar: dict):
        sig = action.get("signal")
        if sig not in (SIGNAL_BUY, SIGNAL_SELL):
            return

        if self._ctx.position.has_position:
            self._exec_log.log_skip(
                sig, "in position — use CLOSE first")
            return

        direction = "long" if sig == SIGNAL_BUY else "short"

        self._pending_signal = {
            "direction": direction,
            "sl":             action.get("sl"),
            "tp":             action.get("tp"),
            "sl_mode":        action.get("sl_mode"),
            "sl_pts":         action.get("sl_pts"),
            "sl_ma_key":      action.get("sl_ma_key"),
            "sl_ma_val":      action.get("sl_ma_val"),
            "tp_mode":        action.get("tp_mode"),
            "tp_r":           action.get("tp_r"),
            "engine_sl_ma_key": action.get("engine_sl_ma_key"),
            "engine_tp_ma_key": action.get("engine_tp_ma_key"),
            "comment":        action.get("comment", f"JG_{sig}"),
        }

        self._last_signal = action
        self._exec_log.log_signal(
            sig, self._bar_index, self._last_bar_time,
            self._current_price, self._ctx.position)

        print(f"[RUNNER] Signal PENDING: {sig} dir={direction} "
              f"SL={action.get('sl')} tp_mode={action.get('tp_mode')} "
              f"tp_r={action.get('tp_r')} (execute next bar)")

        # ★ CHART: Buffer signal marker
        with self._chart_marker_lock:
            self._chart_marker_buffer.append({
                "marker_type": "signal_buy" if direction == "long" else "signal_sell",
                "time": int(bar.get("time", 0)),
                "price": float(bar.get("close", 0)),
                "bar_index": self._bar_index,
                "side": direction,
                "label": sig,
            })

    # =================================================================
    # _on_new_bar — Backtester 8-Step Loop
    # USED BY BOTH LIVE AND VALIDATION — ZERO LOGIC CHANGES
    # =================================================================

    def _on_new_bar(self, bar: dict):
        self._total_bars_produced += 1
        self._last_bar_time = bar.get("time")

        # ★ CHART: Buffer bar for chart persistence
        with self._chart_bar_lock:
            self._chart_bar_buffer.append({
                "bar_index": self._total_bars_produced - 1,
                "time": int(bar.get("time", 0)),
                "open": float(bar.get("open", 0)),
                "high": float(bar.get("high", 0)),
                "low": float(bar.get("low", 0)),
                "close": float(bar.get("close", 0)),
                "volume": float(bar.get("volume", 0)),
            })

        self._just_entered_this_bar = False

        if self._stop_event.is_set():
            return
        if self._strategy is None or self._ctx is None:
            return

        # Update context
        self._absolute_bar_counter += 1
        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        self._ctx._bar_offset = len(bars_list) - 1
        self._ctx._index = self._absolute_bar_counter
        self._bar_index = self._absolute_bar_counter
        self._ctx._prev_indicators = dict(self._prev_indicators)

        if self._indicator_engine:
            self._indicator_engine.update(bars_list, self._ctx)

        # STEP 1: Process pending entry
        if self._pending_signal is not None:
            self._refresh_position()
            self._process_pending_entry(bar)

        # STEP 2: Refresh position + detect broker close
        self._refresh_position()

        if self._active_trade_meta and not self._ctx.position.has_position:
            self._handle_broker_close(bar)

        # STEP 3: MA cross exits (skip entry bar)
        if (self._ctx.position.has_position
                and not self._just_entered_this_bar):
            if self._check_ma_cross_exit(bar):
                self._refresh_position()

        # Min lookback gate
        min_lb = getattr(self._strategy, "min_lookback", 0) or 0
        if self._absolute_bar_counter < min_lb:
            self._prev_indicators = dict(self._ctx._indicators)
            return

        self._on_bar_call_count += 1

        # STEP 4: Call strategy.on_bar()
        try:
            raw_signal = self._strategy.on_bar(self._ctx)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[RUNNER] on_bar() error: {exc}\n{tb}")
            self._set_state("failed",
                            f"on_bar error: {type(exc).__name__}: {exc}")
            self._stop_event.set()
            return

        action = validate_signal(raw_signal, self._bar_index)
        # ★ FIX: Preserve strategy's extra fields (sl, tp, tp_mode, tp_r, etc.)
        if raw_signal and isinstance(raw_signal, dict):
            for k, v in raw_signal.items():
                if k not in action:
                    action[k] = v
        sig = action.get("signal")

        # STEP 5: Handle CLOSE
        closed_position = False

        if ((sig == SIGNAL_CLOSE or action.get("close"))
                and self._ctx.position.has_position):
            reason = action.get("close_reason", "strategy_close")
            self._close_and_record(reason, bar)
            self._signal_count += 1
            self._last_signal = action
            closed_position = True

        elif sig == SIGNAL_CLOSE_LONG:
            if (self._ctx.position.has_position
                    and self._ctx.position.direction == "long"):
                self._close_and_record("strategy_close_long", bar)
                self._signal_count += 1
                self._last_signal = action
                closed_position = True
            else:
                self._exec_log.log_skip("CLOSE_LONG", "no long position")

        elif sig == SIGNAL_CLOSE_SHORT:
            if (self._ctx.position.has_position
                    and self._ctx.position.direction == "short"):
                self._close_and_record("strategy_close_short", bar)
                self._signal_count += 1
                self._last_signal = action
                closed_position = True
            else:
                self._exec_log.log_skip("CLOSE_SHORT", "no short position")

        if closed_position:
            self._refresh_position()
            # Re-call for flip
            if not self._ctx.position.has_position:
                try:
                    raw2 = self._strategy.on_bar(self._ctx)
                    action2 = validate_signal(raw2, self._bar_index)
                    # ★ FIX: Preserve strategy's extra fields for flip signal
                    if raw2 and isinstance(raw2, dict):
                        for k, v in raw2.items():
                            if k not in action2:
                                action2[k] = v
                    sig2 = action2.get("signal")
                    if sig2 in (SIGNAL_BUY, SIGNAL_SELL):
                        print(f"[RUNNER] Post-CLOSE re-call: {sig2} → "
                              f"PENDING (backtester flip)")
                        self._store_pending_signal(action2, bar)
                    elif ("update_sl" in action2
                          or "update_tp" in action2):
                        self._handle_modify(action2)
                except Exception as exc:
                    print(f"[RUNNER] Re-call on_bar() after CLOSE "
                          f"error: {exc}")

        # STEP 6: Dynamic SL/TP updates
        elif self._ctx.position.has_position and not closed_position:
            if "update_sl" in action or "update_tp" in action:
                self._handle_modify(action)
            if sig == SIGNAL_HOLD or sig is None:
                self._exec_log.log_hold()

        # STEP 7: BUY/SELL → PENDING
        elif sig in (SIGNAL_BUY, SIGNAL_SELL):
            if self._ctx.position.has_position:
                self._exec_log.log_skip(
                    sig, "in position — must CLOSE first or "
                         "use close=True flag")
            else:
                self._store_pending_signal(action, bar)

        elif sig == SIGNAL_HOLD or sig is None:
            self._exec_log.log_hold()

        # Periodic pipeline log
        if self._on_bar_call_count % 50 == 0:
            self._log_pipeline("LIVE_BAR")

        # STEP 8: Store prev indicators
        self._prev_indicators = dict(self._ctx._indicators)

    # ─────────────────────────────────────────────────────────
    # Handle Modify
    # ─────────────────────────────────────────────────────────

    def _handle_modify(self, action: dict):
        pos = self._ctx.position
        if not pos.has_position or not pos.ticket:
            self._exec_log.log_skip("MODIFY", "no position")
            return
        new_sl = action.get("update_sl")
        new_tp = action.get("update_tp")
        result = self._executor.modify_sl_tp(
            pos.ticket, sl=new_sl, tp=new_tp)
        self._exec_log.log_modify(result, sl=new_sl, tp=new_tp)
        self._refresh_position()

    # ─────────────────────────────────────────────────────────
    # ★ CHART: Drain methods (called by worker_agent)
    # ─────────────────────────────────────────────────────────

    def drain_chart_bars(self) -> list:
        """Return and clear buffered bars. Thread-safe."""
        with self._chart_bar_lock:
            bars = list(self._chart_bar_buffer)
            self._chart_bar_buffer.clear()
        return bars

    def drain_chart_markers(self) -> list:
        """Return and clear buffered markers. Thread-safe."""
        with self._chart_marker_lock:
            markers = list(self._chart_marker_buffer)
            self._chart_marker_buffer.clear()
        return markers

    # =================================================================
    # ★ VALIDATION MODE: run_validation()
    #
    # Feeds historical ticks through the EXACT SAME _on_new_bar()
    # that runs live. Uses SimulatedExecutor instead of MT5Executor.
    # Zero logic changes to the execution pipeline.
    # =================================================================

    def run_validation(self, ticks: list, executor, progress_cb=None):
        """
        Run the SAME engine against historical ticks with a SimulatedExecutor.
        _on_new_bar() is IDENTICAL to live — zero logic changes.
        """
        import logging
        _log = logging.getLogger("jinni.execution")
        _log.info(f"[VALIDATION] Starting: {self.strategy_id} on "
                  f"{self.symbol}, {len(ticks):,} ticks")

        # 1 — Load strategy
        strategy_instance, load_error = load_strategy_from_source(
            self.source_code, self.class_name, self.strategy_id)
        if load_error:
            raise RuntimeError(f"Strategy load failed: {load_error}")
        self._strategy = strategy_instance

        # 2 — Use provided SimulatedExecutor
        self._executor = executor

        # 3 — Setup context + indicators (same as live _run_lifecycle)
        params = self._strategy.validate_parameters(self.strategy_parameters)
        self._ctx = StrategyContext(bars=[], params=params)
        self._ctx.state = {}

        indicator_defs = self._strategy.build_indicators(params)
        self._indicator_engine = IndicatorEngine(indicator_defs)
        self._exec_log = ExecutionLogger(self.deployment_id, self.symbol)

        # 4 — Init strategy
        try:
            self._strategy.on_init(self._ctx)
        except Exception as e:
            raise RuntimeError(f"on_init() failed: {e}")

        # 5 — Bar engine with the SAME _on_new_bar callback
        self._bar_engine = RangeBarEngine(
            bar_size_points=self.bar_size_points,
            max_bars=self.max_bars,
            on_bar=self._on_new_bar,   # ← THE SAME CALLBACK AS LIVE
            debug=False,
        )

        # 6 — Reset state vars that _on_new_bar expects
        self._pending_signal = None
        self._on_bar_call_count = 0
        self._signal_count = 0
        self._total_bars_produced = 0
        self._total_ticks_ingested = 0
        self._current_price = 0.0
        self._absolute_bar_counter = -1
        self._prev_indicators = {}
        self._active_trade_meta = None
        self._just_entered_this_bar = False
        self._bar_index = 0
        self._trade_counter = 0

        # 7 — Feed ALL ticks through the SAME pipeline
        total = len(ticks)
        report_every = max(1, total // 50)

        for i, tick in enumerate(ticks):
            if self._stop_event.is_set():
                break

            price = tick["price"]
            self._current_price = price

            # ★ Set price on executor BEFORE bar engine processes
            executor.set_current_price(price)

            self._total_ticks_ingested += 1

            self._bar_engine.process_tick(
                tick["ts"], price, tick.get("volume", 0)
            )

            # ★ Check if broker closed position between ticks
            if self._active_trade_meta and executor.get_open_count() == 0:
                if self._ctx and self._bar_engine.bars:
                    fake_bar = {"time": tick["ts"], "open": price,
                                "high": price, "low": price,
                                "close": price, "volume": 0}
                    self._handle_broker_close(fake_bar)

            if progress_cb and i > 0 and i % report_every == 0:
                pct = (i / total) * 100
                bars = self._bar_engine.total_bars_emitted
                progress_cb(
                    pct,
                    f"Tick {i:,}/{total:,} | "
                    f"{bars} bars | "
                    f"{self._signal_count} signals | "
                    f"{self._trade_counter} trades"
                )

        # 8 — Force-close any open position at end
        if executor.get_open_count() > 0:
            pos = executor.get_position_state()
            if pos.has_position and self._active_trade_meta:
                last_bar = list(self._bar_engine.bars)[-1] if self._bar_engine.bars else {"time": 0, "close": self._current_price}
                self._close_and_record("END_OF_DATA", last_bar)

        _log.info(f"[VALIDATION] Done: {self._total_ticks_ingested:,} ticks, "
                  f"{self._bar_engine.total_bars_emitted} bars, "
                  f"{self._signal_count} signals, "
                  f"{self._trade_counter} trades")

    # =================================================================
    # Lifecycle — start / stop / _run / _run_lifecycle
    # =================================================================

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
            self._set_state("failed",
                            f"{type(exc).__name__}: {exc}")
            try:
                mt5_connector.shutdown_mt5()
            except Exception:
                pass

    def _run_lifecycle(self):
        self._started_at = datetime.now(timezone.utc).isoformat()

        # Phase 1: Load Strategy
        self._set_state("loading_strategy")
        strategy_instance, load_error = load_strategy_from_source(
            self.source_code, self.class_name, self.strategy_id)
        if load_error:
            self._set_state("failed",
                            f"Strategy load failed: {load_error}")
            return
        self._strategy = strategy_instance
        params = self._strategy.validate_parameters(
            self.strategy_parameters)
        self._ctx = StrategyContext(bars=[], params=params)

        indicator_defs = self._strategy.build_indicators(params)
        self._indicator_engine = IndicatorEngine(indicator_defs)

        try:
            self._strategy.on_init(self._ctx)
        except Exception as exc:
            self._set_state(
                "failed",
                f"on_init() failed: {type(exc).__name__}: {exc}")
            return
        print(f"[RUNNER] Strategy loaded: {self.class_name} | "
              f"min_lookback="
              f"{getattr(self._strategy, 'min_lookback', 0)} | "
              f"indicators={len(indicator_defs)} | params={params}")

        # Phase 2: Init MT5
        ok, msg = mt5_connector.init_mt5()
        if not ok:
            self._set_state("failed", f"MT5 init failed: {msg}")
            return
        self._capture_mt5_info()

        self._executor = MT5Executor(
            self.symbol, self.lot_size, self.deployment_id)
        self._exec_log = ExecutionLogger(
            self.deployment_id, self.symbol)

        # Phase 3: Fetch Historical Ticks
        self._set_state("fetching_ticks")
        ticks, tick_err = mt5_connector.fetch_historical_ticks(
            self.symbol, self.tick_lookback_value,
            self.tick_lookback_unit)
        if ticks is None:
            self._set_state("failed",
                            f"Tick fetch failed: {tick_err}")
            mt5_connector.shutdown_mt5()
            return
        if len(ticks) == 0:
            self._set_state("failed",
                            "No ticks returned from MT5.")
            mt5_connector.shutdown_mt5()
            return
        self._total_ticks_ingested = len(ticks)
        self._current_price = ticks[-1]["price"]
        print(f"[RUNNER] Fetched {len(ticks)} historical ticks "
              f"for {self.symbol}")

        if self.debug:
            prices = [t["price"] for t in ticks]
            print(f"[DEBUG] Tick price range: "
                  f"min={min(prices):.5f} "
                  f"max={max(prices):.5f} "
                  f"last={prices[-1]:.5f} "
                  f"spread={max(prices)-min(prices):.5f}")
            grid_snap = round(
                round(prices[-1] / self.bar_size_points)
                * self.bar_size_points, 5)
            print(f"[DEBUG] Grid alignment: "
                  f"bar_size={self.bar_size_points} "
                  f"nearest_grid_level={grid_snap}")

        # Phase 4: Generate Initial Bars
        self._set_state("generating_initial_bars")
        self._bar_engine = RangeBarEngine(
            bar_size_points=self.bar_size_points,
            max_bars=self.max_bars,
            on_bar=None,
            debug=self.debug)
        for tick in ticks:
            self._bar_engine.process_tick(
                tick["ts"], tick["price"], tick["volume"])

        initial_count = self._bar_engine.current_bars_count
        self._total_bars_produced = self._bar_engine.total_bars_emitted
        if self._bar_engine.bars:
            self._last_bar_time = self._bar_engine.bars[-1].get("time")

        print(f"[RUNNER] Initial bars: {initial_count} "
              f"(total emitted: {self._total_bars_produced}) "
              f"(from {len(ticks)} ticks, "
              f"bar_size={self.bar_size_points}pt)")

        if self.debug and initial_count > 0:
            b_first = self._bar_engine.bars[0]
            b_last = self._bar_engine.bars[-1]
            opens = [b["open"] for b in self._bar_engine.bars]
            closes = [b["close"] for b in self._bar_engine.bars]
            all_grid = True
            for v in opens + closes:
                remainder = round(v % self.bar_size_points, 10)
                if (remainder > 1e-8
                        and abs(remainder - self.bar_size_points)
                        > 1e-8):
                    all_grid = False
                    break
            grid_status = ("\u2705 ALL GRID-ALIGNED" if all_grid
                           else "\u26a0\ufe0f SOME OFF-GRID")
            print(f"[DEBUG] BarO={b_first['open']:.5f} "
                  f"C={b_first['close']:.5f}")
            print(f"[DEBUG] Bar[-1]: O={b_last['open']:.5f} "
                  f"C={b_last['close']:.5f}")
            print(f"[DEBUG] Grid check: {grid_status}")

        if initial_count == 0:
            self._set_state(
                "failed",
                f"No bars from {len(ticks)} ticks. "
                f"bar_size_points={self.bar_size_points} "
                f"may be too large for {self.symbol}.")
            mt5_connector.shutdown_mt5()
            return

        self._log_pipeline("INITIAL_BARS")

        # Phase 5: Warm Up
        self._set_state("warming_up")
        bars_list = list(self._bar_engine.bars)
        min_lb = getattr(self._strategy, "min_lookback", 0) or 0
        self._prev_indicators = {}
        warmup_pending = None

        print(f"[WARMUP] {len(bars_list)} bars | "
              f"min_lookback={min_lb}")

        for i in range(len(bars_list)):
            if self._stop_event.is_set():
                return

            warmup_slice = bars_list[:i + 1]
            self._ctx._bars = warmup_slice
            self._ctx._bar_offset = len(warmup_slice) - 1
            self._ctx._index = i
            self._bar_index = i
            self._absolute_bar_counter = i
            self._ctx._prev_indicators = dict(
                self._prev_indicators)

            if self._indicator_engine:
                self._indicator_engine.update(
                    warmup_slice, self._ctx)

            self._refresh_position()

            if warmup_pending is not None:
                self._warmup_signal_count += 1
                print(f"[WARMUP] Pending {warmup_pending['direction']}"
                      f" consumed at bar {i} (NOT executed)")
                warmup_pending = None

            if i < min_lb:
                self._prev_indicators = dict(
                    self._ctx._indicators)
                continue

            self._on_bar_call_count += 1
            try:
                raw_signal = self._strategy.on_bar(self._ctx)
                if raw_signal:
                    s = raw_signal.get("signal")
                    if s in (SIGNAL_BUY, SIGNAL_SELL):
                        direction = ("long" if s == SIGNAL_BUY
                                     else "short")
                        warmup_pending = {
                            "direction": direction,
                            "signal": s,
                        }
                        print(f"[WARMUP] Signal at bar {i}: "
                              f"{s} → pending (consume next bar)")
                    elif s in (SIGNAL_CLOSE, SIGNAL_CLOSE_LONG,
                               SIGNAL_CLOSE_SHORT):
                        self._warmup_signal_count += 1
                        print(f"[WARMUP] Signal at bar {i}: "
                              f"{s} (no position, ignored)")
            except Exception as exc:
                print(f"[WARMUP] on_bar error at bar {i}: {exc}")

            self._prev_indicators = dict(self._ctx._indicators)

        if warmup_pending is not None:
            self._warmup_signal_count += 1
            print(f"[WARMUP] Trailing pending "
                  f"{warmup_pending['direction']} discarded")
            warmup_pending = None

        print(f"[RUNNER] Warmup complete. "
              f"on_bar={self._on_bar_call_count} | "
              f"warmup_signals={self._warmup_signal_count} "
              f"(all skipped) | "
              f"absolute_bar_counter="
              f"{self._absolute_bar_counter}")
        self._log_pipeline("WARMUP_DONE")

        # Phase 6: Live Tick Loop
        self._set_state("running")
        self._bar_engine._on_bar = self._on_new_bar
        live_tick_count = 0

        try:
            for tick in mt5_connector.stream_live_ticks(
                    self.symbol):
                if self._stop_event.is_set():
                    break
                self._total_ticks_ingested += 1
                self._current_price = tick["price"]
                live_tick_count += 1
                self._bar_engine.process_tick(
                    tick["ts"], tick["price"], tick["volume"])
                if live_tick_count % 5000 == 0:
                    self._log_pipeline("LIVE_TICK")
        except Exception as exc:
            if not self._stop_event.is_set():
                tb = traceback.format_exc()
                print(f"[RUNNER] Live loop error: {exc}\n{tb}")
                self._set_state(
                    "failed",
                    f"Live loop error: "
                    f"{type(exc).__name__}: {exc}")
        finally:
            self._log_pipeline("SHUTDOWN")
            mt5_connector.shutdown_mt5()
            self._mt5_state = "disconnected"
            if not self._stop_event.is_set():
                self._set_state("stopped")