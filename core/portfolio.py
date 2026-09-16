"""
Portfolio evaluation engine — Engine 1 (evaluate a holdings set, with or
without a candidate trade) and Engine 2 (scan the universe and rank
candidates for diversification/hedging).

Price fetching is injected as a function parameter (rather than imported
directly) so this module can be tested with synthetic data, and swapped
to a cached/batched fetch later without changing this code.
"""

from data.sector_map import get_sector, known_tickers, BENCHMARK_TICKER
from core.stats import (
    to_returns,
    compute_beta,
    build_correlation_matrix,
    compute_sector_weights,
    compute_portfolio_beta,
)


def _price_series_for(tickers: list[str], fetch_closes_fn) -> dict[str, list[float]]:
    """Fetch closing price series for a list of tickers, plus the benchmark."""
    all_tickers = list(set(tickers) | {BENCHMARK_TICKER})
    return {t: fetch_closes_fn(t) for t in all_tickers}


def _current_prices(price_series: dict[str, list[float]]) -> dict[str, float]:
    """Latest close per ticker, from already-fetched price series."""
    return {t: series[-1] for t, series in price_series.items() if series}


def _snapshot(holdings: list[dict], price_series: dict[str, list[float]]) -> dict:
    """
    Compute a full stats snapshot (beta, sector weights, correlation matrix)
    for a given holdings set, using already-fetched price series.
    """
    tickers = [h["ticker"] for h in holdings]
    prices = _current_prices(price_series)

    benchmark_closes = price_series[BENCHMARK_TICKER]
    betas = {
        t: compute_beta(price_series[t], benchmark_closes)
        for t in tickers if t in price_series
    }

    portfolio_beta = compute_portfolio_beta(holdings, prices, betas)
    sector_weights = compute_sector_weights(holdings, prices, get_sector)

    holding_price_series = {t: price_series[t] for t in tickers if t in price_series}
    correlation_matrix = build_correlation_matrix(holding_price_series)

    return {
        "beta": portfolio_beta,
        "sector_weights": sector_weights,
        "correlation_matrix": correlation_matrix,
        "holdings": holdings,
    }


def evaluate_holdings(
    holdings: list[dict],
    fetch_closes_fn,
    candidate: dict | None = None,
) -> dict:
    """
    Engine 1: evaluate a holdings set, optionally with a candidate trade added.

    holdings: [{"ticker": str, "quantity": float}, ...]
    candidate: {"ticker": str, "quantity": float} or None
        (quantity should be signed or handled by caller for buy/sell direction;
        for an MVP, treat "add" as positive quantity added to any existing
        position in that ticker, or a new position if none exists)

    Returns:
        {"current": {...snapshot...}, "after": {...snapshot...} or None}
    """
    tickers_needed = [h["ticker"] for h in holdings]
    if candidate:
        tickers_needed.append(candidate["ticker"])

    price_series = _price_series_for(tickers_needed, fetch_closes_fn)

    current_snapshot = _snapshot(holdings, price_series)

    after_snapshot = None
    if candidate:
        new_holdings = [dict(h) for h in holdings]
        existing = next((h for h in new_holdings if h["ticker"] == candidate["ticker"]), None)
        if existing:
            existing["quantity"] += candidate["quantity"]
        else:
            new_holdings.append({"ticker": candidate["ticker"], "quantity": candidate["quantity"]})
        after_snapshot = _snapshot(new_holdings, price_series)

    return {"current": current_snapshot, "after": after_snapshot}


def rank_diversifiers(
    holdings: list[dict],
    fetch_closes_fn,
    candidate_pool: list[str] | None = None,
    top_n: int = 5,
) -> list[dict]:
    """
    Engine 2: scan a universe of candidate tickers not currently held, and
    rank them by how much they'd reduce portfolio concentration/correlation
    if added in a small equal-weight amount.

    candidate_pool: tickers to consider; defaults to all known (sector-mapped)
    tickers not already held.

    Returns a list of {"ticker": str, "sector": str, "avg_correlation_to_portfolio": float},
    sorted ascending by correlation (lowest/most diversifying first).
    """
    held_tickers = {h["ticker"] for h in holdings}
    pool = candidate_pool or [t for t in known_tickers() if t not in held_tickers]

    price_series = _price_series_for(list(held_tickers) + pool, fetch_closes_fn)
    held_returns = {t: to_returns(price_series[t]) for t in held_tickers if t in price_series}

    from core.stats import compute_correlation

    results = []
    for candidate in pool:
        if candidate not in price_series:
            continue
        candidate_returns = to_returns(price_series[candidate])
        correlations = [
            compute_correlation(candidate_returns, held_returns[h])
            for h in held_returns
        ]
        avg_corr = sum(correlations) / len(correlations) if correlations else 0.0
        results.append({
            "ticker": candidate,
            "sector": get_sector(candidate),
            "avg_correlation_to_portfolio": avg_corr,
        })

    results.sort(key=lambda r: r["avg_correlation_to_portfolio"])
    return results[:top_n]
