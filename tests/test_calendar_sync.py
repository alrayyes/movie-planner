from collections.abc import Iterator
from datetime import date, time
from pathlib import Path

import icalendar
import pytest
from fakes import FakeCalendar

from movie_planner.calendar_sync import (
    CalendarClient,
    CalendarSync,
    CalendarSyncError,
    build_vevent,
)
from movie_planner.store import Store

# --- build_vevent: task 4.2, the three time-completeness mapping rules ---


def _parse(ical_text: str) -> icalendar.Event:
    cal = icalendar.Calendar.from_ical(ical_text)
    (event,) = [c for c in cal.subcomponents if c.name == "VEVENT"]
    return event


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
    assert event["dtstart"].dt == date(2024, 1, 20)
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
    from datetime import datetime

    assert event["dtstart"].dt == datetime(2024, 6, 2, 16, 10)
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
    from datetime import datetime

    assert event["dtstart"].dt == datetime(2024, 3, 15, 14, 0)
    assert event["dtend"].dt == datetime(2024, 3, 15, 16, 32)


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


# --- CalendarClient: task 4.1, wrapping a caldav.Calendar-like object ---


def test_calendar_client_connect_wires_up_the_dav_client(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    class FakeDAVClient:
        def __init__(self, url: str, username: str, password: str) -> None:
            calls["init"] = {"url": url, "username": username, "password": password}

        def calendar(self, url: str) -> FakeCalendar:
            calls["calendar_url"] = url
            return FakeCalendar()

    monkeypatch.setattr("movie_planner.calendar_sync.caldav.DAVClient", FakeDAVClient)

    client = CalendarClient.connect(
        url="https://baikal.example.com/calendars/movies/",
        username="moviewatcher",
        password="secret",
    )

    assert isinstance(client, CalendarClient)
    assert calls["init"]["username"] == "moviewatcher"
    assert calls["calendar_url"] == "https://baikal.example.com/calendars/movies/"


def test_calendar_client_check_connection_succeeds() -> None:
    client = CalendarClient(FakeCalendar())
    client.check_connection()  # does not raise


def test_calendar_client_check_connection_propagates_failure() -> None:
    client = CalendarClient(FakeCalendar(fail_next=True))
    with pytest.raises(ConnectionError):
        client.check_connection()


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


def test_push_update_changes_the_linked_event(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    entry = store.update_entry(entry.id, title="Dune Part Two")

    sync.push_update(entry, venue=None)

    assert "Dune Part Two" in calendar.events_by_uid[entry.caldav_uid].data


def test_push_delete_removes_the_linked_event(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)

    sync.push_delete(entry)

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


def test_push_update_failure_is_wrapped_and_retryable(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    calendar = FakeCalendar()
    sync = CalendarSync(store, CalendarClient(calendar))
    entry = sync.push_new(entry, venue=None)
    calendar.fail_next = True

    with pytest.raises(CalendarSyncError):
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

    with pytest.raises(CalendarSyncError):
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

    # The entry survived the failed push, unsynced, and can be retried.
    assert store.get_entry(entry.id).caldav_uid is None
    calendar.fail_next = False
    synced = sync.push_new(entry, venue=None)
    assert synced.caldav_uid is not None
