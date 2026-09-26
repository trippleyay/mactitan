"""
Live Fed speech feed — genuinely different from every other module in this
codebase. Everything else (macro_calendar.py, macro_data.py) looks up a
pre-built list, because CPI/FOMC/etc are scheduled months in advance and
published that way. Fed speeches by individual officials are NOT published
as a full-year calendar — the Fed's own site only shows what's scheduled
roughly 1-2 months out, filled in on a rolling basis. So this module fetches
the Fed's real, official speeches RSS feed live, at query time, rather than
consulting a static list.

Feed URL confirmed real: https://www.federalreserve.gov/feeds/speeches.xml
(independently verified via a third-party project that parses it
programmatically). Known limitation of the feed itself, not this code:
it carries roughly the 20 most recent items — a rolling window, not a full
archive. Good for "what's recent or coming up soon," not for building a
long historical dataset the way the calendar-based indicators work.

UNVERIFIED: this sandbox cannot reach federalreserve.gov, so the exact XML
field structure below is written defensively from RSS's general spec, not
confirmed against a live fetch. Run tests/test_fed_speeches.py on a machine
with real network access to confirm the actual shape and fix anything that
doesn't match.
"""

import re
import xml.etree.ElementTree as ET

import requests

FEED_URL = "https://www.federalreserve.gov/feeds/speeches.xml"

# Known Fed officials as of this writing — used to extract the speaker's
# name from the entry title/description, since the feed's exact field
# layout isn't confirmed. Update this list when the Board's composition
# changes (see https://www.federalreserve.gov/aboutthefed/bios/board/ ).
KNOWN_FED_OFFICIALS = [
    "Jerome H. Powell", "Powell",
    "Philip N. Jefferson", "Jefferson",
    "Michelle W. Bowman", "Bowman",
    "Michael S. Barr", "Barr",
    "Lisa D. Cook", "Cook",
    "Christopher J. Waller", "Waller",
    "Stephen I. Miran", "Miran",
]


def _extract_speaker(text: str) -> str | None:
    """Best-effort match of a known Fed official's name within a text field."""
    for name in KNOWN_FED_OFFICIALS:
        if name in text:
            return name
    return None


def fetch_fed_speeches(timeout: int = 10) -> list[dict]:
    """
    Fetch and parse the Fed's live speeches RSS feed.

    Returns a list of dicts, most recent first:
        {"title": str, "speaker": str | None, "date": str (ISO if parseable,
         else raw), "link": str, "summary": str}

    Raises requests.HTTPError on a failed fetch. Does not raise on
    individual malformed entries — those are skipped, not fatal.
    """
    resp = requests.get(FEED_URL, timeout=timeout)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    items = root.findall(".//item")

    results = []
    for item in items:
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")
        desc_el = item.find("description")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        pubdate_raw = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else ""
        summary = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        speaker = _extract_speaker(title) or _extract_speaker(summary)

        # Try to normalize the RSS pubDate (RFC 2822 format, e.g.
        # "Thu, 03 Sep 2026 14:00:00 EST") into ISO — fall back to the raw
        # string if the format doesn't match what's expected, rather than
        # crashing on one malformed entry.
        date_iso = pubdate_raw
        match = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", pubdate_raw)
        if match:
            day, mon_str, year = match.groups()
            months = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                      "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                      "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
            if mon_str in months:
                date_iso = f"{year}-{months[mon_str]}-{day.zfill(2)}"

        results.append({
            "title": title,
            "speaker": speaker,
            "date": date_iso,
            "link": link,
            "summary": summary,
        })

    return results


def get_recent_fed_speeches(speaker_filter: str | None = None, limit: int = 10) -> list[dict]:
    """
    Convenience wrapper: recent Fed speeches, optionally filtered to one
    official (e.g. speaker_filter="Powell" for just the Fed Chair — the
    highest market-moving speaker per the product's own framing).
    """
    speeches = fetch_fed_speeches()
    if speaker_filter:
        speeches = [s for s in speeches if s["speaker"] and speaker_filter.lower() in s["speaker"].lower()]
    return speeches[:limit]
