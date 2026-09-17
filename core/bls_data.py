"""
BLS (Bureau of Labor Statistics) module — provides category-level detail
FRED's headline series don't carry: CPI broken into energy/shelter/food/core,
employment by sector, etc.

BLS's API does NOT expose release dates (confirmed — same reference-period
limitation as FRED's raw `date` field). So this module does not attempt to
date its own data. Instead, category values are joined to FRED's real
`release_date` (via macro_data.fetch_series) by matching reference period —
headline CPI and its category breakdown are published in the same report,
on the same day, so this join is accurate, not approximate.
"""

import os
import requests

BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Curated CPI component series (seasonally adjusted, for clean month-over-month
# comparison). Extend as needed — BLS has far more granularity available.
CPI_COMPONENT_SERIES = {
    "headline": "CUSR0000SA0",       # CPI-U, all items
    "core": "CUSR0000SA0L1E",        # all items less food & energy
    "food": "CUSR0000SAF1",
    "energy": "CUSR0000SA0E",
    "shelter": "CUSR0000SAH1",
}

EMPLOYMENT_SERIES = {
    "total_nonfarm": "CES0000000001",
}


def _api_key() -> str:
    key = os.environ.get("BLS_API_KEY")
    if not key:
        raise RuntimeError("BLS_API_KEY not set in environment")
    return key


def fetch_bls_series(series_ids: list[str], start_year: str, end_year: str) -> dict[str, list[dict]]:
    """
    Fetch one or more BLS series over a year range.

    Returns {series_id: [{"year": str, "period": str, "period_name": str,
    "value": float}, ...]}, one list per series, chronological order not
    guaranteed by BLS (results are typically newest-first) — sort by
    caller if needed.
    """
    body = {
        "seriesid": series_ids,
        "startyear": start_year,
        "endyear": end_year,
        "registrationkey": _api_key(),
    }
    resp = requests.post(BASE_URL, json=body, timeout=10)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS API error: {payload.get('message')}")

    result = {}
    for series in payload.get("Results", {}).get("series", []):
        series_id = series["seriesID"]
        observations = []
        for obs in series.get("data", []):
            if obs["period"] == "M13":  # BLS annual-average marker, not a real month
                continue
            observations.append({
                "year": obs["year"],
                "period": obs["period"],       # e.g. "M08"
                "period_name": obs["periodName"],  # e.g. "August"
                "value": float(obs["value"]),
            })
        result[series_id] = observations
    return result


def get_cpi_breakdown(start_year: str, end_year: str) -> dict[str, list[dict]]:
    """Convenience wrapper: fetch all curated CPI component series at once."""
    return fetch_bls_series(list(CPI_COMPONENT_SERIES.values()), start_year, end_year)


def join_breakdown_to_release_dates(
    cpi_breakdown: dict[str, list[dict]],
    headline_fred_observations: list[dict] = None,
) -> list[dict]:
    """
    Join BLS category-level CPI values to real release dates, by matching
    reference year/month — headline CPI and its category breakdown are
    published in the same report, on the same day.

    Uses data/macro_calendar.py's real, manually-sourced CPI_2026_DATES_CONFIRMED
    as the authoritative release-date source — NOT FRED's realtime_start,
    which is confirmed unreliable (see core/macro_data.py's fetch_series
    docstring: bulk revisions overwrite realtime_start for many historical
    points at once, producing wrong/duplicate dates).

    headline_fred_observations is kept as an optional parameter for
    backwards compatibility but is no longer used — real dates come from
    the calendar module instead.

    Returns a list of {"release_date": str, "reference_month": "YYYY-MM",
    "energy": float, "shelter": float, "food": float, "core": float,
    "headline": float} — one row per month where a real calendar date
    exists for that reference month, sorted chronologically. Months without
    a confirmed calendar date are skipped, not errored.
    """
    from data.macro_calendar import CPI_2026_DATES_CONFIRMED

    # Real CPI release dates are the 10th-14th of the month AFTER the
    # reference month (e.g. "2026-08-12" is the release date for July 2026
    # data). Build reference_month -> real release_date by matching each
    # calendar date's release month back to (release_month - 1) as the
    # reference month it describes.
    release_date_by_month: dict[str, str] = {}
    for release_date in CPI_2026_DATES_CONFIRMED:
        year, month, _ = release_date.split("-")
        month_num = int(month)
        if month_num == 1:
            ref_year, ref_month = int(year) - 1, 12
        else:
            ref_year, ref_month = int(year), month_num - 1
        ref_key = f"{ref_year}-{str(ref_month).zfill(2)}"
        release_date_by_month[ref_key] = release_date

    # Reshape BLS data into {("YYYY", "M08"): {component: value}}
    by_period: dict[tuple, dict] = {}
    series_id_to_component = {v: k for k, v in CPI_COMPONENT_SERIES.items()}

    for series_id, observations in cpi_breakdown.items():
        component = series_id_to_component.get(series_id, series_id)
        for obs in observations:
            key = (obs["year"], obs["period"])
            by_period.setdefault(key, {})[component] = obs["value"]

    rows = []
    for (year, period), values in by_period.items():
        month_num = period.replace("M", "").zfill(2)
        month_key = f"{year}-{month_num}"
        release_date = release_date_by_month.get(month_key)
        if not release_date:
            continue  # no matching real calendar date for this month — skip
        rows.append({
            "release_date": release_date,
            "reference_month": month_key,
            **values,
        })

    rows.sort(key=lambda r: r["release_date"])
    return rows
