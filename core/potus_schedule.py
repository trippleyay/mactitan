"""
Live POTUS schedule check — same category of tool as core/fed_speeches.py:
a live fetch at query time, not a pre-built calendar, because this data
genuinely isn't published far enough in advance to hardcode.

SOURCE, AND WHY IT'S HONEST TO USE: the White House's own current site does
not publish a structured advance schedule (that practice existed on the
Obama-era site, archived, not the live one). Factba.se/Roll Call — a
credible, established political-journalism tracker (founded 2017, acquired
by FiscalNote, used by working political journalists, not an anonymous
scraper) — republishes the White House's day-of schedule as a public Google
Calendar in standard ICS format. This is a third-party source, not the
government directly, but a credible and technically clean one: no auth, no
rate limiting, structured data, independently confirmed working by a real
project (github.com/PatrickJamesYoung/MIP-Calendar, live-tested against 22
real events for a specific date).

REAL LIMITATION, not a bug: this can only ever answer "what's on the
schedule right now" — because that's literally the only thing that exists.
It cannot tell you what POTUS is doing three weeks from now (that schedule
doesn't exist yet anywhere), and it's not a reliable historical archive
either (it's a rolling calendar, not built for looking backward). This is
fundamentally different from next_cpi_date() and friends, which answer the
same way regardless of when you ask.
"""

from datetime import datetime, timedelta, timezone

import requests
from icalendar import Calendar

FACTBASE_ICS_URL = (
    "https://calendar.google.com/calendar/ical/"
    "cantymedia.com_62fqfmv1eejqs9hntbr6hof5kc%40group.calendar.google.com/"
    "public/basic.ics"
)

# Known pool-status phrases the source uses — extracted only on an exact
# match so free-form description text isn't misread as one of these.
_POOL_PHRASES = (
    "Out-of-Town Travel Pool", "In-Town Pool", "Open Press", "Closed Press",
    "Pre-Credentialed Media", "Restricted Press", "Travel Pool",
)


def fetch_potus_schedule(timeout: int = 10) -> list[dict]:
    """
    Fetch and parse the live Factba.se/Roll Call White House schedule feed.

    Returns a list of dicts in chronological order:
        {"time_et": str, "description": str, "pool_status": str | None,
         "datetime_utc": str (ISO)}

    Raises requests.HTTPError on a failed fetch.
    """
    resp = requests.get(FACTBASE_ICS_URL, timeout=timeout, headers={"Cache-Control": "no-cache"})
    resp.raise_for_status()

    cal = Calendar.from_ical(resp.content)
    items = []

    for component in cal.walk("VEVENT"):
        dtstart = component.get("DTSTART")
        if dtstart is None:
            continue
        dt = dtstart.dt
        if not isinstance(dt, datetime):
            continue  # skip all-day/date-only entries, not a scheduled item with a real time
        dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        summary = str(component.get("SUMMARY") or "").strip()
        if not summary:
            continue

        description_field = component.get("DESCRIPTION")
        pool_status = None
        if description_field:
            first_line = str(description_field).splitlines()[0].strip()
            if first_line in _POOL_PHRASES:
                pool_status = first_line

        # Display as ET. Uses a simple March-November DST approximation
        # (not exact to the minute DST switches over, but correct for all
        # but a few hours each year) rather than the hardcoded EST-only
        # offset this had at first, which would have mislabeled every
        # summer entry by an hour.
        is_likely_edt = 3 <= dt_utc.month <= 11
        et_offset = timedelta(hours=-4 if is_likely_edt else -5)
        et_dt = dt_utc + et_offset

        items.append({
            "time_et": et_dt.strftime("%-I:%M %p ET"),
            "description": summary,
            "pool_status": pool_status,
            "datetime_utc": dt_utc.isoformat(),
        })

    items.sort(key=lambda it: it["datetime_utc"])
    return items


def get_todays_potus_schedule() -> list[dict]:
    """
    Convenience wrapper: only today's entries (UTC calendar day — a rough
    approximation of "today," since the source's own day boundary handling
    isn't independently confirmed here). For anything requiring precise
    ET day-boundary handling, use fetch_potus_schedule() directly and
    filter against a properly computed ET window.
    """
    all_items = fetch_potus_schedule()
    today_utc = datetime.now(timezone.utc).date()
    return [
        it for it in all_items
        if datetime.fromisoformat(it["datetime_utc"]).date() == today_utc
    ]
