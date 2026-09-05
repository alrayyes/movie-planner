"""Fuzzy duplicate detection: normalized title matching gated to the same
day, so a legitimate rewatch on a different day is never flagged, plus a
title-independent check for two same-day screenings whose times overlap -
a real-world impossibility regardless of how the titles compare. See
design.md's "Duplicate matching" decision for the same-day-over-window and
threshold rationale.
"""

import re
import string
from datetime import date, datetime, time, timedelta

from rapidfuzz import fuzz

from movie_planner.store import Entry

DEFAULT_THRESHOLD = 90.0

# How much slack two screening times get before they count as
# "overlapping" - loose enough that slightly-off showtimes from different
# sources don't false-positive, tight enough to catch a real conflict.
_OVERLAP_BUFFER = timedelta(minutes=30)

# Arbitrary shared date used only to do time-of-day arithmetic with
# datetime/timedelta - date.py has no time-only delta type of its own.
_ARBITRARY_DATE = date(2000, 1, 1)

# Noise picked up from import sources - matched at the end, case-insensitive.
_NOISE_SUFFIXES = (" - movies",)

_PUNCTUATION_RE = re.compile(f"[{re.escape(string.punctuation)}]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    normalized = title.strip().casefold()
    for suffix in _NOISE_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    normalized = _PUNCTUATION_RE.sub("", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def _buffered_range(start: time, end: time | None) -> tuple[datetime, datetime]:
    # A bare start with no end is a zero-width point in time, not an
    # assumed duration - buffering it either side is what gives it any
    # width at all.
    start_dt = datetime.combine(_ARBITRARY_DATE, start)
    end_dt = datetime.combine(_ARBITRARY_DATE, end) if end else start_dt
    return start_dt - _OVERLAP_BUFFER, end_dt + _OVERLAP_BUFFER


def _times_overlap(
    candidate_start: time | None,
    candidate_end: time | None,
    entry_start: time | None,
    entry_end: time | None,
) -> bool:
    if candidate_start is None or entry_start is None:
        return False
    a_start, a_end = _buffered_range(candidate_start, candidate_end)
    b_start, b_end = _buffered_range(entry_start, entry_end)
    return a_start < b_end and b_start < a_end


def find_duplicate(
    title: str,
    entry_date: date,
    existing: list[Entry],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    start_time: time | None = None,
    end_time: time | None = None,
) -> Entry | None:
    normalized_candidate = normalize_title(title)
    for entry in existing:
        if entry.date != entry_date:
            continue
        score = fuzz.token_sort_ratio(normalized_candidate, normalize_title(entry.title))
        if score >= threshold:
            return entry
        if _times_overlap(start_time, end_time, entry.start_time, entry.end_time):
            return entry
    return None
