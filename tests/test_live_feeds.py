"""
Tests the two live-fetch tools (Fed speeches, POTUS schedule) against real
network access. These are the two tools in this codebase that hit a live
feed at call time rather than a pre-built list, and neither has been
verified against a real fetch yet — this sandbox can't reach either
federalreserve.gov or calendar.google.com.

Usage:
    python3 tests/test_live_feeds.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.fed_speeches import fetch_fed_speeches, get_recent_fed_speeches
from core.potus_schedule import fetch_potus_schedule

SEPARATOR = "=" * 60


def test_fed_speeches():
    print(SEPARATOR)
    print("Fed speeches feed — real fetch")
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

    # Check that the speaker extraction actually found SOMEONE, not just
    # None for every entry — if every speaker is None, the name-matching
    # heuristic in fed_speeches.py needs fixing against the real title format.
    matched = sum(1 for s in speeches if s["speaker"])
    print(f"Speaker successfully identified in {matched}/{len(speeches)} entries")
    if matched == 0 and speeches:
        print("  [WARNING] Zero speakers matched — check the real title format against KNOWN_FED_OFFICIALS")
    print()


def test_potus_schedule():
    print(SEPARATOR)
    print("POTUS schedule feed — real fetch")
    print(SEPARATOR)
    schedule = fetch_potus_schedule()
    print(f"Got {len(schedule)} entries. First 5:")
    for item in schedule[:5]:
        print(f"  {item}")
    print()
    print("Check: do the time_et values look like real, sensible clock times?")
    print("Check: does datetime_utc look correctly ordered (chronological)?")


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
    print("Done. These two feeds were never verified against real network access before this.")
