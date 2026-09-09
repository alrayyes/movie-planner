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
    _diff_entry,
    _venue_name_for_entry,
    detect_candidates,
    parse_event,
)
from movie_planner.calendar_sync import build_vevent
from movie_planner.store import Entry, Store

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


def test_parse_event_strips_location_suffix_with_street_address_and_postal_code() -> None:
    # issue #283 extended LOCATION to "name, street, postal city, country"
    # when both a street address and postal code are known - the plain
    # ", city, country" suffix above never matches that shape (the postal
    # code sits between the comma and the city), so this needs its own
    # strip, not just a fallback to the short one.
    ical = build_vevent(
        uid="uid-4b",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue="De Munt, Vijzelstraat 15, 1017 HD Amsterdam, Netherlands",
        extra_properties={
            "X-CITY": "Amsterdam",
            "X-COUNTRY": "Netherlands",
            "X-STREET-ADDRESS": "Vijzelstraat 15",
            "X-POSTAL-CODE": "1017 HD",
        },
    )

    parsed = parse_event(ical)

    assert parsed.venue_name == "De Munt"


def test_parse_event_falls_back_to_the_short_suffix_with_no_street_address() -> None:
    # X-STREET-ADDRESS/X-POSTAL-CODE absent (a venue with only city/
    # country known, issue #217) - still strips the plain ", city,
    # country" suffix, same as before #283 ever existed.
    ical = build_vevent(
        uid="uid-4c",
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


# --- _venue_name_for_entry: id lookup, not name/order coincidence ---


def test_venue_name_for_entry_looks_up_the_venue_matching_the_entrys_id(store: Store) -> None:
    # Two venues, alphabetically ordered "Some Other Venue" < "Tuschinski"
    # by store.list_venues()'s own ORDER BY name - entry.venue_id points
    # at the second one, so a query that matched on anything other than
    # an exact id (a flipped `==`, a dropped lookup entirely) would
    # either return the wrong venue's name or None, not "Tuschinski".
    store.add_venue("Some Other Venue")
    venue = store.add_venue("Tuschinski")
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune", date=date(2026, 1, 1), medium_id=medium.id, venue_id=venue.id
    )

    assert _venue_name_for_entry(store, entry) == "Tuschinski"


def test_venue_name_for_entry_none_when_entry_has_no_venue(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    assert _venue_name_for_entry(store, entry) is None


# --- _diff_entry: exact field-name label for every structured field ---


def test_diff_entry_reports_the_exact_field_name_for_every_structured_field() -> None:
    entry = Entry(
        id=1,
        title="Old Title",
        date=date(2026, 1, 1),
        medium_id=1,
        start_time=time(18, 0),
        end_time=time(20, 0),
        director="Old Director",
        actors="Old Actors",
        genre="Old Genre",
        release_year=2020,
        poster_url="https://old.example.com/poster.jpg",
    )
    parsed = ParsedEvent(
        uid="uid",
        title="New Title",
        date=date(2026, 1, 2),
        start_time=time(19, 0),
        end_time=time(21, 0),
        venue_name="New Venue",
        director="New Director",
        actors="New Actors",
        genre="New Genre",
        release_year=2021,
        poster_url="https://new.example.com/poster.jpg",
        row=None,
        seat=None,
    )

    diffs = _diff_entry(entry, parsed, "Old Venue")

    assert {d.field for d in diffs} == {
        "title",
        "date",
        "start_time",
        "end_time",
        "venue",
        "director",
        "actors",
        "genre",
        "release_year",
        "poster_url",
    }


# --- detect_candidates: the loop keeps going past a skipped/removed entry ---


def test_detect_candidates_continues_past_an_unsynced_entry_to_a_later_removed_one(
    store: Store,
) -> None:
    # An entry with no caldav_uid yet is skipped via `continue`, not
    # `break` - it must not stop the loop from reaching a later entry
    # that *is* synced and should surface as removed.
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Never Synced", date=date(2026, 1, 1), medium_id=medium.id)
    removed_entry = store.create_entry(title="Dune", date=date(2026, 1, 2), medium_id=medium.id)
    removed_entry = store.update_entry(removed_entry.id, caldav_uid="deleted-uid")

    candidates = detect_candidates(store, [])

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, RemovedCandidate)
    assert candidate.entry.id == removed_entry.id


def test_detect_candidates_continues_past_a_removed_entry_to_a_later_changed_one(
    store: Store,
) -> None:
    # Appending a RemovedCandidate is followed by `continue`, not `break`
    # - a later entry in the same pass must still get its own diff.
    medium = store.add_medium("cinema", is_physical_place=True)
    removed_entry = store.create_entry(
        title="Removed Movie", date=date(2026, 1, 1), medium_id=medium.id
    )
    removed_entry = store.update_entry(removed_entry.id, caldav_uid="removed-uid")
    changed_entry = store.create_entry(title="Dune", date=date(2026, 1, 2), medium_id=medium.id)
    changed_entry = store.update_entry(changed_entry.id, caldav_uid="changed-uid")
    ical = build_vevent(
        uid="changed-uid",
        title="Dune: Part Two",
        entry_date=date(2026, 1, 2),
        start_time=None,
        end_time=None,
        venue=None,
    )

    candidates = detect_candidates(store, [ical])

    assert len(candidates) == 2
    by_entry_id = {c.entry.id: c for c in candidates}  # type: ignore[union-attr]
    assert isinstance(by_entry_id[removed_entry.id], RemovedCandidate)
    assert isinstance(by_entry_id[changed_entry.id], ChangedCandidate)


def test_detect_candidates_no_diff_when_the_stored_venue_matches_the_calendar_venue(
    store: Store,
) -> None:
    # Exercises the real store lookup detect_candidates makes for each
    # entry's venue name (not a stubbed-out None, not the wrong store) -
    # a matched venue must not itself produce a spurious venue diff.
    venue = store.add_venue("Tuschinski")
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune", date=date(2026, 1, 1), medium_id=medium.id, venue_id=venue.id
    )
    entry = store.update_entry(entry.id, caldav_uid="uid-venue-match")
    ical = build_vevent(
        uid="uid-venue-match",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue="Tuschinski",
    )

    candidates = detect_candidates(store, [ical])

    assert candidates == []


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
