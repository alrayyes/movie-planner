"""Push-only sync to a Baikal (CalDAV) calendar. The local store is always
authoritative - see design.md's "Source of truth" and "Sync failure"
decisions. Nothing here ever reads the calendar back into the store.
"""

import uuid
from datetime import date, datetime, time
from typing import Protocol

import caldav
import icalendar

from movie_planner.store import Entry, Store


class CalendarSyncError(Exception):
    """Raised when pushing to the calendar fails. The local entry is
    already persisted and unaffected by the failure - calling the same
    method again retries the same push.
    """


def build_vevent(
    *,
    uid: str,
    title: str,
    entry_date: date,
    start_time: time | None,
    end_time: time | None,
    venue: str | None,
) -> str:
    """Maps a movie-log entry's date/time completeness to a VEVENT:
    date-only -> all-day, start-only -> DTSTART with no DTEND, both -> a
    normal ranged event. See design.md's "VEVENT mapping" decision.
    """
    calendar = icalendar.Calendar()
    calendar.add("prodid", "-//movie-planner//EN")
    calendar.add("version", "2.0")

    event = icalendar.Event()
    event.add("uid", uid)
    event.add("summary", title)
    if venue:
        event.add("location", venue)

    if start_time is None:
        event.add("dtstart", entry_date)
    elif end_time is None:
        event.add("dtstart", datetime.combine(entry_date, start_time))
    else:
        event.add("dtstart", datetime.combine(entry_date, start_time))
        event.add("dtend", datetime.combine(entry_date, end_time))

    calendar.add_component(event)
    return calendar.to_ical().decode("utf-8")


class _CalDAVCalendar(Protocol):
    """The slice of caldav.Calendar this module depends on - narrow enough
    that a test double can satisfy it without touching the real library.
    """

    def events(self) -> list[object]: ...
    def add_event(self, ical: str) -> object: ...
    def event_by_uid(self, uid: str) -> object: ...


class CalendarClient:
    def __init__(self, calendar: _CalDAVCalendar) -> None:
        self._calendar = calendar

    @classmethod
    def connect(cls, *, url: str, username: str, password: str) -> CalendarClient:
        client = caldav.DAVClient(url=url, username=username, password=password)
        return cls(client.calendar(url=url))

    def check_connection(self) -> None:
        self._calendar.events()

    def create_event(self, ical_text: str) -> None:
        self._calendar.add_event(ical=ical_text)

    def update_event(self, uid: str, ical_text: str) -> None:
        event = self._calendar.event_by_uid(uid)
        event.data = ical_text
        event.save()

    def delete_event(self, uid: str) -> None:
        event = self._calendar.event_by_uid(uid)
        event.delete()


class CalendarSync:
    def __init__(self, store: Store, client: CalendarClient) -> None:
        self._store = store
        self._client = client

    def push_new(self, entry: Entry, *, venue: str | None) -> Entry:
        uid = str(uuid.uuid4())
        ical_text = build_vevent(
            uid=uid,
            title=entry.title,
            entry_date=entry.date,
            start_time=entry.start_time,
            end_time=entry.end_time,
            venue=venue,
        )
        try:
            self._client.create_event(ical_text)
        except Exception as e:
            raise CalendarSyncError(f"could not sync '{entry.title}' to the calendar: {e}") from e
        return self._store.update_entry(entry.id, caldav_uid=uid)

    def push_update(self, entry: Entry, *, venue: str | None) -> None:
        if entry.caldav_uid is None:
            raise CalendarSyncError(f"'{entry.title}' has never been synced to the calendar")
        ical_text = build_vevent(
            uid=entry.caldav_uid,
            title=entry.title,
            entry_date=entry.date,
            start_time=entry.start_time,
            end_time=entry.end_time,
            venue=venue,
        )
        try:
            self._client.update_event(entry.caldav_uid, ical_text)
        except Exception as e:
            raise CalendarSyncError(
                f"could not sync the update to '{entry.title}' to the calendar: {e}"
            ) from e

    def push_delete(self, entry: Entry) -> None:
        if entry.caldav_uid is None:
            return
        try:
            self._client.delete_event(entry.caldav_uid)
        except Exception as e:
            raise CalendarSyncError(
                f"could not remove '{entry.title}' from the calendar: {e}"
            ) from e
