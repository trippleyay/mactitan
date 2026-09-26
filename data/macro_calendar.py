"""
Forward-looking macro event calendar. Full coverage of major US macro
indicators — every one either has a complete real official 2026 schedule,
or is computed from a confirmed fixed institutional rule.

FRED's release-dates endpoint was tested directly against live data and
confirmed to NOT return future dates — see core/macro_data.py's
get_upcoming_release_dates() for that function and its caveat. This module
replaces that gap with each indicator's actual authoritative source.

COVERAGE STATUS (as of this writing, 2026) — all 20 indicators now either
COMPLETE (full real official 2026 schedule) or COMPUTED (from a confirmed
fixed institutional rule, cross-checked against real dates):

COMPLETE: FOMC, CPI, PPI, nonfarm payrolls / unemployment, retail sales,
industrial production, PCE, GDP (all three estimates per quarter),
housing starts, Michigan consumer sentiment (preliminary and final),
JOLTS, durable goods orders, trade balance

COMPUTED from confirmed fixed rules:
- ISM Manufacturing PMI: 1st business day of each month
- ISM Services PMI: 3rd business day of each month
- Initial jobless claims: every Thursday
- Conference Board consumer confidence: last Tuesday of each month

MAINTENANCE: update yearly from each agency's own schedule page:
- FOMC:                https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- CPI / PPI / jobs / JOLTS: https://www.bls.gov/schedule/news_release/current_year.asp
- PCE / GDP:           https://www.bea.gov/news/schedule/full
- Retail sales / durable goods: https://www.census.gov/economic-indicators/calendar-listview.html
- Trade balance:       https://www.census.gov/foreign-trade/schedule.html
- Housing starts:      https://www.census.gov/economic-indicators/calendar-listview.html
- Industrial production: https://www.federalreserve.gov/releases/g17/
- ISM PMI:             https://www.ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/
- Michigan sentiment:  https://data.sca.isr.umich.edu/fetchdoc.php?docid=79628
- Consumer confidence: https://www.conference-board.org/topics/consumer-confidence/
"""

from datetime import date, timedelta

# ---------------------------------------------------------------------
# COMPLETE for 2026 — real, official, sourced
# ---------------------------------------------------------------------

FOMC_2026_DATES = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]

# Source: bls.gov/schedule/news_release/cpi.htm
CPI_2026_DATES_CONFIRMED = [
    "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10",
    "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
    "2026-09-11", "2026-10-14", "2026-11-10", "2026-12-10",
]

PPI_2026_DATES_CONFIRMED = [
    "2026-01-14", "2026-01-30", "2026-02-27", "2026-03-18",
    "2026-04-14", "2026-05-13", "2026-06-11", "2026-07-15",
    "2026-08-13", "2026-09-10", "2026-10-15", "2026-11-13", "2026-12-15",
]

NONFARM_PAYROLLS_2026_DATES = [
    "2025-12-16", "2026-01-09", "2026-02-11", "2026-03-06",
    "2026-04-03", "2026-05-08", "2026-06-05", "2026-07-02",
    "2026-08-07", "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
]

UNEMPLOYMENT_2026_DATES = NONFARM_PAYROLLS_2026_DATES  # same release, same real dates

RETAIL_SALES_2026_DATES = [
    "2025-11-25", "2025-12-16", "2026-01-14", "2026-02-10",
    "2026-03-06", "2026-04-01", "2026-04-21", "2026-05-14",
    "2026-06-17", "2026-07-16", "2026-08-14", "2026-09-16",
    "2026-10-15", "2026-11-17", "2026-12-16",
]

INDUSTRIAL_PRODUCTION_2026_DATES = [
    "2026-01-16", "2026-02-18", "2026-03-16", "2026-04-16",
    "2026-05-15", "2026-06-15", "2026-07-17", "2026-08-18",
    "2026-09-18", "2026-10-16", "2026-11-17", "2026-12-16",
]

# Source: bea.gov/news/schedule/full
PCE_2026_DATES_CONFIRMED = [
    "2026-01-22", "2026-02-20", "2026-03-13", "2026-04-09",
    "2026-04-30", "2026-05-28", "2026-06-25", "2026-07-30",
    "2026-08-26", "2026-09-30", "2026-10-29", "2026-11-25", "2026-12-23",
]

