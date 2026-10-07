"""
Live POTUS schedule check. Same category as core/fed_speeches.py: it shows
what is published right now, not a forward calendar, because the schedule
is only published day-of.

SOURCE: Factba.se / Roll Call (an established political-journalism tracker)
republishes the White House day-of schedule as a public Google Calendar in
ICS format. This is a third-party source, not the government directly.

MEASURED BEHAVIOR OF THE SOURCE (from a real test, not assumed):
the ICS file is about 10.9 MB, Google takes about 34 seconds to send the
first byte, and the full download takes about 90 seconds. It is not
blocked. Any client with a short timeout fails, a browser just waits.

DESIGN, because of that:
- A background thread downloads the file every 10 minutes and stores the
  small slice that matters (a window around today) in potus_cache.json.
- The chat tool only reads that cache, so it answers instantly and never
  waits 90 seconds inside a request.
- The file is streamed to disk and parsed line by line, so memory stays low
  (a t3.nano has 512 MB; loading 10 MB into a calendar library would not be safe).
- Cached data older than 3 hours is refused instead of shown, because a
  stale day-of schedule is worse than none.

KNOWN GAPS (not verified against the real file):
- Recurring events (RRULE) are counted and logged but not expanded.
- Events with no time zone are assumed to be UTC.
- All-day entries are skipped.
"""

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    from zoneinfo import ZoneInfo
except ImportError:  # very old Python
    ZoneInfo = None

log = logging.getLogger("mactitan.potus")

FACTBASE_ICS_URL = (
    "https://calendar.google.com/calendar/ical/"
    "cantymedia.com_62fqfmv1eejqs9hntbr6hof5kc%40group.calendar.google.com/"
    "public/basic.ics"
)

CACHE_PATH = Path(__file__).parent.parent / "potus_cache.json"

REFRESH_INTERVAL_SECONDS = 600
RETRY_INTERVAL_SECONDS = 120
MAX_CACHE_AGE_SECONDS = 3 * 3600
WINDOW_DAYS_BACK = 2
WINDOW_DAYS_FORWARD = 14
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 120          # max wait between chunks; first byte took ~34s in testing
TOTAL_DEADLINE_SECONDS = 300

_POOL_PHRASES = (
    "Out-of-Town Travel Pool", "In-Town Pool", "Open Press", "Closed Press",
    "Pre-Credentialed Media", "Restricted Press", "Travel Pool",
)


class PotusScheduleUnavailable(Exception):
    """Raised when there is no usable schedule data to show right now."""


# ---------------------------------------------------------------------
# Parsing (streaming, low memory)
# ---------------------------------------------------------------------

def _unfolded_lines(path):
    """Yield ICS lines with folded continuation lines joined back together."""
    pending = None
    with open(path, "rb") as f:
        for raw in f:
            line = raw.rstrip(b"\r\n").decode("utf-8", errors="replace")
            if line[:1] in (" ", "\t") and pending is not None:
                pending += line[1:]
                continue
            if pending is not None:
                yield pending
            pending = line
    if pending is not None:
        yield pending


def _unescape(value):
    out = []
    i = 0
    while i < len(value):
        c = value[i]
        if c == "\\" and i + 1 < len(value):
            n = value[i + 1]
            out.append("\n" if n in "nN" else n)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _split_property(line):
    head, sep, value = line.partition(":")
    if not sep:
        return None
    parts = head.split(";")
    params = {}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        params[k.upper()] = v.strip('"')
    return parts[0].upper(), params, value


def _parse_dtstart(params, value):
    if params.get("VALUE", "").upper() == "DATE" or len(value) == 8:
        return None  # all-day entry, no time
    try:
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        naive = datetime.strptime(value, "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    tzid = params.get("TZID")
    if tzid and ZoneInfo:
        try:
            return naive.replace(tzinfo=ZoneInfo(tzid)).astimezone(timezone.utc)
        except Exception:
            pass
    return naive.replace(tzinfo=timezone.utc)


def _eastern(dt_utc):
    if ZoneInfo:
        try:
            return dt_utc.astimezone(ZoneInfo("America/New_York"))
        except Exception:
            pass
    return dt_utc + timedelta(hours=-4 if 3 <= dt_utc.month <= 11 else -5)


def _format_et(dt_utc):
    return _eastern(dt_utc).strftime("%-I:%M %p ET")


def _finish_event(current, start_utc, end_utc):
    dt = current.get("dtstart")
    summary = current.get("summary")
    if dt is None or not summary:
        return None
    if not (start_utc <= dt < end_utc):
        return None
    desc = (current.get("description") or "").strip()
    first = desc.splitlines()[0].strip() if desc else ""
    return {
        "time_et": _format_et(dt),
        "description": summary,
        "pool_status": first if first in _POOL_PHRASES else None,
        "datetime_utc": dt.isoformat(),
    }


def parse_ics_window(path, start_utc, end_utc):
    """
    Stream through an ICS file and keep only events starting inside
    [start_utc, end_utc). Returns (events sorted by time, stats dict).
    """
    events = []
    stats = {"total": 0, "recurring_not_expanded": 0}
    in_event = False
    nested_depth = 0
    current = None

    for line in _unfolded_lines(path):
        if line == "BEGIN:VEVENT":
            in_event, nested_depth, current = True, 0, {}
            stats["total"] += 1
            continue
        if not in_event:
            continue
        if line == "END:VEVENT":
            in_event = False
            if current.get("rrule"):
                stats["recurring_not_expanded"] += 1
            ev = _finish_event(current, start_utc, end_utc)
            if ev:
                events.append(ev)
            current = None
            continue
        if line.startswith("BEGIN:"):      # e.g. VALARM inside an event
            nested_depth += 1
            continue
        if line.startswith("END:"):
            nested_depth = max(0, nested_depth - 1)
            continue
        if nested_depth:
            continue

        prop = _split_property(line)
        if not prop:
            continue
        name, params, value = prop
        if name == "DTSTART" and "dtstart" not in current:
            current["dtstart"] = _parse_dtstart(params, value)
        elif name == "SUMMARY":
            current["summary"] = _unescape(value).strip()
        elif name == "DESCRIPTION":
            current["description"] = _unescape(value)
        elif name == "RRULE":
            current["rrule"] = True

    events.sort(key=lambda e: e["datetime_utc"])
    return events, stats


# ---------------------------------------------------------------------
# Download + cache
# ---------------------------------------------------------------------

def _download_ics(dest_path):
    started = time.monotonic()
    with requests.get(
        FACTBASE_ICS_URL, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
    ) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as out:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    out.write(chunk)
                if time.monotonic() - started > TOTAL_DEADLINE_SECONDS:
                    raise PotusScheduleUnavailable("Download exceeded the total time limit.")


def _write_cache(events, fetched_at, stats):
    payload = {
        "fetched_at_utc": fetched_at.isoformat(),
        "fetched_at_epoch": fetched_at.timestamp(),
        "stats": stats,
        "items": events,
    }
    tmp = str(CACHE_PATH) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, CACHE_PATH)


