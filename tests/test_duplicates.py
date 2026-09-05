from datetime import date, time

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


def _entry(
    entry_id: int,
    title: str,
    entry_date: date,
    *,
    start_time: time | None = None,
    end_time: time | None = None,
) -> Entry:
    return Entry(
        id=entry_id,
        title=title,
        date=entry_date,
        medium_id=1,
        start_time=start_time,
        end_time=end_time,
    )


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


# --- time-overlap detection: specs/duplicate-detection's delta ---


def test_overlapping_times_different_titles_is_flagged() -> None:
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(19, 0), end_time=time(21, 0))
    ]

    match = find_duplicate(
        "Nightfall Junction",
        date(2024, 3, 15),
        existing,
        start_time=time(19, 30),
        end_time=time(21, 30),
    )

    assert match is existing[0]


def test_overlapping_times_same_title_is_flagged() -> None:
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(19, 0), end_time=time(21, 0))
    ]

    match = find_duplicate(
        "Glass Horizon",
        date(2024, 3, 15),
        existing,
        start_time=time(19, 15),
        end_time=time(21, 15),
    )

    assert match is existing[0]


def test_same_day_no_time_overlap_not_flagged() -> None:
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(14, 0), end_time=time(16, 0))
    ]

    match = find_duplicate(
        "Nightfall Junction",
        date(2024, 3, 15),
        existing,
        start_time=time(20, 0),
        end_time=time(22, 0),
    )

    assert match is None


def test_candidate_with_no_start_time_is_not_checked_for_overlap() -> None:
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(19, 0), end_time=time(21, 0))
    ]

    match = find_duplicate("Nightfall Junction", date(2024, 3, 15), existing)

    assert match is None


def test_existing_entry_with_no_start_time_is_not_checked_for_overlap() -> None:
    existing = [_entry(1, "Glass Horizon", date(2024, 3, 15))]

    match = find_duplicate(
        "Nightfall Junction",
        date(2024, 3, 15),
        existing,
        start_time=time(19, 0),
        end_time=time(21, 0),
    )

    assert match is None


def test_a_bare_start_time_is_treated_as_a_point_not_an_assumed_duration() -> None:
    # Existing entry: a bare start_time, no end_time - a zero-width point,
    # buffered by 30 minutes either side. 18:45 is inside that buffer;
    # 18:00 (an hour before) is not.
    existing = [_entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(19, 0))]

    close = find_duplicate(
        "Nightfall Junction", date(2024, 3, 15), existing, start_time=time(18, 45)
    )
    far = find_duplicate("Nightfall Junction", date(2024, 3, 15), existing, start_time=time(18, 0))

    assert close is existing[0]
    assert far is None


def test_times_just_outside_the_buffer_are_not_flagged() -> None:
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(19, 0), end_time=time(21, 0))
    ]

    # Existing's buffered range ends at 21:30 (21:00 + 30min). A candidate
    # starting at 22:01 has its own buffered range starting at 21:31 -
    # just past that, so the two don't overlap.
    match = find_duplicate(
        "Nightfall Junction",
        date(2024, 3, 15),
        existing,
        start_time=time(22, 1),
        end_time=time(23, 30),
    )

    assert match is None
