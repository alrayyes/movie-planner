import logging
import uuid
from collections.abc import Iterator
from datetime import date, datetime, time
from pathlib import Path

import icalendar
import pytest
from fakes import FakeCalendar, FakeEvent

from movie_planner.calendar_sync import (
    CalendarClient,
    CalendarSync,
    CalendarSyncError,
    build_description,
    build_vevent,
)
from movie_planner.store import Entry, Store
from movie_planner.user_agent import USER_AGENT_HEADER

# --- build_vevent: task 4.2, the three time-completeness mapping rules ---


def _parse(ical_text: str) -> icalendar.Event:
    cal = icalendar.Calendar.from_ical(ical_text)
    (event,) = [c for c in cal.subcomponents if c.name == "VEVENT"]
    assert isinstance(event, icalendar.Event)
    return event


def _dt(event: icalendar.Event, name: str) -> date | datetime:
    # event[name] is typed as icalendar's big property-value union - only
    # the DATE/DATE-TIME wrapper actually has .dt, which is what
    # build_vevent always sets dtstart/dtend to.
    value = event[name]
    assert isinstance(value, icalendar.vDDDTypes)
    assert isinstance(value.dt, date)
    return value.dt


def test_build_vevent_date_only_is_all_day() -> None:
    ical_text = build_vevent(
        uid="uid-1",
        title="Paper Constellations",
        entry_date=date(2024, 1, 20),
        start_time=None,
        end_time=None,
        venue=None,
    )

    event = _parse(ical_text)
    assert _dt(event, "dtstart") == date(2024, 1, 20)
    assert "dtend" not in event


def test_build_vevent_start_only_has_no_dtend() -> None:
    ical_text = build_vevent(
        uid="uid-2",
        title="Solstice Run",
        entry_date=date(2024, 6, 2),
        start_time=time(16, 10),
        end_time=None,
        venue="Riverside Multiplex",
    )

    event = _parse(ical_text)
    assert _dt(event, "dtstart") == datetime(2024, 6, 2, 16, 10)
    assert "dtend" not in event
    assert str(event["location"]) == "Riverside Multiplex"


def test_build_vevent_full_range_has_dtstart_and_dtend() -> None:
    ical_text = build_vevent(
        uid="uid-3",
        title="The Clockmaker's Daughter",
        entry_date=date(2024, 3, 15),
        start_time=time(14, 0),
        end_time=time(16, 32),
        venue="Grand Vista Cinema",
    )

    event = _parse(ical_text)
    assert _dt(event, "dtstart") == datetime(2024, 3, 15, 14, 0)
    assert _dt(event, "dtend") == datetime(2024, 3, 15, 16, 32)