def _read_cache():
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return None


_refresh_lock = threading.Lock()


def refresh_potus_schedule():
    """
    Blocking: download the full feed (about 90 seconds), parse the window
    around today, write the cache. Used by the background thread and by
    `python3 -m core.potus_schedule`.
    """
    if not _refresh_lock.acquire(blocking=False):
        raise PotusScheduleUnavailable("A refresh is already in progress.")
    tmp_path = None
    try:
        now = datetime.now(timezone.utc)
        fd, tmp_path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        _download_ics(tmp_path)
        events, stats = parse_ics_window(
            tmp_path,
            now - timedelta(days=WINDOW_DAYS_BACK),
            now + timedelta(days=WINDOW_DAYS_FORWARD),
        )
        _write_cache(events, now, stats)
        log.info("POTUS schedule refreshed: %d events in window (%s)", len(events), stats)
        return events
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        _refresh_lock.release()


_bg_started = False
_bg_guard = threading.Lock()


def _refresh_loop():
    cache = _read_cache()
    if cache:
        age = time.time() - cache.get("fetched_at_epoch", 0)
        time.sleep(max(0, REFRESH_INTERVAL_SECONDS - age))
    while True:
        try:
            refresh_potus_schedule()
            delay = REFRESH_INTERVAL_SECONDS
        except Exception as e:
            log.warning("POTUS schedule refresh failed: %s", e)
            delay = RETRY_INTERVAL_SECONDS
        time.sleep(delay)


def ensure_background_refresh():
    """Start the refresh thread once per process. Safe to call repeatedly."""
    global _bg_started
    with _bg_guard:
        if _bg_started:
            return
        _bg_started = True
    threading.Thread(target=_refresh_loop, name="potus-refresh", daemon=True).start()


# ---------------------------------------------------------------------
# What the chat tool calls: instant, reads the cache only
# ---------------------------------------------------------------------

def fetch_potus_schedule():
    """
    Return the cached schedule window (list of dicts, chronological), each
    stamped with as_of_utc (when the data was downloaded). Never waits on
    the network. Raises PotusScheduleUnavailable if there is nothing usable.
    """
    ensure_background_refresh()
    cache = _read_cache()
    if cache is None:
        raise PotusScheduleUnavailable(
            "The schedule feed is loading for the first time. The source file is large "
            "and takes 1 to 2 minutes to download. Ask again in a couple of minutes."
        )
    age = time.time() - cache.get("fetched_at_epoch", 0)
    if age > MAX_CACHE_AGE_SECONDS:
        raise PotusScheduleUnavailable(
            f"The schedule data was last refreshed about {int(age // 3600)} hours ago and "
            "recent refreshes have failed, so it is not being shown."
        )
    as_of = cache["fetched_at_utc"]
    return [dict(item, as_of_utc=as_of) for item in cache["items"]]


def get_todays_potus_schedule():
    """Only entries that fall on today's date in Eastern Time."""
    today_et = _eastern(datetime.now(timezone.utc)).date()
    return [
        it for it in fetch_potus_schedule()
        if _eastern(datetime.fromisoformat(it["datetime_utc"])).date() == today_et
    ]


if __name__ == "__main__":
    # Run from the project root: python3 -m core.potus_schedule
    logging.basicConfig(level=logging.INFO)
    t0 = time.monotonic()
    result = refresh_potus_schedule()
    print(f"Downloaded and parsed in {time.monotonic() - t0:.0f}s. "
          f"{len(result)} events in the window. First 10:")
    for e in result[:10]:
        print(" ", e)
