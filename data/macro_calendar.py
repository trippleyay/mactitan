"""
Forward-looking macro event calendar.

MAINTENANCE: these are the real, confirmed 2026 dates as of this writing.
Update yearly when the Fed/BLS publish next year's schedule:
- FOMC: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- CPI:  https://www.bls.gov/schedule/news_release/current_year.asp
"""

# Fully confirmed, official 2026 FOMC meeting dates (decision announced on
# the second day of each two-day meeting, 2:00pm ET).
FOMC_2026_DATES = [
    "2026-01-28",  # meeting Jan 27-28
    "2026-03-18",  # meeting Mar 17-18
    "2026-04-29",  # meeting Apr 28-29
    "2026-06-17",  # meeting Jun 16-17
    "2026-07-29",  # meeting Jul 28-29
    "2026-09-16",  # meeting Sep 15-16
    "2026-10-28",  # meeting Oct 27-28
    "2026-12-09",  # meeting Dec 8-9
]

# Fully confirmed, official 2026 CPI release dates (BLS publishes CPI for
# reference month M in month M+1 or M+2; exact day varies, not estimated).
CPI_2026_DATES_CONFIRMED = [
    "2026-01-13",  # December 2025 data
    "2026-02-13",  # January 2026 data
    "2026-03-11",  # February 2026 data
    "2026-04-10",  # March 2026 data
    "2026-05-12",  # April 2026 data
    "2026-06-10",  # May 2026 data
    "2026-07-14",  # June 2026 data
    "2026-08-12",  # July 2026 data
    "2026-09-11",  # August 2026 data
    "2026-10-14",  # September 2026 data
    "2026-11-10",  # October 2026 data
    "2026-12-10",  # November 2026 data
]


def next_fomc_date(from_date: str) -> str | None:
    """Given today's date (YYYY-MM-DD), return the next FOMC decision date, or None if past the known list."""
    upcoming = [d for d in FOMC_2026_DATES if d >= from_date]
    return upcoming[0] if upcoming else None


def next_cpi_date(from_date: str) -> str | None:
    """
    Given today's date, return the next known CPI release date from the
    confirmed list. Returns None if no confirmed date is available past
    from_date — this means the answer isn't known yet, not that there's no
    upcoming release; check the BLS schedule link above to fill the gap.
    """
    upcoming = [d for d in CPI_2026_DATES_CONFIRMED if d >= from_date]
    return upcoming[0] if upcoming else None