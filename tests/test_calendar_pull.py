from collections.abc import Iterator
from datetime import date, time
from pathlib import Path

import pytest

from movie_planner.calendar_pull import (
    ChangedCandidate,
    FieldDiff,
    NewCandidate,
    ParsedEvent,
    RemovedCandidate,
    detect_candidates,
    parse_event,
)
from movie_planner.calendar_sync import build_vevent
from movie_planner.store import Store

# --- 2.1: SUMMARY/DTSTART/DTEND round-trip, all three time shapes ---


def test_parse_event_date_only_all_day() -> None:
    ical = build_vevent(
        uid="uid-1",
        title="Dune",
        entry_date=date(2026, 3, 15),
        start_time=None,
        end_time=None,
        venue=None,
    )

    parsed = parse_event(ical)

    assert parsed.uid == "uid-1"
    assert parsed.title == "Dune"
    assert parsed.date == date(2026, 3, 15)
    assert parsed.start_time is None
    assert parsed.end_time is None


def test_parse_event_start_only_no_end() -> None:
    ical = build_vevent(
        uid="uid-2",
        title="Dune",
        entry_date=date(2026, 3, 15),
        start_time=time(19, 0),
        end_time=None,
        venue=None,
    )

    parsed = parse_event(ical)

    assert parsed.date == date(2026, 3, 15)
    assert parsed.start_time == time(19, 0)
    assert parsed.end_time is None


def test_parse_event_start_and_end() -> None:
    ical = build_vevent(
        uid="uid-3",
        title="Dune",
        entry_date=date(2026, 3, 15),
        start_time=time(19, 0),
        end_time=time(21, 30),
        venue=None,
    )

    parsed = parse_event(ical)

    assert parsed.start_time == time(19, 0)
    assert parsed.end_time == time(21, 30)


# --- 2.2: LOCATION -> venue name resolution ---


def test_parse_event_strips_location_suffix_matching_x_city_and_x_country() -> None:
    ical = build_vevent(
        uid="uid-4",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue="Tuschinski, Amsterdam, Netherlands",
        extra_properties={"X-CITY": "Amsterdam", "X-COUNTRY": "Netherlands"},
    )

    parsed = parse_event(ical)

    assert parsed.venue_name == "Tuschinski"


def test_parse_event_uses_location_verbatim_when_it_does_not_match_x_city_country() -> None:
    ical = build_vevent(
        uid="uid-5",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue="Some Living Room",
        extra_properties={"X-CITY": "Amsterdam", "X-COUNTRY": "Netherlands"},
    )

    parsed = parse_event(ical)

    assert parsed.venue_name == "Some Living Room"


def test_parse_event_uses_location_verbatim_when_no_x_city_or_x_country() -> None:
    ical = build_vevent(
        uid="uid-6",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue="Grand Vista Cinema, Springfield, USA",
    )

    parsed = parse_event(ical)

    assert parsed.venue_name == "Grand Vista Cinema, Springfield, USA"


