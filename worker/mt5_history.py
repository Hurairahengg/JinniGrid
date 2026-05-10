"""
worker/mt5_history.py
MT5 Deal History — Source of Truth for Trade Records

Queries MT5 history_deals_get() with retry/delay logic to ensure
complete data after position close.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

log = logging.getLogger("jinni.mt5history")

# Lazy MT5 import (only available on worker VMs)
_mt5 = None


def _get_mt5():
    global _mt5
    if _mt5 is None:
        try:
            import MetaTrader5 as mt5
            _mt5 = mt5
        except ImportError:
            log.error("MetaTrader5 package not available")
            return None
    return _mt5


# ── Deal Reason Mapping ─────────────────────────────────────

def _build_reason_map():
    """Build reason map safely (constants may vary by MT5 version)."""
    mt5 = _get_mt5()
    if mt5 is None:
        return {}
    m = {}
    reason_defs = [
        ("DEAL_REASON_CLIENT", "MANUAL_CLOSE"),
        ("DEAL_REASON_MOBILE", "MANUAL_CLOSE"),
        ("DEAL_REASON_WEB", "MANUAL_CLOSE"),
        ("DEAL_REASON_EXPERT", "STRATEGY_CLOSE"),
        ("DEAL_REASON_SL", "SL_HIT"),
        ("DEAL_REASON_TP", "TP_HIT"),
        ("DEAL_REASON_SO", "STOP_OUT"),
        ("DEAL_REASON_ROLLOVER", "ROLLOVER"),
        ("DEAL_REASON_VMARGIN", "VARIATION_MARGIN"),
        ("DEAL_REASON_SPLIT", "SPLIT"),
    ]
    for attr, label in reason_defs:
        val = getattr(mt5, attr, None)
        if val is not None:
            m[val] = label
    return m


_REASON_MAP = None


def _get_reason_map():
    global _REASON_MAP
    if _REASON_MAP is None:
        _REASON_MAP = _build_reason_map()
    return _REASON_MAP


# ── Core: Fetch Closed Position from MT5 History ────────────

def fetch_closed_position(
    position_ticket: int,
    symbol: str = "",
    max_retries: int = 5,
    retry_delay_ms: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Fetch complete trade record for a closed position from MT5 deal history.

    Uses retry logic because MT5 may take 200ms-1s to update history
    after a position closes.

    Returns dict with all trade fields, or None if history unavailable.
    """
    mt5 = _get_mt5()
    if mt5 is None:
        log.error("MT5 not available — cannot fetch history")
        return None

    log.info(f"[MT5-HIST] Fetching history for position ticket={position_ticket} "
             f"symbol={symbol} (max_retries={max_retries})")

    for attempt in range(1, max_retries + 1):
        # Wait before querying (MT5 needs time to finalize)
        delay_s = retry_delay_ms / 1000.0
        if attempt > 1:
            delay_s = delay_s * attempt  # increasing delay
        time.sleep(delay_s)

        try:
            # Query deals for this position
            # Use a wide time range to ensure we catch it
            from_time = datetime.now(timezone.utc) - timedelta(days=30)
            to_time = datetime.now(timezone.utc) + timedelta(hours=1)

            deals = mt5.history_deals_get(
                from_time,
                to_time,
                position=position_ticket
            )

            if deals is None or len(deals) == 0:
                log.warning(f"[MT5-HIST] Attempt {attempt}/{max_retries}: "
                            f"No deals found for position {position_ticket}")
                continue

            log.info(f"[MT5-HIST] Attempt {attempt}: Found {len(deals)} deals "
                     f"for position {position_ticket}")

            # Parse the deals
            return _parse_position_deals(position_ticket, deals, symbol)

        except Exception as e:
            log.error(f"[MT5-HIST] Attempt {attempt}/{max_retries} failed: {e}")
            continue

    log.error(f"[MT5-HIST] FAILED to fetch history for position {position_ticket} "
              f"after {max_retries} retries")
    return None


