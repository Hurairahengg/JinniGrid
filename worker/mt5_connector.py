"""
JINNI GRID — MT5 Connector
Thin wrapper around MetaTrader5 Python package.
Handles init, tick fetch, and live tick streaming.
Does NOT invent broker/account/path details.
worker/mt5_connector.py
"""
from __future__ import annotations
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple


def _import_mt5():
    """Lazy import — fails clearly if MetaTrader5 not installed."""
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


def init_mt5() -> Tuple[bool, str]:
    """
    Initialize MT5 terminal connection.
    Uses whatever MT5 terminal is installed/running on this machine.
    Does NOT specify path, login, server, or password.
    """
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


def fetch_historical_ticks(
    symbol: str,
    lookback_value: int,
    lookback_unit: str,
) -> Tuple[Optional[list], str]:
    """
    Fetch historical ticks from MT5.

    Returns:
        (list_of_tick_dicts, "ok") on success
        (None, error_message) on failure

    Each tick dict: {"ts": int, "price": float, "volume": float}
    """
    mt5 = _import_mt5()
    if mt5 is None:
        return None, "MetaTrader5 package not installed."

    # Calculate from-time
    now = datetime.now(timezone.utc)
    if lookback_unit == "minutes":
        from_time = now - timedelta(minutes=lookback_value)
    elif lookback_unit == "hours":
        from_time = now - timedelta(hours=lookback_value)
    elif lookback_unit == "days":
        from_time = now - timedelta(days=lookback_value)
    else:
        return None, f"Invalid lookback_unit: {lookback_unit}"

    # Validate symbol
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return None, f"Symbol '{symbol}' not found in MT5."
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            return None, f"Failed to enable symbol '{symbol}' in MT5."

    print(f"[MT5] Fetching ticks: {symbol} from {from_time.isoformat()} to {now.isoformat()}")

    ticks = mt5.copy_ticks_range(symbol, from_time, now, mt5.COPY_TICKS_ALL)

    if ticks is None or len(ticks) == 0:
        err = mt5.last_error()
        return None, f"No ticks returned for {symbol}. MT5 error: {err}"

    result = []
    for t in ticks:
        # MT5 tick: time, bid, ask, last, volume, ...
        # Use bid as price (most common for FX), fallback to last
        price = t.bid if t.bid > 0 else (t.last if t.last > 0 else t.ask)
        if price <= 0:
            continue
        result.append({
            "ts": int(t.time),
            "price": float(price),
            "volume": float(t.volume) if t.volume else 0.0,
        })

    print(f"[MT5] Got {len(result)} ticks for {symbol}")
    return result, "ok"


def stream_live_ticks(symbol: str, poll_interval: float = 0.05):
    """
    Generator that yields new ticks by polling MT5.
    Yields: {"ts": int, "price": float, "volume": float}

    Uses copy_ticks_from() with a moving cursor.
    """
    mt5 = _import_mt5()
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed.")

    # Start cursor from now
    cursor_time = datetime.now(timezone.utc)
    last_tick_time = 0

    while True:
        ticks = mt5.copy_ticks_from(symbol, cursor_time, 1000, mt5.COPY_TICKS_ALL)

        if ticks is not None and len(ticks) > 0:
            for t in ticks:
                if t.time_msc <= last_tick_time:
                    continue
                last_tick_time = t.time_msc

                price = t.bid if t.bid > 0 else (t.last if t.last > 0 else t.ask)
                if price <= 0:
                    continue

                yield {
                    "ts": int(t.time),
                    "price": float(price),
                    "volume": float(t.volume) if t.volume else 0.0,
                }

            # Move cursor forward
            last_t = ticks[-1]
            cursor_time = datetime.fromtimestamp(last_t.time, tz=timezone.utc)

        time.sleep(poll_interval)