# Source: bea.gov/news/schedule/full — all three estimates per quarter
GDP_2026_DATES_CONFIRMED = [
    "2026-01-22", "2026-02-20", "2026-03-13", "2026-04-09",
    "2026-04-30", "2026-05-28", "2026-06-25", "2026-07-30",
    "2026-08-26", "2026-09-30", "2026-10-29", "2026-11-25", "2026-12-23",
]

# Source: census.gov/economic-indicators/calendar-listview.html
HOUSING_STARTS_2026_DATES_CONFIRMED = [
    "2026-01-09", "2026-02-18", "2026-03-12", "2026-04-29",
    "2026-05-21", "2026-06-16", "2026-07-17", "2026-08-18",
    "2026-09-17", "2026-10-20", "2026-11-18", "2026-12-17",
]

# Source: data.sca.isr.umich.edu/fetchdoc.php?docid=79628 — two distinct
# real releases per month, not one indicator with one date.
MICHIGAN_SENTIMENT_PRELIM_2026_DATES = [
    "2026-01-09", "2026-02-06", "2026-03-13", "2026-04-10",
    "2026-05-08", "2026-06-12", "2026-07-17", "2026-08-14",
    "2026-09-11", "2026-10-09", "2026-11-06", "2026-12-04",
]

MICHIGAN_SENTIMENT_FINAL_2026_DATES = [
    "2026-01-23", "2026-02-20", "2026-03-27", "2026-04-24",
    "2026-05-22", "2026-06-26", "2026-07-31", "2026-08-28",
    "2026-09-25", "2026-10-23", "2026-11-20", "2026-12-18",
]

# Source: bls.gov/schedule/news_release/jolts.htm
JOLTS_2026_DATES_CONFIRMED = [
    "2026-01-07", "2026-02-05", "2026-03-13", "2026-03-31",
    "2026-05-05", "2026-06-02", "2026-06-30", "2026-08-04",
    "2026-09-01", "2026-09-29", "2026-11-03", "2026-12-01",
]

# Source: census.gov/economic-indicators/calendar-listview.html
DURABLE_GOODS_2026_DATES_CONFIRMED = [
    "2026-01-26", "2026-02-18", "2026-03-13", "2026-04-07",
    "2026-04-29", "2026-05-28", "2026-06-25", "2026-07-27",
    "2026-08-26", "2026-09-25", "2026-10-27", "2026-11-25", "2026-12-23",
]

# Source: census.gov/foreign-trade/schedule.html
TRADE_BALANCE_2026_DATES_CONFIRMED = [
    "2026-01-08", "2026-01-29", "2026-02-19", "2026-03-12",
    "2026-04-02", "2026-05-05", "2026-06-09", "2026-07-07",
    "2026-08-04", "2026-09-03", "2026-10-06", "2026-11-04", "2026-12-08",
]

# ---------------------------------------------------------------------
# COMPUTED from confirmed fixed institutional rules
# ---------------------------------------------------------------------

def _nth_business_day_of_month(year: int, month: int, n: int) -> date:
    """The nth weekday (Mon-Fri) of a given month — does not account for
    named holidays, so specific months may be off by a day or two around
    them (see the one explicit override below for a known case)."""
    d = date(year, month, 1)
    count = 0
    while True:
        if d.weekday() < 5:
            count += 1
            if count == n:
                return d
        d += timedelta(days=1)


def ism_manufacturing_dates_for_year(year: int) -> list[str]:
    """1st business day of each month — confirmed rule from ISM's own site."""
    return [_nth_business_day_of_month(year, m, 1).isoformat() for m in range(1, 13)]


def ism_services_dates_for_year(year: int) -> list[str]:
    """3rd business day of each month — confirmed rule from ISM's own site."""
    return [_nth_business_day_of_month(year, m, 3).isoformat() for m in range(1, 13)]


