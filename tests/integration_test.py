"""
Real-data integration test. Run this LOCALLY (not in the sandbox) with your
.env filled in — it hits live Bitget, FRED, and BLS APIs and prints real
output for every tool, so you can eyeball correctness before any LLM is
involved. No mocking, no synthetic data — if something's wrong here, it's
wrong in the actual product, not a test artifact.

Usage:
    python3 tests/integration_test.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.price_fetch import fetch_price_history, fetch_closes
from core.macro_data import get_cpi_events, get_fed_funds_events, derive_rate_changes
from core.bls_data import get_cpi_breakdown, join_breakdown_to_release_dates
from core.event_reaction import compute_event_reactions, summarize_reactions
from core.sector_sensitivity import rank_sector_sensitivity
from core.stats import compute_recent_volatility
from data.macro_calendar import next_fomc_date, next_cpi_date

SEPARATOR = "=" * 60


def test_price_fetch():
    print(SEPARATOR)
    print("TOOL 2: Price fetch (rAAPL, live from Bitget)")
    print(SEPARATOR)
    candles = fetch_price_history("rAAPL", "1day", 10)
    print(f"Got {len(candles)} candles. Most recent: {candles[-1] if candles else 'NONE'}")
    print()


def test_macro_data():
    print(SEPARATOR)
    print("TOOL 1: Macro event calendar (live from FRED)")
    print(SEPARATOR)
    cpi = get_cpi_events()
    print(f"CPI observations since 2026-01-01: {len(cpi)}")
    if cpi:
        print(f"Most recent: {cpi[-1]}")

    fed_funds = get_fed_funds_events()
    changes = derive_rate_changes(fed_funds)
    print(f"Fed Funds observations: {len(fed_funds)}, real rate changes detected: {len(changes)}")
    for c in changes:
        print(f"  {c}")
    print()


def test_bls_breakdown():
    print(SEPARATOR)
    print("BLS category breakdown, joined to real FRED release dates")
    print(SEPARATOR)
    cpi_headline = get_cpi_events()
    breakdown = get_cpi_breakdown(start_year="2026", end_year="2026")
    joined = join_breakdown_to_release_dates(breakdown, cpi_headline)
    print(f"Joined rows: {len(joined)}")
    for row in joined[-3:]:  # last 3 months
        print(f"  {row}")
    print()


def test_event_reaction():
    print(SEPARATOR)
    print("TOOL 3: Event-reaction calculator (rNVDA around real CPI releases)")
    print(SEPARATOR)
    from data.macro_calendar import CPI_2026_DATES_CONFIRMED
    reactions = compute_event_reactions("rNVDA", CPI_2026_DATES_CONFIRMED, fetch_price_history)
    print(f"Usable reactions found: {len(reactions)} (out of {len(CPI_2026_DATES_CONFIRMED)} CPI events)")
    for r in reactions:
        print(f"  {r}")
    print("Summary:", summarize_reactions(reactions))
    print()


def test_sector_sensitivity():
    print(SEPARATOR)
    print("TOOL 4: Sector sensitivity ranker (real CPI events, small ticker sample)")
    print(SEPARATOR)
    from data.macro_calendar import CPI_2026_DATES_CONFIRMED
    sample_tickers = ["rAAPL", "rMSFT", "rNVDA", "rXOM", "rCVX", "rJPM"]
    ranked = rank_sector_sensitivity(CPI_2026_DATES_CONFIRMED, fetch_price_history, tickers=sample_tickers)
    for r in ranked:
        print(f"  {r}")
    print()


def test_volatility():
    print(SEPARATOR)
    print("TOOL 5: Volatility calculator (rTSLA, real data)")
    print(SEPARATOR)
    closes = fetch_closes("rTSLA", "1day", 60)
    result = compute_recent_volatility(closes, recent_window=10)
    print(f"  {result}")
    print()


def test_upcoming_events():
    print(SEPARATOR)
    print("TOOL 6: Upcoming event lookup (official Fed/BLS calendar)")
    print(SEPARATOR)
    today = date.today().isoformat()
    print(f"  Today: {today}")
    print(f"  Next FOMC: {next_fomc_date(today)}")
    print(f"  Next CPI: {next_cpi_date(today)}")
    print()


if __name__ == "__main__":
    print("Running full integration test against LIVE data — no mocking.\n")

    try:
        test_price_fetch()
    except Exception as e:
        print(f"[FAILED] price_fetch: {e}\n")

    try:
        test_macro_data()
    except Exception as e:
        print(f"[FAILED] macro_data: {e}\n")

    try:
        test_bls_breakdown()
    except Exception as e:
        print(f"[FAILED] bls_data: {e}\n")

    try:
        test_event_reaction()
    except Exception as e:
        print(f"[FAILED] event_reaction: {e}\n")

    try:
        test_sector_sensitivity()
    except Exception as e:
        print(f"[FAILED] sector_sensitivity: {e}\n")

    try:
        test_volatility()
    except Exception as e:
        print(f"[FAILED] volatility: {e}\n")

    try:
        test_upcoming_events()
    except Exception as e:
        print(f"[FAILED] upcoming_events: {e}\n")

    print(SEPARATOR)
    print("Done. Review each section above for correctness before touching the LLM layer.")
