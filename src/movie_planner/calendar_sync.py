"""Push-only sync to a Baikal (CalDAV) calendar. The local store is always
authoritative - see design.md's "Source of truth" and "Sync failure"
decisions. Nothing here ever reads the calendar back into the store.
"""

import uuid
from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Protocol, cast

import icalendar
from caldav.davclient import DAVClient

from movie_planner.store import Entry, Store


class CalendarSyncError(Exception):
    """Raised when pushing to the calendar fails. The local entry is
    already persisted and unaffected by the failure - calling the same
    method again retries the same push.
    """


def build_description(
    entry: Entry, *, chain: str | None = None, screening_details: str | None = None
) -> str | None:
    """Builds the text for a VEVENT's description from whatever metadata
    an entry has - ratings, Letterboxd, the venue's chain, and, for a
    Pathé-sourced entry, the screening format/seat text - or None when
    there's nothing to show. Nothing here is persisted on `Entry`; chain
    comes from the venue, and screening details are provenance for the
    calendar event only. See design.md's "Description content" decision.
    City/country go on LOCATION instead, not here - see `_venue_location`
    in cli.py.
    """
    lines: list[str] = []
    if entry.imdb_rating and entry.imdb_url:
        lines.append(f"IMDb: {entry.imdb_rating} ({entry.imdb_url})")
    elif entry.imdb_rating:
        lines.append(f"IMDb: {entry.imdb_rating}")
    elif entry.imdb_url:
        lines.append(f"IMDb: {entry.imdb_url}")
    if entry.rotten_tomatoes_rating:
        lines.append(f"Rotten Tomatoes: {entry.rotten_tomatoes_rating}")
    if entry.metacritic_rating:
        lines.append(f"Metacritic: {entry.metacritic_rating}")
    if entry.letterboxd_url:
        suffix = f" ({entry.letterboxd_rating})" if entry.letterboxd_rating else ""
        lines.append(f"Letterboxd: {entry.letterboxd_url}{suffix}")
    if chain:
        lines.append(f"Chain: {chain}")
    if entry.notes:
        lines.append(f"Notes: {entry.notes}")
    if screening_details:
        lines.append(screening_details)
    return "\n".join(lines) if lines else None


def build_vevent(
    *,
    uid: str,
    title: str,
    entry_date: date,
    start_time: time | None,
    end_time: time | None,
    venue: str | None,
    description: str | None = None,
    poster_url: str | None = None,
) -> str:
    """Maps a movie-log entry's date/time completeness to a VEVENT:
    date-only -> all-day, start-only -> DTSTART with no DTEND, both -> a
    normal ranged event. See design.md's "VEVENT mapping" decision.
    `X-POSTER-URL` is movie-planner's first (and so far only) custom
    property - matches the bare X-NAME movie-planner-web already reads,
    per docs/calendar-schema.md.
    """
    calendar = icalendar.Calendar()
    calendar.add("prodid", "-//movie-planner//EN")
    calendar.add("version", "2.0")

    event = icalendar.Event()
    event.add("uid", uid)
    event.add("summary", title)
    if venue:
        event.add("location", venue)
    if description:
        event.add("description", description)
    if poster_url:
        event.add("X-POSTER-URL", poster_url)

    if start_time is None:
        event.add("dtstart", entry_date)
    elif end_time is None:
        event.add("dtstart", datetime.combine(entry_date, start_time))
    else:
        event.add("dtstart", datetime.combine(entry_date, start_time))
        event.add("dtend", datetime.combine(entry_date, end_time))

    calendar.add_component(event)
    # icalendar ships no return-type annotations; to_ical() always returns
    # bytes at runtime.
    return cast(bytes, calendar.to_ical()).decode("utf-8")


class _CalDAVEvent(Protocol):
    """The slice of a caldav.Event (or the test double standing in for
    one) this module needs.
    """

    data: str

    def save(self) -> None: ...
    def delete(self) -> None: ...


class _CalDAVCalendar(Protocol):
    """The slice of caldav.Calendar this module depends on - narrow enough
    that a test double can satisfy it without touching the real library.
    """

    # Sequence, not list: list[T] is invariant, so a concrete implementation
    # returning list[FakeEvent] (the test double) or list[caldav.CalendarObjectResource]
    # (the real one) wouldn't structurally satisfy list[object] - Sequence[T]
    # is covariant, and nothing here needs list-specific mutation anyway.
    def events(self) -> Sequence[object]: ...
    def add_event(self, ical: str) -> object: ...
    def event_by_uid(self, uid: str) -> _CalDAVEvent: ...


class CalendarClient:
    def __init__(self, calendar: _CalDAVCalendar) -> None:
        self._calendar = calendar

    @classmethod
    def connect(cls, *, url: str, username: str, password: str) -> CalendarClient:
        client = DAVClient(url=url, username=username, password=password)
        # caldav.DAVClient.calendar() ships no annotations at all - cast
        # covers the return type, but the call itself still needs the
        # ignore for strict mode's disallow_untyped_calls.
        return cls(cast(_CalDAVCalendar, client.calendar(url=url)))  # type: ignore[no-untyped-call]

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

    def push_new(
        self,
        entry: Entry,
        *,
        venue: str | None,
        chain: str | None = None,
        screening_details: str | None = None,
    ) -> Entry:
        uid = str(uuid.uuid4())
        ical_text = build_vevent(
            uid=uid,
            title=entry.title,
            entry_date=entry.date,
            start_time=entry.start_time,
            end_time=entry.end_time,
            venue=venue,
            description=build_description(entry, chain=chain, screening_details=screening_details),
            poster_url=entry.poster_url,
        )
        try:
            self._client.create_event(ical_text)
        except Exception as e:
            raise CalendarSyncError(f"could not sync '{entry.title}' to the calendar: {e}") from e
        return self._store.update_entry(entry.id, caldav_uid=uid)

    def push_update(
        self,
        entry: Entry,
        *,
        venue: str | None,
        chain: str | None = None,
        screening_details: str | None = None,
    ) -> None:
        if entry.caldav_uid is None:
            raise CalendarSyncError(f"'{entry.title}' has never been synced to the calendar")
        ical_text = build_vevent(
            uid=entry.caldav_uid,
            title=entry.title,
            entry_date=entry.date,
            start_time=entry.start_time,
            end_time=entry.end_time,
            venue=venue,
            description=build_description(entry, chain=chain, screening_details=screening_details),
            poster_url=entry.poster_url,
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
