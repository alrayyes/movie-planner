import logging
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


def test_duplicate_match_logs_the_score_at_debug_level(caplog: pytest.LogCaptureFixture) -> None:
    existing = [_entry(1, "Glass Horizon", date(2024, 3, 15))]

    with caplog.at_level(logging.DEBUG, logger="movie_planner.duplicates"):
        match = find_duplicate("Glass Horizon", date(2024, 3, 15), existing)

    assert match is existing[0]
    assert any("Glass Horizon" in r.message and "score" in r.message for r in caplog.records)


def test_duplicate_miss_logs_no_match_found(caplog: pytest.LogCaptureFixture) -> None:
    existing = [_entry(1, "Glass Horizon", date(2024, 3, 15))]

    with caplog.at_level(logging.DEBUG, logger="movie_planner.duplicates"):
        match = find_duplicate("Nightfall Junction", date(2024, 3, 15), existing)

    assert match is None
    assert any("no duplicate" in r.message.lower() for r in caplog.records)


# --- mutmut gap closures: #299 ---


def test_find_duplicate_continues_past_a_different_date_entry() -> None:
    # A `continue` on a date mismatch must keep scanning the rest of
    # `existing`, not stop there - the second entry, same day as the
    # candidate, is the one that should actually be flagged.
    existing = [
        _entry(1, "Glass Horizon", date(2024, 1, 1)),
        _entry(2, "Glass Horizon", date(2024, 3, 15)),
    ]

    match = find_duplicate("Glass Horizon", date(2024, 3, 15), existing)

    assert match is existing[1]


def test_find_duplicate_matches_at_the_exact_threshold_boundary_and_logs_exact_messages(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # threshold=100 with an identical title guarantees a token_sort_ratio
    # of exactly 100.0 (identical strings always score 100) - the one
    # boundary value that distinguishes `score >= threshold` from
    # `score > threshold` deterministically, without depending on
    # rapidfuzz's scoring of any non-identical pair.
    existing = [_entry(1, "Glass Horizon", date(2024, 3, 15))]

    with caplog.at_level(logging.DEBUG, logger="movie_planner.duplicates"):
        match = find_duplicate("Glass Horizon", date(2024, 3, 15), existing, threshold=100.0)

    assert match is existing[0]
    messages = [r.message for r in caplog.records]
    assert (
        "duplicate check: 'Glass Horizon' vs 'Glass Horizon' -> score=100.0 (threshold=100.0)"
    ) in messages
    assert "duplicate match: title score 100.0 >= 100.0" in messages


def test_overlap_match_logs_the_exact_message(caplog: pytest.LogCaptureFixture) -> None:
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(19, 0), end_time=time(21, 0))
    ]

    with caplog.at_level(logging.DEBUG, logger="movie_planner.duplicates"):
        match = find_duplicate(
            "Nightfall Junction",
            date(2024, 3, 15),
            existing,
            start_time=time(19, 30),
            end_time=time(21, 30),
        )

    assert match is existing[0]
    messages = [r.message for r in caplog.records]
    assert "duplicate match: overlapping screening time with 'Glass Horizon'" in messages


def test_no_duplicate_found_logs_the_exact_message(caplog: pytest.LogCaptureFixture) -> None:
    existing = [_entry(1, "Glass Horizon", date(2024, 3, 15))]

    with caplog.at_level(logging.DEBUG, logger="movie_planner.duplicates"):
        match = find_duplicate("Nightfall Junction", date(2024, 3, 15), existing)

    assert match is None
    messages = [r.message for r in caplog.records]
    assert "no duplicate found for 'Nightfall Junction' on 2024-03-15" in messages


def test_candidates_own_end_time_extends_the_overlap_window() -> None:
    # The candidate's end_time must be threaded all the way through to
    # the overlap check, not silently dropped in favor of treating it as
    # a bare point - a long candidate screening here only reaches into
    # the existing entry's buffered range because its own end_time
    # extends it there.
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(21, 45), end_time=time(23, 0))
    ]

    match = find_duplicate(
        "Nightfall Junction",
        date(2024, 3, 15),
        existing,
        start_time=time(19, 0),
        end_time=time(22, 0),
    )

    assert match is existing[0]


def test_existing_entrys_own_end_time_extends_the_overlap_window() -> None:
    # Mirror of the above: the existing entry's own end_time must matter,
    # not just the candidate's.
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(19, 0), end_time=time(22, 0))
    ]

    match = find_duplicate(
        "Nightfall Junction",
        date(2024, 3, 15),
        existing,
        start_time=time(21, 45),
        end_time=time(23, 0),
    )

    assert match is existing[0]


def test_times_touching_exactly_at_the_buffer_boundary_are_not_flagged() -> None:
    # Existing's buffered range ends at exactly 11:30 (11:00 + 30min).
    # A candidate whose own buffered range *starts* at exactly 11:30
    # (12:00 - 30min) touches but does not overlap - `<`, not `<=`.
    existing = [
        _entry(1, "Glass Horizon", date(2024, 3, 15), start_time=time(10, 0), end_time=time(11, 0))
    ]

    match = find_duplicate(
        "Nightfall Junction", date(2024, 3, 15), existing, start_time=time(12, 0)
    )

    assert match is None
