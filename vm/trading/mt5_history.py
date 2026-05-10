"""
worker/mt5_history.py
MT5 Deal History — Source of Truth for Trade Records

Converts MT5 named-tuple results to plain dicts immediately
to prevent 'tuple indices must be integers' errors.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

log = logging.getLogger("jinni.mt5history")

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


# ── Safe conversion: MT5 deal object → plain dict ───────────

def _deal_to_dict(deal) -> dict:
    """
    Convert an MT5 TradeDeal object (named tuple / numpy row) to a plain dict.
    Uses getattr() for safety — works regardless of MT5 version.
    """
    return {
        "ticket": int(getattr(deal, "ticket", 0)),
        "order": int(getattr(deal, "order", 0)),
        "time": int(getattr(deal, "time", 0)),
        "time_msc": int(getattr(deal, "time_msc", 0)),
        "type": int(getattr(deal, "type", 0)),
        "entry": int(getattr(deal, "entry", 0)),
        "magic": int(getattr(deal, "magic", 0)),
        "position_id": int(getattr(deal, "position_id", 0)),
        "reason": int(getattr(deal, "reason", -1)),
        "volume": float(getattr(deal, "volume", 0.0)),
        "price": float(getattr(deal, "price", 0.0)),
        "commission": float(getattr(deal, "commission", 0.0)),
        "swap": float(getattr(deal, "swap", 0.0)),
        "profit": float(getattr(deal, "profit", 0.0)),
        "fee": float(getattr(deal, "fee", 0.0) or 0.0),
        "symbol": str(getattr(deal, "symbol", "")),
        "comment": str(getattr(deal, "comment", "")),
        "external_id": str(getattr(deal, "external_id", "")),
    }


# ── Deal Reason Mapping ─────────────────────────────────────

_REASON_MAP = None


def _get_reason_map() -> dict:
    global _REASON_MAP
    if _REASON_MAP is not None:
        return _REASON_MAP

    mt5 = _get_mt5()
    if mt5 is None:
        return {}

    _REASON_MAP = {}
    defs = [
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
    for attr, label in defs:
        val = getattr(mt5, attr, None)
        if val is not None:
            _REASON_MAP[int(val)] = label

    log.info(f"[MT5-HIST] Reason map loaded: {_REASON_MAP}")
    return _REASON_MAP


# ── Core: Fetch Closed Position ─────────────────────────────

def fetch_closed_position(
    position_ticket: int,
    symbol: str = "",
    max_retries: int = 5,
    retry_delay_ms: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Fetch complete trade record for a closed position from MT5 deal history.
    Retries with increasing delay because MT5 needs time to finalize history.
    """
    mt5 = _get_mt5()
    if mt5 is None:
        log.error("[MT5-HIST] MT5 module not available")
        return None

    position_ticket = int(position_ticket)
    log.info(f"[MT5-HIST] Fetching history: ticket={position_ticket} symbol={symbol}")

    for attempt in range(1, max_retries + 1):
        # Increasing delay: 300ms, 600ms, 900ms, 1200ms, 1500ms
        delay_s = (retry_delay_ms * attempt) / 1000.0
        time.sleep(delay_s)

        try:
            from_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
            to_time = datetime.now(timezone.utc) + timedelta(hours=1)

            raw_deals = mt5.history_deals_get(
                from_time, to_time,
                position=position_ticket
            )

            if raw_deals is None:
                err = mt5.last_error()
                log.warning(
                    f"[MT5-HIST] Attempt {attempt}/{max_retries}: "
                    f"history_deals_get returned None. "
                    f"MT5 error: {err}"
                )
                continue

            if len(raw_deals) == 0:
                log.warning(
                    f"[MT5-HIST] Attempt {attempt}/{max_retries}: "
                    f"0 deals for position {position_ticket}"
                )
                continue

            # Convert ALL deals to plain dicts immediately
            deals = []
            for i, raw in enumerate(raw_deals):
                try:
                    d = _deal_to_dict(raw)
                    deals.append(d)
                    log.debug(
                        f"[MT5-HIST]   deal[{i}]: ticket={d['ticket']} "
                        f"entry={d['entry']} type={d['type']} "
                        f"price={d['price']} profit={d['profit']} "
                        f"commission={d['commission']} reason={d['reason']}"
                    )
                except Exception as conv_err:
                    log.error(
                        f"[MT5-HIST] Failed to convert deal[{i}]: {conv_err} "
                        f"raw type={type(raw)} raw={raw}"
                    )
                    continue

            if not deals:
                log.warning(
                    f"[MT5-HIST] Attempt {attempt}: {len(raw_deals)} raw deals "
                    f"but 0 converted successfully"
                )
                continue

            log.info(
                f"[MT5-HIST] Attempt {attempt}: {len(deals)} deals "
                f"for position {position_ticket}"
            )

            return _build_trade_record(position_ticket, deals, symbol)

        except Exception as e:
            log.error(
                f"[MT5-HIST] Attempt {attempt}/{max_retries} exception: "
                f"{type(e).__name__}: {e}"
            )
            continue

    log.error(
        f"[MT5-HIST] FAILED after {max_retries} retries "
        f"for position {position_ticket}"
    )
    return None


