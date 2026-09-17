"""
Sector-sensitivity ranker — given a macro event type (e.g. rate decisions,
CPI releases), computes and ranks how much each sector has actually moved
around those real events, using real price data across the known ticker
universe. Reuses event_reaction.py and sector_map.py rather than
duplicating logic.
"""

from data.sector_map import SECTOR_MAP, get_sector
from core.event_reaction import compute_event_reactions, summarize_reactions


def rank_sector_sensitivity(
    event_dates: list[str],
    fetch_price_history_fn,
    days_before: int = 1,
    days_after: int = 3,
    tickers: list[str] | None = None,
) -> list[dict]:
    """
    For each sector in the known universe, compute the average price move
    and volatility across its tickers around the given real event dates,
    then rank sectors by average absolute move (most sensitive first).

    event_dates: real dates (e.g. release_date values from macro_data),
        for one specific event type (rate decisions, CPI releases, etc.)
    tickers: optional subset to scan; defaults to the full known universe.

    Returns a list of:
        {"sector": str, "avg_pct_move": float, "avg_abs_move": float,
         "avg_volatility": float, "ticker_count": int}
    sorted descending by avg_abs_move (most sensitive sector first).
    """
    universe = tickers or list(SECTOR_MAP.keys())

    # Group per-ticker summaries by sector
    sector_moves: dict[str, list[float]] = {}
    sector_vols: dict[str, list[float]] = {}

    for ticker in universe:
        try:
            reactions = compute_event_reactions(
                ticker, event_dates, fetch_price_history_fn, days_before, days_after
            )
        except Exception:
            # A single bad/delisted/unlisted ticker (e.g. a real 400 from
            # Bitget for a symbol that doesn't actually exist) must not take
            # down the whole universe scan — skip it and keep going.
            continue

        if not reactions:
            continue  # ticker had no usable price history for these events — skip

        summary = summarize_reactions(reactions)
        sector = get_sector(ticker)

        sector_moves.setdefault(sector, []).append(summary["avg_pct_move"])
        sector_vols.setdefault(sector, []).append(summary["avg_volatility"])

    results = []
    for sector, moves in sector_moves.items():
        vols = sector_vols[sector]
        avg_pct_move = sum(moves) / len(moves)
        avg_abs_move = sum(abs(m) for m in moves) / len(moves)
        avg_volatility = sum(vols) / len(vols)
        results.append({
            "sector": sector,
            "avg_pct_move": round(avg_pct_move, 4),
            "avg_abs_move": round(avg_abs_move, 4),
            "avg_volatility": round(avg_volatility, 4),
            "ticker_count": len(moves),
        })

    results.sort(key=lambda r: r["avg_abs_move"], reverse=True)
    return results
