"""
JINNI GRID — Indicator Engine
worker/indicators.py

Ported from JINNI ZERO backtester shared.py / engine_core.py.
Supports: SMA, EMA, WMA, HMA precomputation on range bar series.
Populates ctx.indicators (current bar values) and ctx.ind_series (full series).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


# =============================================================================
# Core MA Functions (matching JINNI ZERO backtester exactly)
# =============================================================================

def precompute_sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    window_sum = sum(values[:period])
    result[period - 1] = window_sum / period
    for i in range(period, n):
        window_sum += values[i] - values[i - period]
        result[i] = window_sum / period
    return result


def precompute_ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    # Seed with SMA
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    k = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        val = values[i] * k + prev * (1 - k)
        result[i] = val
        prev = val
    return result


def precompute_wma(values: List[float], period: int) -> List[Optional[float]]:
    """Weighted Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    denom = period * (period + 1) / 2.0
    for i in range(period - 1, n):
        w_sum = 0.0
        for j in range(period):
            w_sum += values[i - period + 1 + j] * (j + 1)
        result[i] = w_sum / denom
    return result


def precompute_hma(values: List[float], period: int) -> List[Optional[float]]:
    """
    Hull Moving Average — full series.
    HMA(n) = WMA( 2*WMA(n/2) - WMA(n), sqrt(n) )
    """
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result

    half = max(int(period / 2), 1)
    sqrt_p = max(int(math.sqrt(period)), 1)

    wma_half = precompute_wma(values, half)
    wma_full = precompute_wma(values, period)

    # Build diff series: 2*WMA(half) - WMA(full)
    diff = []
    diff_start = None
    for i in range(n):
        if wma_half[i] is not None and wma_full[i] is not None:
            diff.append(2.0 * wma_half[i] - wma_full[i])
            if diff_start is None:
                diff_start = i
        else:
            diff.append(0.0)

    if diff_start is None:
        return result

    # Only use valid portion of diff
    valid_diff = diff[diff_start:]
    hma_of_diff = precompute_wma(valid_diff, sqrt_p)

    for i, val in enumerate(hma_of_diff):
        target_idx = diff_start + i
        if target_idx < n:
            result[target_idx] = val

    return result


def precompute_ma(values: List[float], kind: str, period: int) -> List[Optional[float]]:
    """
    Dispatch to the correct MA precompute function.
    Matches JINNI ZERO backtester shared.py exactly.
    """
    kind_upper = kind.upper()
    if kind_upper == "SMA":
        return precompute_sma(values, period)
    elif kind_upper == "EMA":
        return precompute_ema(values, period)
    elif kind_upper == "WMA":
        return precompute_wma(values, period)
    elif kind_upper == "HMA":
        return precompute_hma(values, period)
    else:
        print(f"[INDICATORS] WARNING: Unknown MA kind '{kind}', falling back to SMA")
        return precompute_sma(values, period)


# =============================================================================
# Source Extraction
# =============================================================================

def _source_values(bars: list, source: str) -> List[float]:
    """Extract price series from bars by source name."""
    if source == "open":
        return [float(b.get("open", 0)) for b in bars]
    elif source == "high":
        return [float(b.get("high", 0)) for b in bars]
    elif source == "low":
        return [float(b.get("low", 0)) for b in bars]
    else:
        return [float(b.get("close", 0)) for b in bars]


def precompute_indicator_series(bars: list, spec: dict) -> List[Optional[float]]:
    """
    Precompute a full indicator series from bars + spec.
    Spec format (from strategy.build_indicators()):
        {"key": "hma_200", "kind": "HMA", "period": 200, "source": "close"}
    """
    kind = spec.get("kind", "SMA").upper()
    source = spec.get("source", "close")
    period = int(spec.get("period", 14))
    values = _source_values(bars, source)
    return precompute_ma(values, kind, period)


# =============================================================================
# Indicator Engine (live — recomputes on every new bar)
# =============================================================================

class IndicatorEngine:
    """
    Manages indicator computation for live trading.

    On each new bar:
      1. Recomputes full series for all declared indicators
      2. Updates ctx.indicators with current-bar values
      3. Updates ctx.ind_series with full series (for strategy lookback)

    This matches backtester behavior where indicators are precomputed
    over the full bar array. For live, we recompute on the growing
    bar deque — slightly less efficient but guarantees identical values.
    """

    def __init__(self, indicator_defs: List[Dict[str, Any]]):
        self._defs = indicator_defs
        self._warned: set = set()

        if self._defs:
            keys = [d["key"] for d in self._defs]
            print(f"[INDICATORS] Registered {len(self._defs)} indicators: {keys}")
        else:
            print("[INDICATORS] No indicators requested by strategy.")

    def update(self, bars: list, ctx) -> None:
        """Recompute all indicators from current bar list and update ctx."""
        for defn in self._defs:
            key = defn["key"]
            kind = defn.get("kind", "SMA").upper()
            source = defn.get("source", "close")
            period = int(defn.get("period", 14))

            values = _source_values(bars, source)
            series = precompute_ma(values, kind, period)

            # Store full series
            ctx._ind_series[key] = series

            # Store current value (last bar)
            if series and len(series) > 0:
                ctx._indicators[key] = series[-1]
            else:
                ctx._indicators[key] = None

    def get_series_at(self, indicator_store: dict, key: str, index: int) -> Optional[float]:
        """Get indicator value at a specific bar index."""
        series = indicator_store.get(key)
        if series is None or index < 0 or index >= len(series):
            return None
        return series[index]