"""
JINNI GRID — Trade Execution Layer + Logger
worker/execution.py

Handles:
  - Real MT5 order execution (BUY/SELL/CLOSE)
  - Position querying (filtered by magic number)
  - SL/TP modification
  - R-multiple TP computation from fill price
  - MA-snapshot SL computation
  - MA-cross exit monitoring
  - Dedicated [EXEC] execution logger
  - Trade record building for ctx._trades
  - Signal validation (ported from JINNI ZERO engine_core.py)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Signal Constants
# =============================================================================

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_CLOSE = "CLOSE"
SIGNAL_CLOSE_LONG = "CLOSE_LONG"
SIGNAL_CLOSE_SHORT = "CLOSE_SHORT"
VALID_SIGNALS = {
    SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE,
    SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT, None,
}


# =============================================================================
# Signal Validation (ported from JINNI ZERO engine_core.py)
# =============================================================================

def validate_signal(raw, bar_index: int) -> dict:
    """
    Validate and normalize a raw signal dict from strategy.on_bar().
    Matches JINNI ZERO backtester validate_signal() exactly.
    """
    if raw is None:
        return {"signal": "HOLD"}
    if not isinstance(raw, dict):
        print(f"[EXEC] WARNING: Bar {bar_index}: strategy returned "
              f"{type(raw).__name__}, expected dict or None")
        return {"signal": "HOLD"}

    sig = raw.get("signal")
    if sig is not None:
        sig = str(sig).upper()
    if sig not in VALID_SIGNALS:
        print(f"[EXEC] WARNING: Bar {bar_index}: invalid signal '{sig}'")
        return {"signal": "HOLD"}

    out = {"signal": sig or "HOLD"}

    # Direct SL/TP
    if raw.get("sl") is not None:
        out["sl"] = float(raw["sl"])
    if raw.get("tp") is not None:
        out["tp"] = float(raw["tp"])

    # Engine-computed SL/TP fields
    for key in ("sl_mode", "sl_pts", "sl_ma_key", "sl_ma_val",
                "tp_mode", "tp_r"):
        if raw.get(key) is not None:
            if key in ("sl_mode", "sl_ma_key", "tp_mode"):
                out[key] = raw[key]
            else:
                out[key] = float(raw[key])

    # Engine-level MA cross exit keys
    if raw.get("engine_sl_ma_key") is not None:
        out["engine_sl_ma_key"] = str(raw["engine_sl_ma_key"])
    if raw.get("engine_tp_ma_key") is not None:
        out["engine_tp_ma_key"] = str(raw["engine_tp_ma_key"])

    # CLOSE signal
    if out["signal"] == "CLOSE":
        out["close"] = True
        out["close_reason"] = str(raw.get("close_reason", "strategy_close"))
    elif raw.get("close"):
        out["close"] = True
        out["close_reason"] = str(raw.get("close_reason", "strategy_close"))

    # Dynamic SL/TP updates
    if raw.get("update_sl") is not None:
        out["update_sl"] = float(raw["update_sl"])
    if raw.get("update_tp") is not None:
        out["update_tp"] = float(raw["update_tp"])

    # Comment
    if raw.get("comment"):
        out["comment"] = str(raw["comment"])

    return out


# =============================================================================
# SL/TP Computation Helpers
# =============================================================================

def compute_sl(signal: dict, entry_price: float, direction: str) -> Optional[float]:
    """
    Compute SL price from signal fields.
    Supports: direct sl, sl_mode=ma_snapshot, sl_mode=fixed.
    """
    sl_mode = signal.get("sl_mode")

    if sl_mode == "ma_snapshot":
        ma_val = signal.get("sl_ma_val")
        if ma_val is not None:
            ma_val = float(ma_val)
            if direction == "long" and ma_val < entry_price:
                return round(ma_val, 5)
            elif direction == "short" and ma_val > entry_price:
                return round(ma_val, 5)
        return None

    if sl_mode == "fixed":
        pts = float(signal.get("sl_pts", 0))
        if pts > 0:
            if direction == "long":
                return round(entry_price - pts, 5)
            else:
                return round(entry_price + pts, 5)
        return None

    # Direct SL
    if signal.get("sl") is not None:
        return float(signal["sl"])

    return None


def compute_tp(signal: dict, entry_price: float, sl_price: Optional[float],
               direction: str) -> Optional[float]:
    """
    Compute TP price from signal fields.
    Supports: direct tp, tp_mode=r_multiple.
    """
    tp_mode = signal.get("tp_mode")

    if tp_mode == "r_multiple":
        r = float(signal.get("tp_r", 1.0))
        if sl_price is not None:
            risk = abs(entry_price - sl_price)
            if risk > 0:
                if direction == "long":
                    return round(entry_price + risk * r, 5)
                else:
                    return round(entry_price - risk * r, 5)
        return None

    # Direct TP
    if signal.get("tp") is not None:
        return float(signal["tp"])

    return None


# =============================================================================
# Position State
# =============================================================================

@dataclass
class PositionState:
    has_position: bool = False
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    size: Optional[float] = None
    ticket: Optional[int] = None
    profit: Optional[float] = None
    entry_bar: Optional[int] = None
    # Backtester-compatible fields
    bars_held: int = 0
    unrealized_pts: float = 0.0
    unrealized_pnl: float = 0.0
    mae: float = 0.0
    mfe: float = 0.0

    @property
    def sl_level(self) -> Optional[float]:
        """Backtester-compatible alias for sl."""
        return self.sl

    @property
    def tp_level(self) -> Optional[float]:
        """Backtester-compatible alias for tp."""
        return self.tp


# =============================================================================
# Execution Logger
# =============================================================================

class ExecutionLogger:
    """Dedicated [EXEC] logger for all trade decisions."""

    def __init__(self, deployment_id: str, symbol: str):
        self.deployment_id = deployment_id
        self.symbol = symbol
        self.buys_attempted = 0
        self.buys_filled = 0
        self.sells_attempted = 0
        self.sells_filled = 0
        self.closes_attempted = 0
        self.closes_filled = 0
        self.holds = 0
        self.skips = 0
        self.rejections = 0
        self.modifications = 0
        self.ma_cross_exits = 0

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

    def _pos_str(self, pos: PositionState) -> str:
        if not pos or not pos.has_position:
            return "FLAT"
        d = (pos.direction or "?").upper()
        p = f"@{pos.entry_price:.5f}" if pos.entry_price else ""
        s = f"x{pos.size}" if pos.size else ""
        pnl = f" pnl={pos.profit:.2f}" if pos.profit is not None else ""
        return f"{d}{p}{s}{pnl}"

    def log_signal(self, action: str, bar_idx: int, bar_time, price,
                   pos: PositionState):
        print(
            f"[EXEC] {self._ts()} | {action} | {self.symbol} | "
            f"bar={bar_idx} t={bar_time} | price={price} | "
            f"pos={self._pos_str(pos)}"
        )

    def log_open(self, direction: str, result: dict, sl=None, tp=None):
        if direction == "BUY":
            self.buys_attempted += 1
        else:
            self.sells_attempted += 1

        if result.get("success"):
            if direction == "BUY":
                self.buys_filled += 1
            else:
                self.sells_filled += 1
            print(
                f"[EXEC]   -> OPENED {direction} | "
                f"ticket={result.get('ticket')} "
                f"price={result.get('price', 0):.5f} "
                f"vol={result.get('volume', 0)} "
                f"sl={sl} tp={tp}"
            )
        else:
            self.rejections += 1
            print(
                f"[EXEC]   -> REJECTED {direction} | "
                f"error={result.get('error', 'unknown')}"
            )

    def log_close(self, results: list, reason: str = "signal"):
        self.closes_attempted += 1
        for r in results:
            if r.get("success"):
                self.closes_filled += 1
                print(
                    f"[EXEC]   -> CLOSED ticket={r.get('ticket')} "
                    f"price={r.get('price', 0):.5f} "
                    f"profit={r.get('profit', 0):.2f} "
                    f"reason={reason}"
                )
            else:
                self.rejections += 1
                print(
                    f"[EXEC]   -> CLOSE FAILED ticket={r.get('ticket', '?')} "
                    f"error={r.get('error', 'unknown')}"
                )

    def log_skip(self, action: str, reason: str):
        self.skips += 1
        print(f"[EXEC]   -> SKIPPED {action} | reason={reason}")

    def log_hold(self):
        self.holds += 1

    def log_modify(self, result: dict, sl=None, tp=None):
        self.modifications += 1
        if result.get("success"):
            print(f"[EXEC]   -> MODIFIED sl={sl} tp={tp}")
        else:
            print(f"[EXEC]   -> MODIFY FAILED error={result.get('error')}")

    def log_ma_cross_exit(self, ma_key: str, direction: str, ma_val: float,
                          close_price: float):
        self.ma_cross_exits += 1
        print(
            f"[EXEC]   -> MA CROSS EXIT | {ma_key}={ma_val:.5f} "
            f"close={close_price:.5f} dir={direction}"
        )

    def get_stats(self) -> dict:
        return {
            "buys_attempted": self.buys_attempted,
            "buys_filled": self.buys_filled,
            "sells_attempted": self.sells_attempted,
            "sells_filled": self.sells_filled,
            "closes_attempted": self.closes_attempted,
            "closes_filled": self.closes_filled,
            "holds": self.holds,
            "skips": self.skips,
            "rejections": self.rejections,
            "modifications": self.modifications,
            "ma_cross_exits": self.ma_cross_exits,
        }


# =============================================================================
# MT5 Trade Executor
# =============================================================================

def _import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


class MT5Executor:
    """Handles all real MT5 order execution."""

    def __init__(self, symbol: str, lot_size: float, deployment_id: str):
        self.symbol = symbol
        self.lot_size = lot_size
        self.magic = self._make_magic(deployment_id)
        self._mt5 = _import_mt5()
        self._filling_mode = None

        if self._mt5:
            self._filling_mode = self._detect_filling()
            print(
                f"[EXECUTOR] Ready: symbol={symbol} lot={lot_size} "
                f"magic={self.magic} filling={self._filling_mode}"
            )
        else:
            print("[EXECUTOR] WARNING: MT5 not available. Execution disabled.")

    @staticmethod
    def _make_magic(deployment_id: str) -> int:
        h = 0
        for c in deployment_id:
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
        return (h % 900000) + 100000

    def _detect_filling(self) -> int:
        mt5 = self._mt5
        info = mt5.symbol_info(self.symbol)
        if info is None:
            return 1
        fm = info.filling_mode
        if fm & 2:
            return 1  # IOC
        elif fm & 1:
            return 0  # FOK
        else:
            return 2  # RETURN

    # ── Open Orders ─────────────────────────────────────────

    def open_buy(self, sl=None, tp=None, comment="") -> dict:
        return self._open_order("buy", sl, tp, comment)

    def open_sell(self, sl=None, tp=None, comment="") -> dict:
        return self._open_order("sell", sl, tp, comment)

    def _open_order(self, direction: str, sl=None, tp=None,
                    comment="") -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "error": "MT5 not available"}

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return {"success": False,
                    "error": f"No tick data for {self.symbol}"}

        is_buy = direction == "buy"
        price = tick.ask if is_buy else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot_size,
            "type": order_type,
            "price": price,
            "deviation": 30,
            "magic": self.magic,
            "comment": comment or f"JG_{direction}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode,
        }

        if sl is not None and sl > 0:
            request["sl"] = round(float(sl), 5)
        if tp is not None and tp > 0:
            request["tp"] = round(float(tp), 5)

        print(f"[EXECUTOR] Sending {direction.upper()}: {request}")
        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            return {"success": False, "error": f"order_send returned None: {err}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "error": f"retcode={result.retcode} comment={result.comment}",
                "retcode": result.retcode,
            }

        return {
            "success": True,
            "ticket": result.order,
            "price": result.price,
            "volume": result.volume,
        }

    # ── Close Orders ────────────────────────────────────────

    def close_position(self, ticket: int, pos_type: int,
                       volume: float, profit: float) -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "ticket": ticket,
                    "error": "MT5 not available"}

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return {"success": False, "ticket": ticket,
                    "error": f"No tick for {self.symbol}"}

        is_long = (pos_type == 0)
        close_price = tick.bid if is_long else tick.ask
        close_type = mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": volume,
            "type": close_type,
            "position": ticket,
            "price": close_price,
            "deviation": 30,
            "magic": self.magic,
            "comment": "JG_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode,
        }

        print(f"[EXECUTOR] Closing ticket={ticket}: {request}")
        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            return {"success": False, "ticket": ticket,
                    "error": f"order_send None: {err}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False, "ticket": ticket,
                "error": f"retcode={result.retcode} comment={result.comment}",
            }

        return {
            "success": True, "ticket": ticket,
            "price": result.price, "volume": volume,
            "profit": profit,
        }

    def close_all_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions()]

    def close_long_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions() if p["type"] == 0]

    def close_short_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions() if p["type"] == 1]

    # ── Modify SL/TP ────────────────────────────────────────

    def modify_sl_tp(self, ticket: int, sl=None, tp=None) -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "error": "MT5 not available"}

        positions = mt5.positions_get(ticket=ticket)
        if positions is None or len(positions) == 0:
            return {"success": False, "error": f"Position {ticket} not found"}

        pos = positions[0]
        new_sl = round(float(sl), 5) if sl is not None else pos.sl
        new_tp = round(float(tp), 5) if tp is not None else pos.tp

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp,
        }

        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "error": "order_send returned None"}
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False,
                    "error": f"retcode={result.retcode} comment={result.comment}"}
        return {"success": True, "sl": new_sl, "tp": new_tp}

    # ── Query ───────────────────────────────────────────────

    def get_positions(self) -> list:
        mt5 = self._mt5
        if mt5 is None:
            return []
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []
        result = []
        for p in positions:
            if p.magic != self.magic:
                continue
            result.append({
                "ticket": p.ticket, "type": p.type,
                "volume": p.volume, "price_open": p.price_open,
                "sl": p.sl, "tp": p.tp, "profit": p.profit,
                "symbol": p.symbol, "magic": p.magic,
            })
        return result

    def get_floating_pnl(self) -> float:
        return sum(p["profit"] for p in self.get_positions())

    def get_open_count(self) -> int:
        return len(self.get_positions())

    def get_position_state(self) -> PositionState:
        positions = self.get_positions()
        if not positions:
            return PositionState(has_position=False)
        p = positions[0]
        return PositionState(
            has_position=True,
            direction="long" if p["type"] == 0 else "short",
            entry_price=p["price_open"],
            sl=p["sl"] if p["sl"] != 0 else None,
            tp=p["tp"] if p["tp"] != 0 else None,
            size=p["volume"],
            ticket=p["ticket"],
            profit=p["profit"],
        )


# =============================================================================
# Trade Record Builder (for ctx._trades)
# =============================================================================

def build_trade_record(
    trade_id: int,
    direction: str,
    entry_price: float,
    entry_bar: int,
    entry_time: int,
    exit_price: float,
    exit_bar: int,
    exit_time: int,
    exit_reason: str,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    lot_size: float = 0.01,
    ticket: Optional[int] = None,
    profit: Optional[float] = None,
) -> dict:
    """
    Build a trade record compatible with JINNI ZERO backtester format.
    Strategies use ctx.trades for gating logic, no-reuse, etc.
    """
    points_pnl = (exit_price - entry_price) if direction == "long" \
                 else (entry_price - exit_price)

    return {
        "id": trade_id,
        "direction": direction,
        "entry_bar": entry_bar,
        "entry_time": entry_time,
        "entry_price": round(entry_price, 5),
        "exit_bar": exit_bar,
        "exit_time": exit_time,
        "exit_price": round(exit_price, 5),
        "exit_reason": exit_reason,
        "sl_level": sl,
        "tp_level": tp,
        "lot_size": lot_size,
        "ticket": ticket,
        "points_pnl": round(points_pnl, 5),
        "profit": profit,
        "bars_held": exit_bar - entry_bar,
    }