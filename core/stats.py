"""
Core portfolio statistics: returns, beta, correlation, sector weighting.

All functions here are pure computation — no network calls, no LLM.
Given price series and holdings, they return real numbers.
"""

import numpy as np


def to_returns(closes: list[float]) -> np.ndarray:
    """Convert a list of closing prices into daily returns (% change)."""
    arr = np.array(closes, dtype=float)
    return (arr[1:] - arr[:-1]) / arr[:-1]


def compute_beta(asset_closes: list[float], benchmark_closes: list[float]) -> float:
    """
    Beta of an asset relative to a benchmark, computed via covariance/variance
    on daily returns. Both series must be aligned (same dates, same length).
    """
    asset_returns = to_returns(asset_closes)
    bench_returns = to_returns(benchmark_closes)

    n = min(len(asset_returns), len(bench_returns))
    asset_returns = asset_returns[-n:]
    bench_returns = bench_returns[-n:]

    covariance = np.cov(asset_returns, bench_returns)[0, 1]
    benchmark_variance = np.var(bench_returns)

    if benchmark_variance == 0:
        return 0.0
    return float(covariance / benchmark_variance)


def compute_correlation(returns_a: np.ndarray, returns_b: np.ndarray) -> float:
    """Pearson correlation between two return series (already aligned)."""
    n = min(len(returns_a), len(returns_b))
    a = returns_a[-n:]
    b = returns_b[-n:]
    if n < 2 or np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def build_correlation_matrix(price_series: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    """
    Given {ticker: [closes...]} for multiple tickers, return a full
    pairwise correlation matrix as nested dicts: matrix[a][b] = correlation.
    """
    returns = {ticker: to_returns(closes) for ticker, closes in price_series.items()}
    tickers = list(returns.keys())

    matrix = {}
    for a in tickers:
        matrix[a] = {}
        for b in tickers:
            if a == b:
                matrix[a][b] = 1.0
            else:
                matrix[a][b] = compute_correlation(returns[a], returns[b])
    return matrix


def compute_sector_weights(holdings: list[dict], prices: dict[str, float], sector_of) -> dict[str, float]:
    """
    Compute portfolio weight per sector.

    holdings: list of {"ticker": str, "quantity": float}
    prices: {ticker: current_price} — latest close per ticker
    sector_of: function(ticker) -> sector name (e.g. sector_map.get_sector)

    Returns {sector: weight_fraction}, weights sum to 1.0 across the portfolio.
    """
    values_by_sector: dict[str, float] = {}
    total_value = 0.0

    for h in holdings:
        ticker = h["ticker"]
        qty = h["quantity"]
        price = prices.get(ticker, 0.0)
        value = qty * price
        sector = sector_of(ticker)
        values_by_sector[sector] = values_by_sector.get(sector, 0.0) + value
        total_value += value

    if total_value == 0:
        return {}

    return {sector: value / total_value for sector, value in values_by_sector.items()}


def compute_portfolio_beta(holdings: list[dict], prices: dict[str, float], betas: dict[str, float]) -> float:
    """
    Weighted-average beta of the whole portfolio.

    holdings: list of {"ticker": str, "quantity": float}
    prices: {ticker: current_price}
    betas: {ticker: beta_vs_benchmark}
    """
    total_value = 0.0
    weighted_beta = 0.0

    for h in holdings:
        ticker = h["ticker"]
        value = h["quantity"] * prices.get(ticker, 0.0)
        total_value += value
        weighted_beta += value * betas.get(ticker, 0.0)

    if total_value == 0:
        return 0.0
    return weighted_beta / total_value


def compute_recent_volatility(closes: list[float], recent_window: int = 10) -> dict:
    """
    Compare a ticker's recent realized volatility to its own longer-run
    baseline — answers "is this elevated right now" using the ticker's own
    history, not an arbitrary external threshold.

    closes: full available closing price series (oldest first)
    recent_window: how many most-recent days count as "recent" (default 10)

    Returns:
        {"recent_volatility": float, "baseline_volatility": float,
         "ratio": float, "elevated": bool}
    "elevated" is True when recent volatility is at least 1.5x baseline —
    a simple, explainable threshold rather than a statistical test, since
    this is meant to answer a plain-language question, not run inference.
    """
    returns = to_returns(closes)

    if len(returns) < recent_window + 5:
        # Not enough history to compare meaningfully — return None fields
        # rather than a misleading number computed from a tiny sample.
        return {
            "recent_volatility": None,
            "baseline_volatility": None,
            "ratio": None,
            "elevated": None,
        }

    recent_returns = returns[-recent_window:]
    baseline_returns = returns[:-recent_window]  # everything before the recent window

    recent_vol = float(np.std(recent_returns))
    baseline_vol = float(np.std(baseline_returns))

    if baseline_vol == 0:
        ratio = None
        elevated = None
    else:
        ratio = recent_vol / baseline_vol
        elevated = ratio >= 1.5

    return {
        "recent_volatility": round(recent_vol, 5),
        "baseline_volatility": round(baseline_vol, 5),
        "ratio": round(ratio, 3) if ratio is not None else None,
        "elevated": elevated,
    }