def jobless_claims_thursdays_for_year(year: int) -> list[str]:
    """Every Thursday — confirmed weekly DOL/BLS release day."""
    d = date(year, 1, 1)
    while d.weekday() != 3:
        d += timedelta(days=1)
    dates = []
    while d.year == year:
        dates.append(d.isoformat())
        d += timedelta(days=7)
    return dates


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    d = next_month - timedelta(days=1)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def consumer_confidence_dates_for_year(year: int) -> list[str]:
    """Last Tuesday of each month — confirmed rule from the Conference
    Board's own site, cross-checked against two real 2026 dates."""
    return [_last_weekday_of_month(year, m, 1).isoformat() for m in range(1, 13)]


ISM_MANUFACTURING_2026_DATES = ism_manufacturing_dates_for_year(2026)
ISM_SERVICES_2026_DATES = ism_services_dates_for_year(2026)
INITIAL_JOBLESS_CLAIMS_2026_DATES = jobless_claims_thursdays_for_year(2026)
CONSUMER_CONFIDENCE_2026_DATES = consumer_confidence_dates_for_year(2026)

# Known holiday-shift override: the computed "1st business day" rule lands
# on Jan 1, 2026 (New Year's Day itself). Real confirmed ISM date: Jan 5.
if ISM_MANUFACTURING_2026_DATES and ISM_MANUFACTURING_2026_DATES[0] == "2026-01-01":
    ISM_MANUFACTURING_2026_DATES[0] = "2026-01-05"


# ---------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------

def _next_from(dates: list[str], from_date: str) -> str | None:
    upcoming = [d for d in dates if d >= from_date]
    return upcoming[0] if upcoming else None


def next_fomc_date(from_date: str) -> str | None:
    return _next_from(FOMC_2026_DATES, from_date)


def next_cpi_date(from_date: str) -> str | None:
    return _next_from(CPI_2026_DATES_CONFIRMED, from_date)


def next_ppi_date(from_date: str) -> str | None:
    return _next_from(PPI_2026_DATES_CONFIRMED, from_date)


def next_nonfarm_payrolls_date(from_date: str) -> str | None:
    return _next_from(NONFARM_PAYROLLS_2026_DATES, from_date)


def next_unemployment_date(from_date: str) -> str | None:
    return _next_from(UNEMPLOYMENT_2026_DATES, from_date)


def next_retail_sales_date(from_date: str) -> str | None:
    return _next_from(RETAIL_SALES_2026_DATES, from_date)


def next_industrial_production_date(from_date: str) -> str | None:
    return _next_from(INDUSTRIAL_PRODUCTION_2026_DATES, from_date)


def next_pce_date(from_date: str) -> str | None:
    return _next_from(PCE_2026_DATES_CONFIRMED, from_date)


def next_gdp_date(from_date: str) -> str | None:
    return _next_from(GDP_2026_DATES_CONFIRMED, from_date)


def next_housing_starts_date(from_date: str) -> str | None:
    return _next_from(HOUSING_STARTS_2026_DATES_CONFIRMED, from_date)


def next_consumer_sentiment_prelim_date(from_date: str) -> str | None:
    return _next_from(MICHIGAN_SENTIMENT_PRELIM_2026_DATES, from_date)


def next_consumer_sentiment_final_date(from_date: str) -> str | None:
    return _next_from(MICHIGAN_SENTIMENT_FINAL_2026_DATES, from_date)


def next_jolts_date(from_date: str) -> str | None:
    return _next_from(JOLTS_2026_DATES_CONFIRMED, from_date)


def next_durable_goods_date(from_date: str) -> str | None:
    return _next_from(DURABLE_GOODS_2026_DATES_CONFIRMED, from_date)


def next_trade_balance_date(from_date: str) -> str | None:
    return _next_from(TRADE_BALANCE_2026_DATES_CONFIRMED, from_date)


def next_ism_manufacturing_date(from_date: str) -> str | None:
    return _next_from(ISM_MANUFACTURING_2026_DATES, from_date)


def next_ism_services_date(from_date: str) -> str | None:
    return _next_from(ISM_SERVICES_2026_DATES, from_date)


def next_initial_jobless_claims_date(from_date: str) -> str | None:
    return _next_from(INITIAL_JOBLESS_CLAIMS_2026_DATES, from_date)


def next_consumer_confidence_date(from_date: str) -> str | None:
    return _next_from(CONSUMER_CONFIDENCE_2026_DATES, from_date)
