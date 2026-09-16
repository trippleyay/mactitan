"""
Macro event data, sourced live from FRED (Federal Reserve Economic Data),
the St. Louis Fed's free, official public API — not hardcoded.

Requires a free FRED API key (30-second signup at
https://fred.stlouisfed.org/docs/api/api_key.html), stored as FRED_API_KEY
in the environment.

Two series cover everything this product needs:
- CPIAUCSL: Consumer Price Index (monthly) — gives real CPI release dates
  and values, automatically, no manual maintenance.
- FEDFUNDS: Federal Funds Rate (monthly) — the exact date the rate changes
  tells you when a real hike/cut/hold happened, replacing any hand-typed
  FOMC outcome table.

Note: FRED does not provide analyst "expected/consensus" values (that's
commercial economic-calendar data, not free/public) — this module only
surfaces real, actual, dated outcomes. Reaction analysis is computed
against the real event date, not against a "was it a surprise" framing.
"""

import os
import requests

BASE_URL = "https://api.stlouisfed.org/fred"


def _api_key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY not set in environment")
    return key


def fetch_series(series_id: str, observation_start: str = "2026-01-01") -> list[dict]:
    """
    Fetch observations for a FRED series.

    Returns a list of {"reference_date": "YYYY-MM-DD", "release_date": "YYYY-MM-DD",
    "value": float}, chronological by reference_date.

    reference_date is the period the data describes (e.g. "2026-08-01" for
    August CPI) — NOT when it was published. release_date (FRED's
    realtime_start) is the actual day the value became public, which is
    what event-reaction analysis needs to measure against — using
    reference_date instead would compare stock prices to the wrong day
    entirely, off by however long the publication lag is for that series.
    """
    params = {
        "series_id": series_id,
        "api_key": _api_key(),
        "file_type": "json",
        "observation_start": observation_start,
        "sort_order": "asc",
    }
    resp = requests.get(f"{BASE_URL}/series/observations", params=params, timeout=10)
    resp.raise_for_status()
    body = resp.json()

    observations = []
    for obs in body.get("observations", []):
        if obs["value"] == ".":  # FRED's marker for missing data
            continue
        observations.append({
            "reference_date": obs["date"],
            "release_date": obs["realtime_start"],
            "value": float(obs["value"]),
        })
    return observations


def get_cpi_events(observation_start: str = "2026-01-01") -> list[dict]:
    """Real CPI release dates and values — replaces any hardcoded CPI table."""
    return fetch_series("CPIAUCSL", observation_start)


def get_fed_funds_events(observation_start: str = "2026-01-01") -> list[dict]:
    """
    Real Fed Funds Rate observations. A change in value between consecutive
    entries marks an actual rate hike/cut; no change marks a hold — derived
    from real data, not a maintained table.
    """
    return fetch_series("FEDFUNDS", observation_start)


# Full set of market-moving macro series covered, beyond just CPI/Fed Funds.
# All free via FRED, same fetch_series() call — extend this dict as needed.
MACRO_SERIES = {
    "cpi": "CPIAUCSL",           # Consumer Price Index (headline inflation)
    "pce": "PCEPI",              # PCE Price Index — Fed's preferred inflation gauge
    "ppi": "PPIACO",             # Producer Price Index — leading inflation indicator
    "fed_funds": "FEDFUNDS",     # Federal Funds Rate
    "nonfarm_payrolls": "PAYEMS",  # Jobs report
    "unemployment": "UNRATE",    # Unemployment rate
    "gdp": "GDPC1",              # Real GDP
    "retail_sales": "RSAFS",     # Consumer spending strength
    "consumer_sentiment": "UMCSENT",  # U. Michigan sentiment survey
    "treasury_10y": "DGS10",     # 10-Year Treasury yield (daily, ties to rate expectations)
    "housing_starts": "HOUST",   # Housing starts
}


def get_macro_events(indicator: str, observation_start: str = "2026-01-01") -> list[dict]:
    """
    Fetch real observations for any named macro indicator (see MACRO_SERIES
    for available keys). This is the general entry point — get_cpi_events()
    and get_fed_funds_events() above remain as convenience wrappers for the
    two most commonly used series.
    """
    if indicator not in MACRO_SERIES:
        raise ValueError(f"Unknown macro indicator '{indicator}'. Available: {list(MACRO_SERIES.keys())}")
    return fetch_series(MACRO_SERIES[indicator], observation_start)


def derive_rate_changes(fed_funds_events: list[dict]) -> list[dict]:
    """
    Given chronological Fed Funds observations, return only the points where
    the rate actually changed, labeled hike/cut, plus the magnitude.
    Uses release_date (real publication day), not reference_date.
    """
    changes = []
    for prev, curr in zip(fed_funds_events, fed_funds_events[1:]):
        delta = curr["value"] - prev["value"]
        if abs(delta) > 1e-6:
            changes.append({
                "release_date": curr["release_date"],
                "direction": "hike" if delta > 0 else "cut",
                "magnitude": round(abs(delta), 3),
                "new_rate": curr["value"],
            })
    return changes