def test_build_vevent_uid_and_title_carried_through() -> None:
    ical_text = build_vevent(
        uid="unique-id",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    event = _parse(ical_text)
    assert str(event["uid"]) == "unique-id"
    assert str(event["summary"]) == "Dune"


def test_build_vevent_sets_the_correct_prodid_and_version() -> None:
    # icalendar's Component is a caseless dict - the *property names* here
    # ("prodid", "version") are re-serialized uppercase regardless of the
    # case passed to add(), so only the literal *values* are worth pinning
    # down; a case-only mutation of the name can never be observed.
    ical_text = build_vevent(
        uid="uid-prodid",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    assert "PRODID:-//movie-planner//EN" in ical_text
    assert "VERSION:2.0" in ical_text


def test_build_vevent_with_description() -> None:
    ical_text = build_vevent(
        uid="uid-4",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
        description="IMDb: 8.5/10",
    )

    event = _parse(ical_text)
    assert str(event["description"]) == "IMDb: 8.5/10"


def test_build_vevent_with_no_description_omits_the_field() -> None:
    ical_text = build_vevent(
        uid="uid-5",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    event = _parse(ical_text)
    assert "description" not in event


def test_build_vevent_with_extra_properties() -> None:
    ical_text = build_vevent(
        uid="uid-6",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
        extra_properties={"X-DIRECTOR": "Denis Villeneuve", "X-YEAR": "2021"},
    )

    event = _parse(ical_text)
    assert str(event["X-DIRECTOR"]) == "Denis Villeneuve"
    assert str(event["X-YEAR"]) == "2021"


def test_build_vevent_with_no_extra_properties_adds_none() -> None:
    ical_text = build_vevent(
        uid="uid-7",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    event = _parse(ical_text)
    assert "X-DIRECTOR" not in event


# --- GEO: issue #170 ---


def test_build_vevent_with_geo_adds_the_property() -> None:
    ical_text = build_vevent(
        uid="uid-8",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue="Tuschinski, Amsterdam, Netherlands",
        geo=(52.3667, 4.8945),
    )

    event = _parse(ical_text)
    geo = event["geo"]
    assert isinstance(geo, icalendar.vGeo)
    assert (round(geo.latitude, 4), round(geo.longitude, 4)) == (52.3667, 4.8945)


def test_build_vevent_with_no_geo_omits_the_field() -> None:
    ical_text = build_vevent(
        uid="uid-9",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    event = _parse(ical_text)
    assert "geo" not in event


# --- build_description: task 2.1 ---


def _entry(**overrides: object) -> Entry:
    defaults: dict[str, object] = {
        "id": 1,
        "title": "Dune",
        "date": date(2026, 1, 1),
        "medium_id": 1,
    }
    defaults.update(overrides)
    return Entry(**defaults)  # type: ignore[arg-type]


def test_build_description_includes_all_present_fields() -> None:
    entry = _entry(
        imdb_rating="8.5/10",
        rotten_tomatoes_rating="91%",
        metacritic_rating="80",
        released="22 Oct 2021",
        plot="Paul Atreides unites with the Fremen.",
        awards="Won 6 Oscars.",
        letterboxd_url="https://letterboxd.com/film/dune-2021/",
        letterboxd_rating="4.5",
    )

    description = build_description(entry, screening_details="Original Version")

    assert description is not None
    assert "IMDb: 8.5/10" in description
    assert "Rotten Tomatoes: 91%" in description
    assert "Metacritic: 80" in description
    assert "Released: 22 Oct 2021" in description
    assert "Plot: Paul Atreides unites with the Fremen." in description
    assert "Awards: Won 6 Oscars." in description
    assert "https://letterboxd.com/film/dune-2021/" in description
    assert "4.5" in description
    assert "Original Version" in description


def test_build_description_omits_released_plot_and_awards_when_absent() -> None:
    entry = _entry(imdb_rating="8.5/10")

    description = build_description(entry)

    assert description is not None
    assert "Released" not in description
    assert "Plot" not in description
    assert "Awards" not in description


def test_build_description_with_nothing_present_is_none() -> None:
    entry = _entry()

    assert build_description(entry) is None


def test_build_description_includes_notes() -> None:
    entry = _entry(notes="Enjoyed the soundtrack")

    description = build_description(entry)

    assert description == "Notes: Enjoyed the soundtrack"


def test_build_description_includes_chain() -> None:
    entry = _entry()

    description = build_description(entry, chain="Pathé")

    assert description == "Chain: Pathé"


def test_build_description_with_only_some_fields() -> None:
    entry = _entry(imdb_rating="8.5/10")

    description = build_description(entry)

    assert description == "IMDb: 8.5/10"


def test_build_description_includes_the_imdb_link_alongside_the_rating() -> None:
    entry = _entry(imdb_rating="8.5/10", imdb_url="https://www.imdb.com/title/tt1160419/")

    description = build_description(entry)

    assert description == "IMDb: 8.5/10 (https://www.imdb.com/title/tt1160419/)"


def test_build_description_includes_the_imdb_link_with_no_rating() -> None:
    entry = _entry(imdb_url="https://www.imdb.com/title/tt1160419/")

    description = build_description(entry)

    assert description == "IMDb: https://www.imdb.com/title/tt1160419/"


def test_build_description_letterboxd_link_with_no_rating_has_no_suffix() -> None:
    entry = _entry(letterboxd_url="https://letterboxd.com/film/dune-2021/")

    description = build_description(entry)

    assert description == "Letterboxd: https://letterboxd.com/film/dune-2021/"


def test_build_description_joins_multiple_lines_with_a_single_newline() -> None:
    entry = _entry(imdb_rating="8.5/10", rotten_tomatoes_rating="91%")

    description = build_description(entry)

    assert description == "IMDb: 8.5/10\nRotten Tomatoes: 91%"


# --- CalendarClient: task 4.1, wrapping a caldav.Calendar-like object ---


def test_calendar_client_connect_wires_up_the_dav_client(monkeypatch: pytest.MonkeyPatch) -> None:
    init_calls: dict[str, object] = {}
    calendar_urls: list[str] = []

    class FakeDAVClient:
        def __init__(self, url: str, username: str, password: str, headers: dict[str, str]) -> None:
            init_calls["url"] = url
            init_calls["username"] = username
            init_calls["password"] = password
            init_calls["headers"] = headers

        def calendar(self, url: str) -> FakeCalendar:
            calendar_urls.append(url)
            return FakeCalendar()

    monkeypatch.setattr("movie_planner.calendar_sync.DAVClient", FakeDAVClient)

    client = CalendarClient.connect(
        url="https://baikal.example.com/calendars/movies/",
        username="moviewatcher",
        password="secret",
    )

    assert isinstance(client, CalendarClient)
    assert init_calls["username"] == "moviewatcher"
    assert init_calls["password"] == "secret"
    assert init_calls["headers"] == USER_AGENT_HEADER
    assert calendar_urls == ["https://baikal.example.com/calendars/movies/"]


def test_calendar_client_check_connection_succeeds() -> None:
    client = CalendarClient(FakeCalendar())
    client.check_connection()  # does not raise


def test_calendar_client_check_connection_propagates_failure() -> None:
    client = CalendarClient(FakeCalendar(fail_next=True))
    with pytest.raises(ConnectionError):
        client.check_connection()


def test_calendar_client_list_events_returns_raw_ical_text_per_event() -> None:
    calendar = FakeCalendar()
    client = CalendarClient(calendar)
    ical_a = build_vevent(
        uid="uid-a",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    ical_b = build_vevent(
        uid="uid-b",
        title="Arrival",
        entry_date=date(2026, 1, 2),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.add_event(ical_a)
    calendar.add_event(ical_b)

    events = client.list_events()

    assert sorted(events) == sorted([ical_a, ical_b])


def test_calendar_client_list_events_empty_calendar() -> None:
    client = CalendarClient(FakeCalendar())

    assert client.list_events() == []


def test_calendar_client_list_events_propagates_failure() -> None:
    client = CalendarClient(FakeCalendar(fail_next=True))
    with pytest.raises(ConnectionError):
        client.list_events()


def test_calendar_client_check_connection_does_not_use_list_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check_connection just calls events() for connectivity - it doesn't
    route through list_events (task 1.2).
    """
    client = CalendarClient(FakeCalendar())

    def fail(self: CalendarClient) -> list[str]:
        raise AssertionError("check_connection should not call list_events")

    monkeypatch.setattr(CalendarClient, "list_events", fail)

    client.check_connection()  # does not raise


def test_calendar_client_create_event() -> None:
    calendar = FakeCalendar()
    client = CalendarClient(calendar)
    ical_text = build_vevent(
        uid="uid-1",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )

    client.create_event(ical_text)

    assert "uid-1" in calendar.events_by_uid


def test_calendar_client_update_event() -> None:
    calendar = FakeCalendar()
    client = CalendarClient(calendar)
    ical_text = build_vevent(
        uid="uid-1",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    client.create_event(ical_text)
    updated_ical = build_vevent(
        uid="uid-1",
        title="Dune Part Two",
        entry_date=date(2026, 1, 2),
        start_time=None,
        end_time=None,
        venue=None,
    )

    client.update_event("uid-1", updated_ical)

    assert calendar.events_by_uid["uid-1"].data == updated_ical


def test_calendar_client_delete_event() -> None:
    calendar = FakeCalendar()
    client = CalendarClient(calendar)
    ical_text = build_vevent(
        uid="uid-1",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    client.create_event(ical_text)

    client.delete_event("uid-1")

    assert calendar.events_by_uid["uid-1"].deleted is True


# --- CalendarSync: tasks 4.3, 4.4, 4.5 ---


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "movies.db")
    yield s
    s.close()


def test_push_new_stores_the_returned_uid_on_the_entry(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    sync = CalendarSync(store, CalendarClient(FakeCalendar()))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    assert store.get_entry(entry.id).caldav_uid == synced.caldav_uid


def test_push_new_generates_a_uuid7(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    sync = CalendarSync(store, CalendarClient(FakeCalendar()))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    assert uuid.UUID(synced.caldav_uid).version == 7


def test_push_new_maps_the_entrys_start_and_end_time_onto_the_event(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune",
        date=date(2026, 1, 1),
        medium_id=medium.id,
        start_time=time(19, 30),
        end_time=time(21, 45),
    )
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    event = _parse(calendar.events_by_uid[synced.caldav_uid].data)
    assert _dt(event, "dtstart") == datetime(2026, 1, 1, 19, 30)
    assert _dt(event, "dtend") == datetime(2026, 1, 1, 21, 45)


# --- crash safety: issue #246 ---


def test_push_new_records_the_uid_locally_before_creating_the_event(store: Store) -> None:
    # The core of the fix: an interruption between the CalDAV create and
    # the local save can no longer produce a "caldav_uid is still None
    # but a real event already exists" state, because the local write
    # now happens first - by the time create_event runs, the store
    # already agrees on the UID that's about to be created.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    seen_uid_at_create_time: list[str | None] = []
    original_add_event = calendar.add_event

    def spying_add_event(ical: str) -> FakeEvent:
        seen_uid_at_create_time.append(store.get_entry(entry.id).caldav_uid)
        return original_add_event(ical)

    calendar.add_event = spying_add_event  # type: ignore[method-assign]
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert seen_uid_at_create_time == [synced.caldav_uid]


def test_push_new_interrupted_before_the_event_landed_self_heals_without_duplicating(
    store: Store,
) -> None:
    # Simulates a crash between the local write and the CalDAV create
    # actually reaching the server - the entry claims a UID that
    # doesn't exist on the calendar yet. The next push for this entry
    # (any push_update, e.g. from `sync refresh`) must recover through
    # the same NotFoundError path #166 already added, not fail forever
    # and not create a second event alongside a first one that was
    # never actually made.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    interrupted = store.update_entry(entry.id, caldav_uid="never-actually-created")
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    sync.push_update(interrupted, venue=None)  # does not raise

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    assert refreshed.caldav_uid != "never-actually-created"
    assert list(calendar.events_by_uid) == [refreshed.caldav_uid]


def test_push_new_interrupted_after_the_event_landed_does_not_duplicate(store: Store) -> None:
    # The other half of the same crash window: the CalDAV create
    # actually succeeded server-side before the interruption, so a
    # real event already exists under the UID the store also already
    # recorded (since that write happens first). The next push for
    # this entry must find and use that existing event, not create a
    # second one under a fresh UID.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    # Simulates the crash landing after create_event succeeded but
    # before the caller got to do anything else with the result -
    # both the store and the calendar already agree on this UID.
    ical_text = build_vevent(
        uid="already-created",
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.add_event(ical=ical_text)
    interrupted = store.update_entry(entry.id, caldav_uid="already-created")

    sync.push_update(interrupted, venue=None)  # finds and updates the existing event

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid == "already-created"
    assert list(calendar.events_by_uid) == ["already-created"]


def test_push_new_on_a_create_failure_leaves_the_uid_recorded_rather_than_rolling_back(
    store: Store,
) -> None:
    # A caught create_event failure can't be reliably told apart from
    # "the server actually created it and the failure happened on the
    # way back" (a dropped connection reading the response, say) - so
    # rolling the local UID back to None here would reopen exactly the
    # bug this issue is about for that case. Leaving it recorded is
    # safe either way: the next push for this entry self-heals through
    # the same NotFoundError path, whether or not the event actually
    # exists yet.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar(fail_next=True)
    sync = CalendarSync(store, CalendarClient(calendar))

    with pytest.raises(
        CalendarSyncError, match=f"could not sync '{entry.title}' to the calendar: "
    ):
        sync.push_new(entry, venue=None)

    failed = store.get_entry(entry.id)
    assert failed.caldav_uid is not None
    calendar.fail_next = False

    sync.push_update(failed, venue=None)  # self-heals, does not raise

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    assert list(calendar.events_by_uid) == [refreshed.caldav_uid]


def test_push_new_includes_ratings_in_the_description(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, imdb_rating="8.5/10")
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    assert "IMDb: 8.5/10" in calendar.events_by_uid[synced.caldav_uid].data


def test_push_new_includes_poster_url_as_an_x_property(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(
        entry.id, poster_url="https://m.media-amazon.com/images/dune-poster.jpg"
    )
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-POSTER-URL:https://m.media-amazon.com/images/dune-poster.jpg" in ical_text


def test_push_new_includes_director_actors_genre_and_year_as_x_properties(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(
        entry.id,
        director="Denis Villeneuve",
        actors="Timothée Chalamet, Rebecca Ferguson, Zendaya",
        genre="Action, Adventure, Drama",
        release_year=2021,
    )
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-DIRECTOR:Denis Villeneuve" in ical_text
    assert "X-ACTORS:Timothée Chalamet, Rebecca Ferguson, Zendaya" in ical_text
    assert "X-GENRE:Action, Adventure, Drama" in ical_text
    assert "X-YEAR:2021" in ical_text


def test_push_new_includes_the_rest_of_omdbs_fields_as_x_properties(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(
        entry.id,
        rated="PG-13",
        runtime="155 min",
        language="English, Mandarin",
        country="United States, Canada",
        # Not stored on this entry, so X-CITY/X-COUNTRY (issue #217,
        # venue-derived) are unaffected below, confirming the two
        # never collide despite the movie's own "country" field.
        metascore="74",
        imdb_votes="757,451",
        dvd="22 Nov 2021",
        box_office="$108,327,830",
        production="Legendary Pictures",
        website="https://www.dunemovie.com",
    )
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-RATED:PG-13" in ical_text
    assert "X-RUNTIME:155 min" in ical_text
    assert "X-MOVIE-LANGUAGE:English, Mandarin" in ical_text
    assert "X-MOVIE-COUNTRY:United States, Canada" in ical_text
    # Not the venue's X-CITY/X-COUNTRY (issue #217) - genuinely
    # different data, so it needs its own, differently-named property.
    assert "X-COUNTRY:" not in ical_text
    assert "X-METASCORE:74" in ical_text
    assert "X-IMDB-VOTES:757,451" in ical_text
    assert "X-DVD:22 Nov 2021" in ical_text
    assert "X-BOX-OFFICE:$108,327,830" in ical_text
    assert "X-PRODUCTION:Legendary Pictures" in ical_text
    assert "X-WEBSITE:https://www.dunemovie.com" in ical_text


def test_push_new_omits_the_rest_of_omdbs_fields_when_entry_has_none(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    for prop in (
        "X-RATED",
        "X-RUNTIME",
        "X-MOVIE-LANGUAGE",
        "X-MOVIE-COUNTRY",
        "X-METASCORE",
        "X-IMDB-VOTES",
        "X-DVD",
        "X-BOX-OFFICE",
        "X-PRODUCTION",
        "X-WEBSITE",
    ):
        assert prop not in ical_text


def test_push_new_includes_x_trailer_url_when_entry_has_one(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, trailer_url="https://www.youtube.com/watch?v=8g18jFHCLXk")
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-TRAILER-URL:https://www.youtube.com/watch?v=8g18jFHCLXk" in ical_text


def test_push_new_omits_x_trailer_url_when_entry_has_none(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-TRAILER-URL" not in ical_text


# --- X-COLLECTION/X-CERTIFICATION/X-KEYWORDS/X-BUDGET/X-POPULARITY: issue #311 ---


def test_push_new_includes_tmdbs_own_fields_as_x_properties(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(
        entry.id,
        collection="Dune Collection",
        certification="PG-13",
        keywords="desert, prophecy, sandworm",
        budget=165_000_000,
        popularity=245.318,
    )
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-COLLECTION:Dune Collection" in ical_text
    assert "X-CERTIFICATION:PG-13" in ical_text
    assert "X-KEYWORDS:desert, prophecy, sandworm" in ical_text
    assert "X-BUDGET:165000000" in ical_text
    assert "X-POPULARITY:245.318" in ical_text


def test_push_new_omits_tmdbs_own_fields_when_entry_has_none(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    for prop in ("X-COLLECTION", "X-CERTIFICATION", "X-KEYWORDS", "X-BUDGET", "X-POPULARITY"):
        assert prop not in ical_text


def test_push_new_includes_a_genuine_zero_popularity(store: Store) -> None:
    # Unlike a missing/None popularity (omitted, above), a real 0.0 is
    # meaningful TMDb data - it must still show up as X-POPULARITY:0.0,
    # not be filtered out the way an empty/falsy value normally would be.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, popularity=0.0)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-POPULARITY:0.0" in ical_text


# --- X-IMPORTER/X-IMPORTER-VERSION: issue #257 ---


def test_push_new_includes_importer_and_version_when_given(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None, importer="log")

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-IMPORTER:log" in ical_text
    assert "X-IMPORTER-VERSION:" in ical_text


def test_push_new_omits_importer_properties_when_not_given(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-IMPORTER" not in ical_text


def test_push_update_includes_importer_when_given(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_update(entry, venue=None, importer="update")

    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "X-IMPORTER:update" in ical_text


def test_push_new_logs_the_full_ical_payload_at_debug_level(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    with caplog.at_level(logging.DEBUG, logger="movie_planner.calendar_sync"):
        synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    # An exact match on the whole message, not just a substring check - the
    # pushed ical_text itself always contains the entry's uid (in its own
    # UID: line), so a substring check on caldav_uid alone can't tell a
    # correctly-logged uid apart from one silently dropped from the
    # "uid=%s" slot of the log line itself.
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    records = [r for r in caplog.records if r.name == "movie_planner.calendar_sync"]
    assert records[-1].message == f"Calendar push (create, uid={synced.caldav_uid}):\n{ical_text}"


def test_push_update_logs_the_full_ical_payload_at_debug_level(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    with caplog.at_level(logging.DEBUG, logger="movie_planner.calendar_sync"):
        sync.push_update(entry, venue=None)

    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    records = [r for r in caplog.records if r.name == "movie_planner.calendar_sync"]
    assert records[-1].message == f"Calendar push (update, uid={entry.caldav_uid}):\n{ical_text}"


def test_push_new_omits_director_actors_genre_and_year_when_entry_has_none(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-DIRECTOR" not in ical_text
    assert "X-ACTORS" not in ical_text
    assert "X-GENRE" not in ical_text
    assert "X-YEAR" not in ical_text


def test_push_update_refreshes_director_actors_genre_and_year(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    entry = store.update_entry(entry.id, director="Denis Villeneuve", release_year=2021)

    sync.push_update(entry, venue=None)

    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "X-DIRECTOR:Denis Villeneuve" in ical_text
    assert "X-YEAR:2021" in ical_text


def test_push_new_includes_city_and_country_as_x_properties(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue="Pathé De Munt", city="Amsterdam", country="Netherlands")

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-CITY:Amsterdam" in ical_text
    assert "X-COUNTRY:Netherlands" in ical_text


def test_push_new_includes_street_address_and_postal_code_as_x_properties(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(
        entry,
        venue="Pathé De Munt",
        street_address="Vijzelstraat 15",
        postal_code="1017 HD",
    )

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-STREET-ADDRESS:Vijzelstraat 15" in ical_text
    assert "X-POSTAL-CODE:1017 HD" in ical_text


def test_push_new_omits_street_address_when_entry_has_none(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-STREET-ADDRESS" not in ical_text
    assert "X-POSTAL-CODE" not in ical_text


def test_push_new_sets_street_address_and_postal_code_independently(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None, street_address="Vijzelstraat 15")

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-STREET-ADDRESS:Vijzelstraat 15" in ical_text
    assert "X-POSTAL-CODE" not in ical_text


def test_push_new_includes_row_and_seat_as_x_properties(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune", date=date(2026, 1, 1), medium_id=medium.id, row="5", seat="17"
    )
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-ROW:5" in ical_text
    assert "X-SEAT:17" in ical_text


def test_push_new_omits_row_and_seat_when_entry_has_none(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-ROW" not in ical_text
    assert "X-SEAT" not in ical_text


def test_push_update_refreshes_row_and_seat(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    entry = store.update_entry(entry.id, row="5", seat="17")

    sync.push_update(entry, venue=None)

    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "X-ROW:5" in ical_text
    assert "X-SEAT:17" in ical_text


def test_push_new_omits_city_and_country_for_an_unrecognized_venue(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue="Grand Vista Cinema")

    assert synced.caldav_uid is not None
    ical_text = calendar.events_by_uid[synced.caldav_uid].data
    assert "X-CITY" not in ical_text
    assert "X-COUNTRY" not in ical_text


def test_push_update_refreshes_city_and_country(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_update(entry, venue="Pathé De Munt", city="Amsterdam", country="Netherlands")

    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "LOCATION:Pathé De Munt" in ical_text
    assert "X-CITY:Amsterdam" in ical_text
    assert "X-COUNTRY:Netherlands" in ical_text


def test_push_update_keeps_the_events_own_uid(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_update(entry, venue=None)

    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert f"UID:{entry.caldav_uid}" in ical_text


def test_push_update_maps_the_entrys_start_and_end_time_onto_the_event(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    entry = store.update_entry(entry.id, start_time=time(19, 30), end_time=time(21, 45))

    sync.push_update(entry, venue=None)

    assert entry.caldav_uid is not None
    event = _parse(calendar.events_by_uid[entry.caldav_uid].data)
    assert _dt(event, "dtstart") == datetime(2026, 1, 1, 19, 30)
    assert _dt(event, "dtend") == datetime(2026, 1, 1, 21, 45)


def test_push_update_refreshes_geo(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_update(entry, venue=None, geo=(52.3667, 4.8945))

    assert entry.caldav_uid is not None
    event = _parse(calendar.events_by_uid[entry.caldav_uid].data)
    geo = event["geo"]
    assert isinstance(geo, icalendar.vGeo)
    assert (round(geo.latitude, 4), round(geo.longitude, 4)) == (52.3667, 4.8945)


def test_push_update_refreshes_chain_in_the_description(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_update(entry, venue="Tuschinski, Amsterdam, Netherlands", chain="Pathé")

    assert entry.caldav_uid is not None
    assert "Chain: Pathé" in calendar.events_by_uid[entry.caldav_uid].data


def test_push_update_refreshes_screening_details_in_the_description(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_update(entry, venue=None, screening_details="Auditorium 1 DOLBY - Row 5 Seat 17")

    assert entry.caldav_uid is not None
    assert "Auditorium 1 DOLBY - Row 5 Seat 17" in calendar.events_by_uid[entry.caldav_uid].data


def test_push_update_refreshes_street_address_and_postal_code(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_update(entry, venue=None, street_address="Vijzelstraat 15", postal_code="1017 HD")

    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "X-STREET-ADDRESS:Vijzelstraat 15" in ical_text
    assert "X-POSTAL-CODE:1017 HD" in ical_text


def test_push_new_omits_poster_url_property_when_entry_has_none(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    assert "X-POSTER-URL" not in calendar.events_by_uid[synced.caldav_uid].data


def test_push_new_includes_chain_in_the_description(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(entry, venue="Tuschinski, Amsterdam, Netherlands", chain="Pathé")

    assert synced.caldav_uid is not None
    assert "Chain: Pathé" in calendar.events_by_uid[synced.caldav_uid].data
    assert (
        "Tuschinski\\, Amsterdam\\, Netherlands" in calendar.events_by_uid[synced.caldav_uid].data
    )


def test_push_new_includes_screening_details_in_the_description(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="The Dog Stars", date=date(2026, 8, 29), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))

    synced = sync.push_new(
        entry, venue=None, screening_details="Auditorium 1 DOLBY - Row 5 Seat 17"
    )

    assert synced.caldav_uid is not None
    assert "Auditorium 1 DOLBY - Row 5 Seat 17" in calendar.events_by_uid[synced.caldav_uid].data


def test_push_update_refreshes_the_description(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    entry = store.update_entry(entry.id, imdb_rating="8.5/10")

    sync.push_update(entry, venue=None)

    assert entry.caldav_uid is not None
    assert "IMDb: 8.5/10" in calendar.events_by_uid[entry.caldav_uid].data


def test_push_update_changes_the_linked_event(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    entry = store.update_entry(entry.id, title="Dune Part Two")

    sync.push_update(entry, venue=None)

    assert entry.caldav_uid is not None
    assert "Dune Part Two" in calendar.events_by_uid[entry.caldav_uid].data


def test_push_delete_removes_the_linked_event(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_delete(entry)

    assert entry.caldav_uid is not None
    assert calendar.events_by_uid[entry.caldav_uid].deleted is True


def test_push_delete_on_never_synced_entry_is_a_no_op(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    sync = CalendarSync(store, CalendarClient(FakeCalendar()))

    sync.push_delete(entry)  # does not raise


def test_push_update_on_never_synced_entry_raises(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    sync = CalendarSync(store, CalendarClient(FakeCalendar()))

    with pytest.raises(CalendarSyncError, match="never been synced"):
        sync.push_update(entry, venue=None)


def test_push_update_recreates_the_event_when_the_caldav_uid_is_stale(store: Store) -> None:
    # movie-planner#166: an external wipe/rebuild of the calendar leaves
    # every entry's caldav_uid pointing at an event that no longer
    # exists - push_update should recover by treating the entry as
    # never synced, not fail forever.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    stale_uid = entry.caldav_uid
    assert stale_uid is not None
    del calendar.events_by_uid[stale_uid]  # simulates an external wipe

    sync.push_update(entry, venue=None)  # does not raise

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    assert refreshed.caldav_uid != stale_uid
    assert refreshed.caldav_uid in calendar.events_by_uid


def test_push_update_stale_uid_recovery_keeps_city_and_country(store: Store) -> None:
    # movie-planner#262: the NotFoundError recovery branch forwarded
    # venue/chain/screening_details/geo to push_new but not city/
    # country, silently dropping X-CITY/X-COUNTRY on the recreated
    # event - a real regression in #217's own fix.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None, city="Amsterdam", country="Netherlands")
    stale_uid = entry.caldav_uid
    assert stale_uid is not None
    del calendar.events_by_uid[stale_uid]  # simulates an external wipe

    sync.push_update(entry, venue=None, city="Amsterdam", country="Netherlands")

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    ical_text = calendar.events_by_uid[refreshed.caldav_uid].data
    assert "X-CITY:Amsterdam" in ical_text
    assert "X-COUNTRY:Netherlands" in ical_text


def test_push_update_stale_uid_recovery_keeps_importer(store: Store) -> None:
    # Same class of bug as #262, same call site (the NotFoundError
    # recovery branch's push_new call) - added importer/importer_version
    # here alongside city/country, so this guards against a repeat of
    # that exact mistake for the new parameter.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None, importer="log")
    stale_uid = entry.caldav_uid
    assert stale_uid is not None
    del calendar.events_by_uid[stale_uid]  # simulates an external wipe

    sync.push_update(entry, venue=None, importer="log")

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    ical_text = calendar.events_by_uid[refreshed.caldav_uid].data
    assert "X-IMPORTER:log" in ical_text


def test_push_update_stale_uid_recovery_keeps_street_address(store: Store) -> None:
    # Same class of bug as #262/#257, same call site - guards street
    # address/postal code (issue #283) against the same mistake.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(
        entry,
        venue=None,
        street_address="Teststraat 1",
        postal_code="1000 AA",
    )
    stale_uid = entry.caldav_uid
    assert stale_uid is not None
    del calendar.events_by_uid[stale_uid]  # simulates an external wipe

    sync.push_update(entry, venue=None, street_address="Teststraat 1", postal_code="1000 AA")

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    ical_text = calendar.events_by_uid[refreshed.caldav_uid].data
    assert "X-STREET-ADDRESS:Teststraat 1" in ical_text
    assert "X-POSTAL-CODE:1000 AA" in ical_text


def test_push_update_stale_uid_recovery_keeps_venue(store: Store) -> None:
    # Same class of bug as #262/#257/#283 - guards the recreated event's
    # LOCATION (the venue itself, not just city/country) against the same
    # "forwarded to push_new but forgotten" mistake.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue="Grand Vista Cinema")
    stale_uid = entry.caldav_uid
    assert stale_uid is not None
    del calendar.events_by_uid[stale_uid]  # simulates an external wipe

    sync.push_update(entry, venue="Grand Vista Cinema")

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    ical_text = calendar.events_by_uid[refreshed.caldav_uid].data
    assert "LOCATION:Grand Vista Cinema" in ical_text


def test_push_update_stale_uid_recovery_keeps_chain(store: Store) -> None:
    # Same class of bug as #262/#257/#283, guarding the chain line in the
    # recreated event's DESCRIPTION.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue="Tuschinski, Amsterdam, Netherlands", chain="Pathé")
    stale_uid = entry.caldav_uid
    assert stale_uid is not None
    del calendar.events_by_uid[stale_uid]  # simulates an external wipe

    sync.push_update(entry, venue="Tuschinski, Amsterdam, Netherlands", chain="Pathé")

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    ical_text = calendar.events_by_uid[refreshed.caldav_uid].data
    assert "Chain: Pathé" in ical_text


def test_push_update_stale_uid_recovery_keeps_screening_details(store: Store) -> None:
    # Same class of bug as #262/#257/#283, guarding the free-text
    # screening-details line in the recreated event's DESCRIPTION.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None, screening_details="Auditorium 1 DOLBY - Row 5 Seat 17")
    stale_uid = entry.caldav_uid
    assert stale_uid is not None
    del calendar.events_by_uid[stale_uid]  # simulates an external wipe

    sync.push_update(entry, venue=None, screening_details="Auditorium 1 DOLBY - Row 5 Seat 17")

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    ical_text = calendar.events_by_uid[refreshed.caldav_uid].data
    assert "Auditorium 1 DOLBY - Row 5 Seat 17" in ical_text


def test_push_update_stale_uid_recovery_keeps_geo(store: Store) -> None:
    # Same class of bug as #262/#257/#283, guarding GEO (issue #170) on the
    # recreated event.
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None, geo=(52.3667, 4.8945))
    stale_uid = entry.caldav_uid
    assert stale_uid is not None
    del calendar.events_by_uid[stale_uid]  # simulates an external wipe

    sync.push_update(entry, venue=None, geo=(52.3667, 4.8945))

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
    event = _parse(calendar.events_by_uid[refreshed.caldav_uid].data)
    geo = event["geo"]
    assert isinstance(geo, icalendar.vGeo)
    assert (round(geo.latitude, 4), round(geo.longitude, 4)) == (52.3667, 4.8945)


def test_push_update_failure_is_wrapped_and_retryable(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    calendar.fail_next = True

    with pytest.raises(
        CalendarSyncError, match=f"could not sync the update to '{entry.title}' to the calendar: "
    ):
        sync.push_update(entry, venue=None)

    calendar.fail_next = False
    sync.push_update(entry, venue=None)  # retry succeeds


def test_push_delete_failure_is_wrapped(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    calendar.fail_next = True

    with pytest.raises(
        CalendarSyncError, match=f"could not remove '{entry.title}' from the calendar: "
    ):
        sync.push_delete(entry)


def test_push_new_failure_leaves_the_local_entry_persisted_and_is_retryable(
    store: Store,
) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar(fail_next=True)
    sync = CalendarSync(store, CalendarClient(calendar))

    with pytest.raises(CalendarSyncError):
        sync.push_new(entry, venue=None)

    # The entry survived the failed push and can be retried - via
    # push_update, not push_new again (issue #246): a second push_new
    # can't tell whether the first one actually reached the server
    # despite the local error, so retrying has to go through the same
    # find-or-recreate path push_update already has.
    failed = store.get_entry(entry.id)
    calendar.fail_next = False
    sync.push_update(failed, venue=None)

    refreshed = store.get_entry(entry.id)
    assert refreshed.caldav_uid is not None
