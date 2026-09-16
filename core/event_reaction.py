"""
Computes how a specific rToken actually reacted, in price and volatility,
around real macro event dates. This is the core "macro quant" computation —
measured historical sensitivity, not narrated commentary.

Ties together:
- core.macro_data (real event dates, from FRED)
- core.price_fetch (real price history, from Bitget)
"""

from datetime import datetime, timedelta

import numpy as np


def _timestamp_to_date(ts_ms: int) -> str:
    """Convert a millisecond timestamp to 'YYYY-MM-DD'."""
    return datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")


def _index_by_date(candles: list[dict]) -> dict[str, float]:
    """Build a {date_str: close_price} lookup from candle data."""
    return {_timestamp_to_date(c["timestamp"]): c["close"] for c in candles}


def _nearest_available_date(target_date: str, available_dates: list[str], direction: str = "forward") -> str | None:
    """
    Find the nearest trading day to target_date in available_dates.
    direction="forward" looks for the nearest date >= target_date (or before, if none found)
    direction="backward" looks for the nearest date STRICTLY BEFORE target_date —
        this must be strict (<), not <=, because "pre-event price" needs to be
        the price before whatever happened on the event day itself. Using <=
        would let the event date match itself, hiding same-day moves entirely.
    Returns None if no reasonable match exists.
    """
    target = datetime.strptime(target_date, "%Y-%m-%d")
    candidates = sorted(available_dates)

    if direction == "backward":
        eligible = [d for d in candidates if datetime.strptime(d, "%Y-%m-%d") < target]
        return eligible[-1] if eligible else None
    else:
        eligible = [d for d in candidates if datetime.strptime(d, "%Y-%m-%d") >= target]
        return eligible[0] if eligible else None


def compute_event_reactions(
    ticker: str,
    event_dates: list[str],
    fetch_price_history_fn,
    days_before: int = 1,
    days_after: int = 3,
    candle_limit: int = 100,
) -> list[dict]:
    """
    For a given ticker and a list of real event dates (e.g. from FRED),
    compute the actual price move and realized volatility in a window
    around each event.

    event_dates: list of "YYYY-MM-DD" strings (real dates from macro_data)
    fetch_price_history_fn: injected price-history function (same shape as
        core.price_fetch.fetch_price_history), so this is testable without
        live network access.

    Returns a list of dicts, one per event that had usable price data:
        {"event_date": str, "pre_price": float, "post_price": float,
         "pct_move": float, "realized_volatility": float}

    Events that fall outside the available price history window (e.g.
    before the ticker's rToken launch date) are silently skipped, not
    treated as errors — this is expected given rToken's limited history.
    """
    candles = fetch_price_history_fn(ticker, "1day", candle_limit)
    price_by_date = _index_by_date(candles)
    available_dates = list(price_by_date.keys())

    if not available_dates:
        return []

    results = []
    for event_date in event_dates:
        pre_date = _nearest_available_date(event_date, available_dates, direction="backward")
        post_target = (datetime.strptime(event_date, "%Y-%m-%d") + timedelta(days=days_after)).strftime("%Y-%m-%d")
        post_date = _nearest_available_date(post_target, available_dates, direction="forward")

        if not pre_date or not post_date:
            continue  # event outside available price history — skip, don't error

        pre_price = price_by_date[pre_date]
        post_price = price_by_date[post_date]
        pct_move = (post_price - pre_price) / pre_price if pre_price else 0.0

        # Realized volatility across the reaction window: std dev of daily
        # returns from the event date itself through post_date — deliberately
        # NOT starting at pre_date, since pre_date is before the event and
        # would dilute the window with pre-event calm.
        window_dates = sorted(d for d in available_dates if event_date <= d <= post_date)
        window_prices = [price_by_date[d] for d in window_dates]
        if len(window_prices) > 2:
            returns = np.diff(window_prices) / window_prices[:-1]
            volatility = float(np.std(returns))
        else:
            volatility = 0.0

        results.append({
            "event_date": event_date,
            "pre_price": pre_price,
            "post_price": post_price,
            "pct_move": round(pct_move, 4),
            "realized_volatility": round(volatility, 4),
        })

    return results


def summarize_reactions(reactions: list[dict]) -> dict:
    """
    Given a list of event reactions (from compute_event_reactions), return
    summary stats: average move, direction consistency, average volatility.
    """
    if not reactions:
        return {
            "event_count": 0,
            "avg_pct_move": None,
            "avg_volatility": None,
            "consistent_direction": None,
        }

    moves = [r["pct_move"] for r in reactions]
    vols = [r["realized_volatility"] for r in reactions]

    positive = sum(1 for m in moves if m > 0)
    negative = sum(1 for m in moves if m < 0)
    total = len(moves)

    return {
        "event_count": total,
        "avg_pct_move": round(sum(moves) / total, 4),
        "avg_volatility": round(sum(vols) / total, 4),
        "consistent_direction": (
            "up" if positive / total >= 0.7 else
            "down" if negative / total >= 0.7 else
            "mixed"
        ),
    }
