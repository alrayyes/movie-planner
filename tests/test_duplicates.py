from datetime import date

import pytest

from movie_planner.duplicates import find_duplicate, normalize_title
from movie_planner.store import Entry


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("The Clockmaker's Daughter", "the clockmakers daughter"),
        ("Midnight Ferry: Part Two - Movies", "midnight ferry part two"),
        ("Midnight Ferry: Part Two", "midnight ferry part two"),
        ("Nightfall Junction: No One Returns", "nightfall junction no one returns"),
        ("  Quiet Static  ", "quiet static"),
    ],
)
def test_normalize_title(title: str, expected: str) -> None:
    assert normalize_title(title) == expected


def _entry(entry_id: int, title: str, entry_date: date) -> Entry:
    return Entry(id=entry_id, title=title, date=entry_date, medium_id=1)


def test_find_duplicate_same_title_same_day_is_flagged() -> None:
    existing = [_entry(1, "Midnight Ferry: Part Two - Movies", date(2024, 8, 10))]

    match = find_duplicate("Midnight Ferry: Part Two", date(2024, 8, 10), existing)

    assert match is existing[0]


def test_find_duplicate_same_title_different_day_not_flagged() -> None:
    existing = [_entry(1, "The Clockmaker's Daughter", date(2024, 3, 15))]

    match = find_duplicate("The Clockmaker's Daughter", date(2024, 11, 5), existing)

    assert match is None


def test_find_duplicate_different_title_same_day_not_flagged() -> None:
    existing = [_entry(1, "The Clockmaker's Daughter", date(2024, 3, 15))]

    match = find_duplicate("Glass Horizon", date(2024, 3, 15), existing)

    assert match is None


def test_find_duplicate_respects_configurable_threshold() -> None:
    existing = [_entry(1, "The Clockmaker's Daughter", date(2024, 3, 15))]

    # A loose partial match - passes a low threshold, not the high default.
    assert (
        find_duplicate("The Clockmaker", date(2024, 3, 15), existing, threshold=50) is existing[0]
    )
    assert find_duplicate("The Clockmaker", date(2024, 3, 15), existing, threshold=95) is None


def test_find_duplicate_with_no_existing_entries() -> None:
    assert find_duplicate("Anything", date(2024, 1, 1), []) is None
