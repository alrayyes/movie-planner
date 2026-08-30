from datetime import date

import pytest

from movie_planner.duplicates import find_duplicate, normalize_title
from movie_planner.store import Entry


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("The Housemaid", "the housemaid"),
        ("Ready or Not 2: Here I Come - Movies", "ready or not 2 here i come"),
        ("Ready or Not 2: Here I Come", "ready or not 2 here i come"),
        ("Loverboy: Vertrouw Niemand", "loverboy vertrouw niemand"),
        ("  Good Boy  ", "good boy"),
    ],
)
def test_normalize_title(title: str, expected: str) -> None:
    assert normalize_title(title) == expected


def _entry(entry_id: int, title: str, entry_date: date) -> Entry:
    return Entry(
        id=entry_id,
        title=title,
        date=entry_date,
        start_time=None,
        end_time=None,
        medium_id=1,
        venue_id=None,
        caldav_uid=None,
    )


def test_find_duplicate_same_title_same_day_is_flagged() -> None:
    existing = [_entry(1, "Ready or Not 2: Here I Come - Movies", date(2026, 3, 29))]

    match = find_duplicate("Ready or Not 2: Here I Come", date(2026, 3, 29), existing)

    assert match is existing[0]


def test_find_duplicate_same_title_different_day_not_flagged() -> None:
    existing = [_entry(1, "The Housemaid", date(2026, 1, 3))]

    match = find_duplicate("The Housemaid", date(2026, 6, 1), existing)

    assert match is None


def test_find_duplicate_different_title_same_day_not_flagged() -> None:
    existing = [_entry(1, "The Housemaid", date(2026, 1, 3))]

    match = find_duplicate("Cold Storage", date(2026, 1, 3), existing)

    assert match is None


def test_find_duplicate_respects_configurable_threshold() -> None:
    existing = [_entry(1, "The Housemaid", date(2026, 1, 3))]

    # "The House" is a loose partial match - passes a low threshold, not the
    # high default.
    assert find_duplicate("The House", date(2026, 1, 3), existing, threshold=50) is existing[0]
    assert find_duplicate("The House", date(2026, 1, 3), existing, threshold=95) is None


def test_find_duplicate_with_no_existing_entries() -> None:
    assert find_duplicate("Anything", date(2026, 1, 1), []) is None
