"""
Tests the two live feeds against real network access.

The POTUS part downloads the full source file (about 11 MB, roughly 1 to 2
minutes because Google is slow to respond), so expect this script to sit
quietly for a while on that step.

Usage:
    python3 tests/test_live_feeds.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.fed_speeches import fetch_fed_speeches, get_recent_fed_speeches
from core.potus_schedule import refresh_potus_schedule

SEPARATOR = "=" * 60


def test_fed_speeches():
    print(SEPARATOR)
    print("Fed speeches feed, real fetch")
    print(SEPARATOR)
    speeches = fetch_fed_speeches()
    print(f"Got {len(speeches)} entries. First 3:")
    for s in speeches[:3]:
        print(f"  {s}")
    print()

    powell_only = get_recent_fed_speeches(speaker_filter="Powell")
    print(f"Powell-filtered: {len(powell_only)} entries")
    for s in powell_only[:3]:
        print(f"  {s}")
    print()

    matched = sum(1 for s in speeches if s["speaker"])
    print(f"Speaker identified in {matched}/{len(speeches)} entries")
    print()


def test_potus_schedule():
    print(SEPARATOR)
    print("POTUS schedule feed, real download (1 to 2 minutes)")
    print(SEPARATOR)
    started = time.monotonic()
    events = refresh_potus_schedule()
    print(f"Downloaded and parsed in {time.monotonic() - started:.0f}s")
    print(f"{len(events)} events in the window (2 days back to 14 days ahead). First 8:")
    for item in events[:8]:
        print(f"  {item}")
    print()
    print("Check: are the times sensible, and is today's schedule in there?")


if __name__ == "__main__":
    try:
        test_fed_speeches()
    except Exception as e:
        print(f"[FAILED] Fed speeches: {e}\n")

    try:
        test_potus_schedule()
    except Exception as e:
        print(f"[FAILED] POTUS schedule: {e}\n")

    print(SEPARATOR)
    print("Done.")