# ── Build trade record from parsed deal dicts ───────────────

def _build_trade_record(
    position_ticket: int,
    deals: List[dict],
    symbol: str
) -> Optional[Dict[str, Any]]:
    """
    Build a clean trade record from a list of deal dicts.
    All deals are already plain dicts (safe to use ["key"]).
    """
    reason_map = _get_reason_map()

    # Separate IN (entry=0) and OUT (entry=1,2,3) deals
    in_deals = [d for d in deals if d["entry"] == 0]
    out_deals = [d for d in deals if d["entry"] in (1, 2, 3)]

    if not in_deals:
        log.warning(
            f"[MT5-HIST] No IN deal for position {position_ticket}. "
            f"Deal entries: {[d['entry'] for d in deals]}"
        )
    if not out_deals:
        log.warning(
            f"[MT5-HIST] No OUT deal for position {position_ticket} "
            f"— may still be open"
        )
        return None

    in_deal = in_deals[0] if in_deals else None
    out_deal = out_deals[-1]

    # Aggregate financials across ALL deals for this position
    total_profit = round(sum(d["profit"] for d in deals), 2)
    total_commission = round(sum(d["commission"] for d in deals), 2)
    total_swap = round(sum(d["swap"] for d in deals), 2)
    total_fee = round(sum(d["fee"] for d in deals), 2)
    net_pnl = round(total_profit + total_commission + total_swap + total_fee, 2)

    # Entry info
    entry_price = in_deal["price"] if in_deal else out_deal["price"]
    entry_time = in_deal["time"] if in_deal else out_deal["time"]

    # Exit info
    exit_price = out_deal["price"]
    exit_time = out_deal["time"]

    # Direction: IN deal type 0=BUY→long, 1=SELL→short
    if in_deal:
        direction = "long" if in_deal["type"] == 0 else "short"
    else:
        # OUT deal type is opposite of position direction
        direction = "short" if out_deal["type"] == 0 else "long"

    volume = in_deal["volume"] if in_deal else out_deal["volume"]
    trade_symbol = (in_deal or out_deal)["symbol"] or symbol

    # Close reason from MT5 reason enum
    close_reason = "UNKNOWN"
    out_reason_code = out_deal["reason"]
    if out_reason_code >= 0:
        close_reason = reason_map.get(out_reason_code, "UNKNOWN")
        log.info(
            f"[MT5-HIST] Reason code={out_reason_code} -> {close_reason}"
        )

    # Fallback: check deal comment
    if close_reason in ("UNKNOWN", "STRATEGY_CLOSE"):
        comment = out_deal["comment"].lower()
        if "tp" in comment:
            close_reason = "TP_HIT"
        elif "sl" in comment:
            close_reason = "SL_HIT"
        elif "so" in comment:
            close_reason = "STOP_OUT"

    all_tickets = [d["ticket"] for d in in_deals + out_deals]

    record = {
        "mt5_position_ticket": position_ticket,
        "mt5_deal_tickets": all_tickets,
        "mt5_entry_deal": in_deal["ticket"] if in_deal else None,
        "mt5_exit_deal": out_deal["ticket"],
        "symbol": trade_symbol,
        "direction": direction,
        "volume": volume,
        "lot_size": volume,
        "entry_price": round(entry_price, 8),
        "exit_price": round(exit_price, 8),
        "entry_time": entry_time,
        "exit_time": exit_time,
        "profit": total_profit,
        "commission": total_commission,
        "swap": total_swap,
        "fee": total_fee,
        "net_pnl": net_pnl,
        "exit_reason": close_reason,
        "mt5_comment": out_deal["comment"],
        "mt5_source": True,
    }

    log.info(
        f"[MT5-HIST] RECORD BUILT: pos={position_ticket} "
        f"{direction.upper()} {trade_symbol} "
        f"entry={entry_price:.5f} exit={exit_price:.5f} "
        f"profit={total_profit:.2f} comm={total_commission:.2f} "
        f"swap={total_swap:.2f} net={net_pnl:.2f} "
        f"reason={close_reason} deals={all_tickets}"
    )

    return record


# ── Bulk fetch (for reconciliation) ─────────────────────────

def fetch_recent_closed_positions(since_hours: int = 24) -> list:
    mt5 = _get_mt5()
    if mt5 is None:
        return []

    from_time = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    to_time = datetime.now(timezone.utc) + timedelta(hours=1)

    raw = mt5.history_deals_get(from_time, to_time)
    if raw is None or len(raw) == 0:
        return []

    # Convert and group by position_id
    positions = {}
    for r in raw:
        try:
            d = _deal_to_dict(r)
        except Exception:
            continue
        pid = d["position_id"]
        if pid == 0:
            continue
        positions.setdefault(pid, []).append(d)

    results = []
    for pid, pos_deals in positions.items():
        has_in = any(d["entry"] == 0 for d in pos_deals)
        has_out = any(d["entry"] in (1, 2, 3) for d in pos_deals)
        if has_in and has_out:
            rec = _build_trade_record(pid, pos_deals, "")
            if rec:
                results.append(rec)

    log.info(f"[MT5-HIST] Bulk fetch: {len(results)} closed positions")
    return results