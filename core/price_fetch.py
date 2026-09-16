"""
Fetches public rToken price history from Bitget's spot market API.
No API key required — this is public market data, shared across all users.
"""

import requests

BASE_URL = "https://api.bitget.com"
CANDLE_ENDPOINT = "/api/v2/spot/market/candles"


def rtoken_symbol(ticker: str) -> str:
    """Convert our canonical rToken ticker (e.g. 'rAAPL') to Bitget's trading
    symbol format (e.g. 'RAAPLUSDT'), matching the confirmed instrument response."""
    return f"{ticker.upper()}USDT"


def fetch_price_history(ticker: str, granularity: str = "1day", limit: int = 100) -> list[dict]:
    """
    Fetch historical candles for a given rToken ticker.

    Returns a list of dicts, oldest first, each with:
        {"timestamp": int (ms), "open": float, "high": float,
         "low": float, "close": float, "volume": float}

    Raises requests.HTTPError on a failed request, and ValueError if
    Bitget's response body indicates an error (non-"00000" code).
    """
    symbol = rtoken_symbol(ticker)
    params = {
        "symbol": symbol,
        "granularity": granularity,
        "limit": limit,
    }
    resp = requests.get(BASE_URL + CANDLE_ENDPOINT, params=params, timeout=10)
    resp.raise_for_status()
    body = resp.json()

    if body.get("code") != "00000":
        raise ValueError(f"Bitget API error for {symbol}: {body.get('msg')}")

    candles = []
    # Bitget candle rows are typically:
    # [timestamp, open, high, low, close, base_volume, quote_volume, ...]
    # Sorted newest-first from the API — reverse to oldest-first for
    # time-series math (returns, rolling windows) downstream.
    for row in reversed(body.get("data", [])):
        candles.append({
            "timestamp": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        })
    return candles


def fetch_closes(ticker: str, granularity: str = "1day", limit: int = 100) -> list[float]:
    """Convenience wrapper: just the closing prices, oldest first."""
    return [c["close"] for c in fetch_price_history(ticker, granularity, limit)]