def _parse_position_deals(
    position_ticket: int,
    deals,
    symbol: str
) -> Dict[str, Any]:
    """
    Parse MT5 deal objects into a clean trade record.

    A position typically has:
    - 1 IN deal (opening)
    - 1 OUT deal (closing)
    - Sometimes multiple partial fills
    """
    mt5 = _get_mt5()
    reason_map = _get_reason_map()

    # Separate IN and OUT deals
    in_deals = []
    out_deals = []

    for d in deals:
        entry = d.entry  # 0=IN, 1=OUT, 2=INOUT, 3=OUT_BY
        deal_info = {
            "deal_ticket": d.ticket,
            "order_ticket": d.order,
            "time": d.time,
            "type": d.type,  # 0=BUY, 1=SELL
            "entry": entry,
            "symbol": d.symbol,
            "volume": d.volume,
            "price": d.price,
            "profit": d.profit,
            "commission": d.commission,
            "swap": d.swap,
            "fee": getattr(d, 'fee', 0.0) or 0.0,
            "comment": d.comment,
            "reason": getattr(d, 'reason', None),
            "position_id": d.position_id,
        }

        if entry == 0:  # DEAL_ENTRY_IN
            in_deals.append(deal_info)
        elif entry in (1, 2, 3):  # OUT, INOUT, OUT_BY
            out_deals.append(deal_info)

    if not in_deals:
        log.warning(f"[MT5-HIST] No IN deal found for position {position_ticket}")
        # Still try to build from OUT deals alone
    if not out_deals:
        log.warning(f"[MT5-HIST] No OUT deal found for position {position_ticket} "
                    f"— position may still be open")
        return None

    # Use first IN deal for entry, last OUT deal for exit
    in_deal = in_deals[0] if in_deals else None
    out_deal = out_deals[-1]  # last closing deal

    # Aggregate all deal profits/commissions/swaps
    total_profit = sum(d["profit"] for d in deals)
    total_commission = sum(d["commission"] for d in deals)
    total_swap = sum(d["swap"] for d in deals)
    total_fee = sum(d["fee"] for d in deals)

    # Entry info
    entry_price = in_deal["price"] if in_deal else out_deal["price"]
    entry_time = in_deal["time"] if in_deal else out_deal["time"]
    entry_type = in_deal["type"] if in_deal else out_deal["type"]

    # Exit info
    exit_price = out_deal["price"]
    exit_time = out_deal["time"]

    # Direction: IN deal type 0=BUY means LONG, type 1=SELL means SHORT
    # (the OUT deal type is opposite)
    if in_deal:
        direction = "long" if in_deal["type"] == 0 else "short"
    else:
        # Infer from OUT deal (OUT deal type is opposite of position direction)
        direction = "short" if out_deal["type"] == 0 else "long"

    # Volume
    volume = in_deal["volume"] if in_deal else out_deal["volume"]

    # Close reason from MT5 deal reason enum
    close_reason = "UNKNOWN"
    out_reason_code = out_deal.get("reason")
    if out_reason_code is not None:
        close_reason = reason_map.get(out_reason_code, "UNKNOWN")
        log.info(f"[MT5-HIST] Deal reason code={out_reason_code} -> {close_reason}")

    # If MT5 didn't give us a reason, check comment field
    if close_reason == "UNKNOWN" and out_deal.get("comment"):
        comment = out_deal["comment"].lower()
        if "tp" in comment:
            close_reason = "TP_HIT"
        elif "sl" in comment:
            close_reason = "SL_HIT"
        elif "so" in comment:
            close_reason = "STOP_OUT"

    # Net PnL (profit + commission + swap + fee)
    net_pnl = round(total_profit + total_commission + total_swap + total_fee, 2)

    # Symbol
    trade_symbol = in_deal["symbol"] if in_deal else (out_deal["symbol"] or symbol)

    # Build deal ID list for logging
    all_deal_tickets = [d["deal_ticket"] for d in in_deals + out_deals]

    record = {
        "mt5_position_ticket": position_ticket,
        "mt5_deal_tickets": all_deal_tickets,
        "mt5_entry_deal": in_deal["deal_ticket"] if in_deal else None,
        "mt5_exit_deal": out_deal["deal_ticket"],
        "symbol": trade_symbol,
        "direction": direction,
        "volume": volume,
        "lot_size": volume,
        "entry_price": round(entry_price, 8),
        "exit_price": round(exit_price, 8),
        "entry_time": entry_time,  # Unix timestamp
        "exit_time": exit_time,    # Unix timestamp
        "profit": round(total_profit, 2),
        "commission": round(total_commission, 2),
        "swap": round(total_swap, 2),
        "fee": round(total_fee, 2),
        "net_pnl": net_pnl,
        "exit_reason": close_reason,
        "mt5_comment": out_deal.get("comment", ""),
        "mt5_source": True,  # flag: this came from MT5 history
    }

    log.info(
        f"[MT5-HIST] COMPLETE: pos={position_ticket} {direction.upper()} "
        f"{trade_symbol} entry={entry_price:.5f} exit={exit_price:.5f} "
        f"profit={total_profit:.2f} comm={total_commission:.2f} "
        f"swap={total_swap:.2f} net={net_pnl:.2f} reason={close_reason} "
        f"deals={all_deal_tickets}"
    )

    return record


# ── Bulk: Fetch Recent Closed Positions ─────────────────────

def fetch_recent_closed_positions(
    since_hours: int = 24,
    symbol: str = None,
) -> list:
    """
    Fetch all closed positions from the last N hours.
    Useful for reconciliation / backfill.
    """
    mt5 = _get_mt5()
    if mt5 is None:
        return []

    from_time = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    to_time = datetime.now(timezone.utc) + timedelta(hours=1)

    if symbol:
        deals = mt5.history_deals_get(from_time, to_time, symbol=symbol)
    else:
        deals = mt5.history_deals_get(from_time, to_time)

    if deals is None or len(deals) == 0:
        return []

    # Group deals by position_id
    positions = {}
    for d in deals:
        pid = d.position_id
        if pid not in positions:
            positions[pid] = []
        positions[pid].append(d)

    # Build records for completed positions (must have both IN and OUT)
    results = []
    for pid, pos_deals in positions.items():
        has_in = any(d.entry == 0 for d in pos_deals)
        has_out = any(d.entry in (1, 2, 3) for d in pos_deals)
        if has_in and has_out:
            record = _parse_position_deals(pid, pos_deals, symbol or "")
            if record:
                results.append(record)

    log.info(f"[MT5-HIST] Fetched {len(results)} closed positions "
             f"from last {since_hours}h")
    return results