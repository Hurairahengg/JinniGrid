"""
JINNI GRID — Simulated Executor
vm/trading/sim_executor.py

Drop-in replacement for MT5Executor used during validation.
Same API — StrategyRunner._on_new_bar() runs IDENTICALLY.
"""

from __future__ import annotations
from trading.execution import PositionState


class SimulatedExecutor:
    """Simulated trade executor matching MT5Executor interface exactly."""

    def __init__(self, symbol: str, lot_size: float, deployment_id: str,
                 point: float, tick_size: float, tick_value: float):
        self.symbol = symbol
        self.lot_size = lot_size
        self.magic = self._make_magic(deployment_id)
        self._point = point
        self._tick_size = tick_size if tick_size > 0 else point
        self._tick_value = tick_value if tick_value > 0 else 1.0
        self._current_price = 0.0
        self._positions: list = []
        self._next_ticket = 100000
        self._filling_mode = 1

        print(f"[SIM-EXEC] Ready: symbol={symbol} lot={lot_size} "
              f"point={point} tick_size={self._tick_size} "
              f"tick_value={self._tick_value}")

    @staticmethod
    def _make_magic(deployment_id: str) -> int:
        h = 0
        for c in deployment_id:
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
        return (h % 900000) + 100000

    # ── Price Feed ──────────────────────────────────────────

    def set_current_price(self, price: float):
        """Update the current market price (call before each tick/bar)."""
        self._current_price = price
        # Update floating PnL on all open positions
        for p in self._positions:
            p["profit"] = self._calc_pnl(p)

    def _calc_pnl(self, pos: dict) -> float:
        entry = pos["price_open"]
        current = self._current_price
        vol = pos["volume"]
        if pos["type"] == 0:  # long
            pts = current - entry
        else:  # short
            pts = entry - current
        if self._tick_size > 0:
            ticks_moved = pts / self._tick_size
            return round(ticks_moved * self._tick_value * vol, 2)
        return 0.0

    # ── Open Orders ─────────────────────────────────────────

    def open_buy(self, sl=None, tp=None, comment="") -> dict:
        return self._open("buy", sl, tp, comment)

    def open_sell(self, sl=None, tp=None, comment="") -> dict:
        return self._open("sell", sl, tp, comment)

    def _open(self, direction: str, sl=None, tp=None, comment="") -> dict:
        ticket = self._next_ticket
        self._next_ticket += 1
        price = self._current_price

        pos = {
            "ticket": ticket,
            "type": 0 if direction == "buy" else 1,
            "volume": self.lot_size,
            "price_open": price,
            "sl": round(float(sl), 5) if sl and sl > 0 else 0,
            "tp": round(float(tp), 5) if tp and tp > 0 else 0,
            "profit": 0.0,
            "symbol": self.symbol,
            "magic": self.magic,
        }
        self._positions.append(pos)

        print(f"[SIM-EXEC] OPENED {direction.upper()} ticket={ticket} "
              f"price={price:.5f} sl={pos['sl']} tp={pos['tp']}")

        return {
            "success": True,
            "ticket": ticket,
            "price": price,
            "volume": self.lot_size,
        }

    # ── Close Orders ────────────────────────────────────────

    def close_position(self, ticket: int, pos_type: int,
                       volume: float, profit: float) -> dict:
        pos = None
        for p in self._positions:
            if p["ticket"] == ticket:
                pos = p
                break
        if pos is None:
            return {"success": False, "ticket": ticket,
                    "error": "Position not found"}

        close_price = self._current_price
        actual_pnl = self._calc_pnl(pos)
        self._positions.remove(pos)

        print(f"[SIM-EXEC] CLOSED ticket={ticket} "
              f"price={close_price:.5f} pnl={actual_pnl:.2f}")

        return {
            "success": True,
            "ticket": ticket,
            "price": close_price,
            "volume": volume,
            "profit": actual_pnl,
        }

    def close_all_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"],
                                    p["volume"], p["profit"])
                for p in list(self._positions)]

    def close_long_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"],
                                    p["volume"], p["profit"])
                for p in list(self._positions) if p["type"] == 0]

    def close_short_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"],
                                    p["volume"], p["profit"])
                for p in list(self._positions) if p["type"] == 1]

    # ── Modify SL/TP ───────────────────────────────────────

    def modify_sl_tp(self, ticket: int, sl=None, tp=None) -> dict:
        for p in self._positions:
            if p["ticket"] == ticket:
                if sl is not None:
                    p["sl"] = round(float(sl), 5)
                if tp is not None:
                    p["tp"] = round(float(tp), 5)
                return {"success": True, "sl": p["sl"], "tp": p["tp"]}
        return {"success": False, "error": f"Position {ticket} not found"}

    # ── Query ───────────────────────────────────────────────

    def get_positions(self) -> list:
        return list(self._positions)

    def get_floating_pnl(self) -> float:
        return sum(p["profit"] for p in self._positions)

    def get_open_count(self) -> int:
        return len(self._positions)

    def get_position_state(self) -> PositionState:
        if not self._positions:
            return PositionState(has_position=False)
        p = self._positions[0]
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

    def get_closed_deal_profit(self, ticket: int) -> dict:
        """No MT5 history in sim — return empty so runner uses estimated path."""
        return {}

    def get_account_info(self) -> dict:
        return {
            "balance": 0.0,
            "equity": self.get_floating_pnl(),
            "margin": 0.0,
            "free_margin": 0.0,
            "profit": self.get_floating_pnl(),
            "currency": "USD",
        }