"""
JINNI GRID — Range Bar Engine
Ported directly from JINNI ZERO range_bars.py RangeBarStreamer.
Same exact 3-state machine logic (startup / bull / bear),
same continuation (1x range) and reversal (2x range) rules.
worker/range_bar_engine.py
Adapted for live streaming: no file I/O, callback-based emission.
"""
from __future__ import annotations
from collections import deque
from typing import Callable, Dict, Optional


def _make_bar(time_: int, open_: float, high_: float, low_: float,
              close_: float, volume_: float) -> dict:
    return {
        "time": int(time_),
        "open": round(open_, 5),
        "high": round(high_, 5),
        "low": round(low_, 5),
        "close": round(close_, 5),
        "volume": round(volume_, 2),
    }


class RangeBarEngine:
    """
    Tick-by-tick range bar builder. Exact same logic as JINNI ZERO.

    Usage:
        engine = RangeBarEngine(bar_size_points=6.0, max_bars=500, on_bar=my_callback)
        engine.process_tick(timestamp, price, volume)  # call per tick
    """

    def __init__(self, bar_size_points: float, max_bars: int = 500,
                 on_bar: Optional[Callable[[dict], None]] = None):
        self.range_size: float = float(bar_size_points)
        self.max_bars: int = max_bars
        self._on_bar: Optional[Callable[[dict], None]] = on_bar

        self.trend: int = 0   # 0 = startup, 1 = bull, -1 = bear
        self.bar: Optional[dict] = None

        # Rolling bar buffer
        self.bars: deque = deque(maxlen=max_bars)

        # Timestamp deduplication (matches JINNI ZERO fix_timestamps)
        self._last_emitted_ts: Optional[int] = None

        # Stats
        self.total_ticks: int = 0
        self.total_bars_emitted: int = 0

    @property
    def current_bars_count(self) -> int:
        return len(self.bars)

    def _emit(self, bar_dict: dict) -> None:
        """Emit a completed bar: dedup timestamp, store in buffer, fire callback."""
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
        """
        Feed a single tick. May emit zero, one, or multiple completed bars.
        Exact same while-True loop from JINNI ZERO RangeBarStreamer.process_tick().
        """
        self.total_ticks += 1

        if self.bar is None:
            self._start_bar(ts, price, volume)
            return

        p = price
        rs = self.range_size

        # Accumulate volume on developing bar
        self.bar["volume"] += volume

        while True:
            o = self.bar["open"]

            # ── STARTUP / NO TREND YET ──────────────────────────
            if self.trend == 0:
                up_target = o + rs
                down_target = o - rs

                if p >= up_target:
                    self.bar["high"] = max(self.bar["high"], up_target)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = up_target

                    self._emit(_make_bar(
                        self.bar["time"], self.bar["open"], self.bar["high"],
                        self.bar["low"], self.bar["close"], self.bar["volume"]
                    ))

                    self.trend = 1
                    new_open = up_target
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                elif p <= down_target:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], down_target)
                    self.bar["close"] = down_target

                    self._emit(_make_bar(
                        self.bar["time"], self.bar["open"], self.bar["high"],
                        self.bar["low"], self.bar["close"], self.bar["volume"]
                    ))

                    self.trend = -1
                    new_open = down_target
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                else:
                    self.bar["high"] = max(self.bar["high"], p)
                    self.bar["low"] = min(self.bar["low"], p)
                    self.bar["close"] = p
                    break

            # ── BULL TREND ──────────────────────────────────────
            elif self.trend == 1:
                cont_target = o + rs
                rev_target = o - (2 * rs)

                if p >= cont_target:
                    self.bar["high"] = max(self.bar["high"], cont_target)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = cont_target

                    self._emit(_make_bar(
                        self.bar["time"], self.bar["open"], self.bar["high"],
                        self.bar["low"], self.bar["close"], self.bar["volume"]
                    ))

                    new_open = cont_target
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                elif p <= rev_target:
                    rev_open = o - rs
                    rev_close = o - (2 * rs)
                    high_ = max(self.bar["high"], o)
                    low_ = min(self.bar["low"], rev_close)

                    self._emit(_make_bar(
                        self.bar["time"], rev_open, high_, low_,
                        rev_close, self.bar["volume"]
                    ))

                    self.trend = -1
                    new_open = rev_close
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                else:
                    self.bar["high"] = max(self.bar["high"], p)
                    self.bar["low"] = min(self.bar["low"], p)
                    self.bar["close"] = p
                    break

            # ── BEAR TREND ──────────────────────────────────────
            elif self.trend == -1:
                cont_target = o - rs
                rev_target = o + (2 * rs)

                if p <= cont_target:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], cont_target)
                    self.bar["close"] = cont_target

                    self._emit(_make_bar(
                        self.bar["time"], self.bar["open"], self.bar["high"],
                        self.bar["low"], self.bar["close"], self.bar["volume"]
                    ))

                    new_open = cont_target
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                elif p >= rev_target:
                    rev_open = o + rs
                    rev_close = o + (2 * rs)
                    high_ = max(self.bar["high"], rev_close)
                    low_ = min(self.bar["low"], o)

                    self._emit(_make_bar(
                        self.bar["time"], rev_open, high_, low_,
                        rev_close, self.bar["volume"]
                    ))

                    self.trend = 1
                    new_open = rev_close
                    self.bar = {"time": ts, "open": new_open, "high": new_open,
                                "low": new_open, "close": new_open, "volume": 0.0}
                    continue

                else:
                    self.bar["high"] = max(self.bar["high"], p)
                    self.bar["low"] = min(self.bar["low"], p)
                    self.bar["close"] = p
                    break

    def reset(self) -> None:
        """Full reset — clears all bars and state."""
        self.trend = 0
        self.bar = None
        self.bars.clear()
        self._last_emitted_ts = None
        self.total_ticks = 0
        self.total_bars_emitted = 0