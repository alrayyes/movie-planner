"""Fuzzy duplicate detection: normalized title matching gated to the same
day, so a legitimate rewatch on a different day is never flagged. See
design.md's "Duplicate matching" decision for the same-day-over-window and
threshold rationale.
"""

import re
import string
from datetime import date

from rapidfuzz import fuzz

from movie_planner.store import Entry

DEFAULT_THRESHOLD = 90.0

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


def find_duplicate(
    title: str,
    entry_date: date,
    existing: list[Entry],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> Entry | None:
    normalized_candidate = normalize_title(title)
    for entry in existing:
        if entry.date != entry_date:
            continue
        score = fuzz.token_sort_ratio(normalized_candidate, normalize_title(entry.title))
        if score >= threshold:
            return entry
    return None
