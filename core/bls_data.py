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

CPI_COMPONENT_SERIES = {
    "headline": "CUSR0000SA0",
    "core": "CUSR0000SA0L1E",
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
            if obs["period"] == "M13":
                continue
            observations.append({
                "year": obs["year"],
                "period": obs["period"],
                "period_name": obs["periodName"],
                "value": float(obs["value"]),
            })
        result[series_id] = observations
    return result


def get_cpi_breakdown(start_year: str, end_year: str) -> dict[str, list[dict]]:
    return fetch_bls_series(list(CPI_COMPONENT_SERIES.values()), start_year, end_year)


def join_breakdown_to_release_dates(
    cpi_breakdown: dict[str, list[dict]],
    headline_fred_observations: list[dict],
) -> list[dict]:
    release_date_by_month = {
        obs["reference_date"][:7]: obs["release_date"]
        for obs in headline_fred_observations
    }

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
            continue
        rows.append({
            "release_date": release_date,
            "reference_month": month_key,
            **values,
        })

    rows.sort(key=lambda r: r["release_date"])
    return rows