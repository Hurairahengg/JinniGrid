"""
JINNI Grid — Debug Always-Buy Strategy
debug_always_buy.py

Purpose:
    System pipeline verification ONLY.
    Emits a BUY signal on every single bar close.
    Verifies: tick ingestion -> bar generation -> on_bar() -> signal emission.

Usage:
    Upload this file through the JINNI Grid Strategies page.
    Deploy to any worker with any symbol.
    Check logs for "[DEBUG_STRATEGY]" lines.
    If signals appear in logs + UI, the pipeline works.

Note:
    Execution layer is not yet implemented in JINNI Grid.
    So signals will be LOGGED but no actual MT5 orders will be placed.
    This is expected and correct for current phase.
"""

from base_strategy import BaseStrategy


class DebugAlwaysBuy(BaseStrategy):
    strategy_id = "debug_always_buy"
    name = "Debug Always Buy"
    description = (
        "Pipeline test strategy. Emits BUY on every bar close. "
        "No filters, no indicators. For system verification only."
    )
    version = "1.0"
    min_lookback = 0

    parameters = {
        "lot_size": {
            "type": "number",
            "label": "Lot Size",
            "default": 0.01,
            "min": 0.01,
            "max": 1.0,
            "step": 0.01,
            "help": "Trade size per signal (not executed yet — logged only)",
        },
        "log_every_bar": {
            "type": "boolean",
            "label": "Log Every Bar",
            "default": True,
            "help": "Print detailed log for every bar close",
        },
    }

    def on_init(self, ctx):
        ctx.state["total_bars_seen"] = 0
        ctx.state["total_signals"] = 0
        print("[DEBUG_STRATEGY] on_init() called. Debug Always Buy ready.")

    def on_bar(self, ctx):
        ctx.state["total_bars_seen"] += 1
        ctx.state["total_signals"] += 1

        bar = ctx.bar
        lot = ctx.params.get("lot_size", 0.01)
        verbose = ctx.params.get("log_every_bar", True)

        o = bar.get("open", 0)
        h = bar.get("high", 0)
        l = bar.get("low", 0)
        c = bar.get("close", 0)
        t = bar.get("time", 0)
        v = bar.get("volume", 0)

        if verbose:
            print(
                f"[DEBUG_STRATEGY] Bar #{ctx.index} | "
                f"time={t} O={o:.5f} H={h:.5f} L={l:.5f} C={c:.5f} V={v:.1f} | "
                f"total_bars={ctx.state['total_bars_seen']} "
                f"total_signals={ctx.state['total_signals']} | "
                f"-> BUY"
            )
        else:
            # Still log every 10th bar for visibility
            if ctx.state["total_bars_seen"] % 10 == 0:
                print(
                    f"[DEBUG_STRATEGY] Bar #{ctx.index} | "
                    f"C={c:.5f} | signals={ctx.state['total_signals']} | -> BUY"
                )

        return {
            "signal": "BUY",
            "lot_size": lot,
            "sl": None,
            "tp": None,
            "comment": f"debug_buy_bar_{ctx.index}_t{t}",
        }

    def on_end(self, ctx):
        print(
            f"[DEBUG_STRATEGY] on_end() | "
            f"Total bars: {ctx.state.get('total_bars_seen', 0)} | "
            f"Total signals: {ctx.state.get('total_signals', 0)}"
        )