def test_parse_event_venue_name_none_when_no_location() -> None:
    ical = build_vevent(
        uid="uid-7",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    parsed = parse_event(ical)

    assert parsed.venue_name is None


def test_parse_event_resolves_a_known_alias_to_its_canonical_venue() -> None:
    # "Pathé Tuschinski" is a known alias of the canonical "Tuschinski" -
    # design.md's alias-resolution requirement, exercised here without
    # any X-CITY/X-COUNTRY suffix-stripping in play.
    ical = build_vevent(
        uid="uid-8",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue="Pathé Tuschinski",
    )

    parsed = parse_event(ical)

    assert parsed.venue_name == "Tuschinski"


# --- 2.3: X-* properties read directly, present-or-None ---


def test_parse_event_reads_structured_x_properties() -> None:
    ical = build_vevent(
        uid="uid-9",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
        extra_properties={
            "X-DIRECTOR": "Denis Villeneuve",
            "X-ACTORS": "Timothée Chalamet, Zendaya",
            "X-GENRE": "Action, Adventure, Drama",
            "X-YEAR": "2021",
            "X-POSTER-URL": "https://example.com/poster.jpg",
            "X-ROW": "5",
            "X-SEAT": "17",
        },
    )

    parsed = parse_event(ical)

    assert parsed.director == "Denis Villeneuve"
    assert parsed.actors == "Timothée Chalamet, Zendaya"
    assert parsed.genre == "Action, Adventure, Drama"
    assert parsed.release_year == 2021
    assert parsed.poster_url == "https://example.com/poster.jpg"
    assert parsed.row == "5"
    assert parsed.seat == "17"


def test_parse_event_missing_x_properties_map_to_none_not_an_error() -> None:
    ical = build_vevent(
        uid="uid-10",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    parsed = parse_event(ical)

    assert parsed.director is None
    assert parsed.actors is None
    assert parsed.genre is None
    assert parsed.release_year is None
    assert parsed.poster_url is None
    assert parsed.row is None
    assert parsed.seat is None


# --- 2.4: DESCRIPTION is never parsed for any structured field ---


def test_parse_event_never_reads_description() -> None:
    ical = build_vevent(
        uid="uid-11",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
        description="IMDb: 8.5/10\nRotten Tomatoes: 91%\nNotes: watched with friends",
    )

    parsed = parse_event(ical)

    # ParsedEvent has no field at all for ratings/notes/Letterboxd/chain -
    # this asserts the dataclass shape itself carries none of them.
    assert not hasattr(parsed, "imdb_rating")
    assert not hasattr(parsed, "notes")
    assert not hasattr(parsed, "letterboxd_url")
    assert not hasattr(parsed, "chain")


# --- 3.1: new-entry detection ---


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "movies.db")
    yield s
    s.close()


def test_detect_candidates_new_entry_for_an_unmatched_calendar_event(store: Store) -> None:
    ical = build_vevent(
        uid="web-uid-1",
        title="Arrival",
        entry_date=date(2026, 2, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    candidates = detect_candidates(store, [ical])

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, NewCandidate)
    assert candidate.parsed.uid == "web-uid-1"
    assert candidate.parsed.title == "Arrival"


def test_detect_candidates_no_candidate_when_uid_already_matches_an_entry(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, caldav_uid="matched-uid")
    ical = build_vevent(
        uid="matched-uid",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    candidates = detect_candidates(store, [ical])

    assert candidates == []


# --- 3.2: changed-entry detection ---


def test_detect_candidates_changed_entry_when_a_structured_field_differs(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, caldav_uid="uid-changed")
    ical = build_vevent(
        uid="uid-changed",
        title="Dune: Part Two",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    candidates = detect_candidates(store, [ical])

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, ChangedCandidate)
    assert candidate.entry.id == entry.id
    assert FieldDiff(field="title", stored="Dune", calendar="Dune: Part Two") in candidate.diffs


def test_detect_candidates_description_only_difference_is_not_a_candidate(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, caldav_uid="uid-desc-only", imdb_rating="8.0/10")
    # DESCRIPTION on the calendar event carries a rating the store
    # doesn't have recorded the same way - every structured field still
    # matches, so this must not surface as a candidate at all.
    ical = build_vevent(
        uid="uid-desc-only",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
        description="IMDb: 9.9/10 (a totally different rating)",
    )

    candidates = detect_candidates(store, [ical])

    assert candidates == []


# --- 3.3: removed-entry detection ---


def test_detect_candidates_removed_when_entrys_uid_matches_no_event(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, caldav_uid="deleted-uid")

    candidates = detect_candidates(store, [])

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, RemovedCandidate)
    assert candidate.entry.id == entry.id


def test_detect_candidates_never_synced_entry_is_not_a_removed_candidate(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    candidates = detect_candidates(store, [])

    assert candidates == []


# --- 3.4: missing X-* property phrased as "unknown", not a confirmed deletion ---


def test_detect_candidates_missing_x_property_diff_is_stored_value_to_none(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, caldav_uid="uid-row-seat", row="5", seat="17")
    # The event has no X-ROW/X-SEAT at all - could be a real removal, or
    # movie-planner-web#294's allow-list bug dropping it as a side
    # effect of an unrelated edit. Detection itself doesn't decide which;
    # it's the same diff shape either way (design.md).
    ical = build_vevent(
        uid="uid-row-seat",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    candidates = detect_candidates(store, [ical])

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, ChangedCandidate)
    assert FieldDiff(field="row", stored="5", calendar=None) in candidate.diffs
    assert FieldDiff(field="seat", stored="17", calendar=None) in candidate.diffs


def test_parsed_event_is_a_frozen_dataclass() -> None:
    # Cheap sanity check that the type used throughout this module can't
    # be mutated after construction, matching every other dataclass in
    # this codebase.
    parsed = ParsedEvent(
        uid="u",
        title="t",
        date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue_name=None,
        director=None,
        actors=None,
        genre=None,
        release_year=None,
        poster_url=None,
        row=None,
        seat=None,
    )
    with pytest.raises(AttributeError):
        parsed.title = "changed"  # type: ignore[misc]
