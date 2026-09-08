"""Push-only sync to a Baikal (CalDAV) calendar. The local store is always
authoritative - see design.md's "Source of truth" and "Sync failure"
decisions. Nothing here ever reads the calendar back into the store.
"""

import logging
import uuid
from collections.abc import Sequence
from datetime import date, datetime, time
from importlib.metadata import version
from typing import Protocol, cast

import icalendar
from caldav.davclient import DAVClient
from caldav.lib.error import NotFoundError

from movie_planner.store import Entry, Store

logger = logging.getLogger(__name__)


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
    City/country go on LOCATION (via `_venue_location` in cli.py) and,
    additionally, their own X-CITY/X-COUNTRY properties (issue #217) -
    never in the description here.
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
    # Long-form OMDb fields (issue #237) - labelled, same reasoning as
    # Notes below: nothing but position would otherwise tell them
    # apart from each other or from screening_details.
    if entry.released:
        lines.append(f"Released: {entry.released}")
    if entry.plot:
        lines.append(f"Plot: {entry.plot}")
    if entry.awards:
        lines.append(f"Awards: {entry.awards}")
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
    extra_properties: dict[str, str] | None = None,
    geo: tuple[float, float] | None = None,
) -> str:
    """Maps a movie-log entry's date/time completeness to a VEVENT:
    date-only -> all-day, start-only -> DTSTART with no DTEND, both -> a
    normal ranged event. See design.md's "VEVENT mapping" decision.
    `extra_properties` covers movie-planner's custom `X-*` properties
    (`X-POSTER-URL`, `X-DIRECTOR`, `X-ACTORS`, `X-GENRE`, `X-YEAR`) -
    bare X-NAME form, matching what movie-planner-web already reads, per
    docs/calendar-schema.md. Only set (non-empty) values belong in the
    dict; this adds whatever it's given with no further filtering.
    `geo` is `(latitude, longitude)` for a venue with known coordinates
    (issue #170) - omitted entirely, never guessed, when there are none.
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
    if geo is not None:
        event.add("geo", geo)
    for name, value in (extra_properties or {}).items():
        event.add(name, value)

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

    def list_events(self) -> list[str]:
        """Raw iCalendar text for every event on the calendar - the read
        side `sync pull` (issue #235) needs; `check_connection` above
        deliberately doesn't route through this, it only needs
        connectivity, not the data.
        """
        return [cast(_CalDAVEvent, e).data for e in self._calendar.events()]

    def create_event(self, ical_text: str) -> None:
        self._calendar.add_event(ical=ical_text)

    def update_event(self, uid: str, ical_text: str) -> None:
        event = self._calendar.event_by_uid(uid)
        event.data = ical_text
        event.save()

    def delete_event(self, uid: str) -> None:
        event = self._calendar.event_by_uid(uid)
        event.delete()


def _extra_properties(
    entry: Entry,
    *,
    city: str | None = None,
    country: str | None = None,
    street_address: str | None = None,
    postal_code: str | None = None,
    importer: str | None = None,
) -> dict[str, str]:
    values: dict[str, str | None] = {
        "X-POSTER-URL": entry.poster_url,
        "X-DIRECTOR": entry.director,
        "X-ACTORS": entry.actors,
        "X-GENRE": entry.genre,
        "X-YEAR": str(entry.release_year) if entry.release_year is not None else None,
        # Additive to LOCATION's own "venue, city, country" string
        # (issue #217) - a structured field movie-planner-web can read
        # without parsing LOCATION apart, same "omit, never guess" rule
        # as everything else here: only set for a venue matching the
        # hardcoded chain/location table.
        "X-CITY": city,
        "X-COUNTRY": country,
        # Same reasoning as X-CITY/X-COUNTRY, split rather than one
        # combined X-ADDRESS (issue #283, agreed jointly with
        # movie-planner-web): a direct 1:1 passthrough, each omitted
        # independently when its own value isn't known - LOCATION is the
        # only place these two are ever paired together.
        "X-STREET-ADDRESS": street_address,
        "X-POSTAL-CODE": postal_code,
        # Structured, unlike screening_details' free text (issue #218) -
        # already on Entry itself, so no extra push_new/push_update
        # parameter is needed the way city/country above required one.
        "X-ROW": entry.row,
        "X-SEAT": entry.seat,
        # The rest of OMDb's response (issue #237) - discrete values
        # only; Plot/Awards/Released go into DESCRIPTION instead
        # (build_description below), same as ratings/Letterboxd
        # already do, since they're long-form text rather than a
        # single value. X-MOVIE-LANGUAGE/X-MOVIE-COUNTRY, not
        # X-LANGUAGE/X-COUNTRY - the movie's own country/language of
        # origin is a different thing from the venue's X-CITY/
        # X-COUNTRY (#217), and reusing that name would collide.
        "X-RATED": entry.rated,
        "X-RUNTIME": entry.runtime,
        "X-MOVIE-LANGUAGE": entry.language,
        "X-MOVIE-COUNTRY": entry.country,
        "X-METASCORE": entry.metascore,
        "X-IMDB-VOTES": entry.imdb_votes,
        "X-DVD": entry.dvd,
        "X-BOX-OFFICE": entry.box_office,
        "X-PRODUCTION": entry.production,
        "X-WEBSITE": entry.website,
        # TMDb's own YouTube trailer link (issue #236) - not from OMDb,
        # looked up separately by imdb_id once OMDb has matched a title.
        # Same "omit, never guess" rule: no tmdb.api_key configured, or no
        # official YouTube trailer found, and this is simply absent.
        "X-TRAILER-URL": entry.trailer_url,
        # Debugging provenance (issue #257) - which movie-planner command
        # performed this push, and which version of the tool did it.
        # Same "omit, never guess" rule: a caller that doesn't pass
        # importer (a test using CalendarSync directly, say) gets
        # neither property, rather than a guessed "unknown" importer
        # with a real version attached to it.
        "X-IMPORTER": importer,
        "X-IMPORTER-VERSION": version("movie-planner") if importer else None,
    }
    return {name: value for name, value in values.items() if value}


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
        geo: tuple[float, float] | None = None,
        city: str | None = None,
        country: str | None = None,
        street_address: str | None = None,
        postal_code: str | None = None,
        importer: str | None = None,
    ) -> Entry:
        # uuid7, not uuid4: time-ordered, so newly-created entries insert
        # sequentially rather than at a random point - and it's already
        # in Python 3.14's stdlib, no new dependency needed.
        uid = str(uuid.uuid7())
        ical_text = build_vevent(
            uid=uid,
            title=entry.title,
            entry_date=entry.date,
            start_time=entry.start_time,
            end_time=entry.end_time,
            venue=venue,
            description=build_description(entry, chain=chain, screening_details=screening_details),
            extra_properties=_extra_properties(
                entry,
                city=city,
                country=country,
                street_address=street_address,
                postal_code=postal_code,
                importer=importer,
            ),
            geo=geo,
        )
        logger.debug("Calendar push (create, uid=%s):\n%s", uid, ical_text)
        # The local store records this UID *before* the CalDAV create,
        # not after (issue #246). An interruption between the two - a
        # killed process, a dropped connection after the server actually
        # created the event - used to leave caldav_uid unset locally
        # while a real, orphaned event sat on the calendar; the next
        # retry had no way to tell it had already been created and made
        # a second, genuinely duplicate one. With the write done first,
        # the local record and the (possibly not-yet-existing) calendar
        # event always agree on the UID, so any later push for this
        # entry - push_update, from a normal retry or `sync refresh` -
        # either finds the real event and updates it, or gets
        # NotFoundError and recovers through the same path #166 already
        # added, in both cases without ever creating a second event.
        #
        # A caught create_event failure deliberately does NOT roll this
        # back to None: there's no reliable way here to tell "definitely
        # never reached the server" apart from "reached it, and only the
        # response was lost" - rolling back would reopen this exact bug
        # for the second case. Leaving it recorded is safe either way,
        # for the same reason above.
        updated = self._store.update_entry(entry.id, caldav_uid=uid)
        try:
            self._client.create_event(ical_text)
        except Exception as e:
            raise CalendarSyncError(f"could not sync '{entry.title}' to the calendar: {e}") from e
        return updated

    def push_update(
        self,
        entry: Entry,
        *,
        venue: str | None,
        chain: str | None = None,
        screening_details: str | None = None,
        geo: tuple[float, float] | None = None,
        city: str | None = None,
        country: str | None = None,
        street_address: str | None = None,
        postal_code: str | None = None,
        importer: str | None = None,
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
            extra_properties=_extra_properties(
                entry,
                city=city,
                country=country,
                street_address=street_address,
                postal_code=postal_code,
                importer=importer,
            ),
            geo=geo,
        )
        logger.debug("Calendar push (update, uid=%s):\n%s", entry.caldav_uid, ical_text)
        try:
            self._client.update_event(entry.caldav_uid, ical_text)
        except NotFoundError:
            # The calendar no longer has this UID - wiped or rebuilt
            # out-of-band (movie-planner#166). Treat the entry as never
            # synced instead of failing forever: clear the stale UID and
            # create a fresh event.
            never_synced = self._store.update_entry(entry.id, caldav_uid=None)
            self.push_new(
                never_synced,
                venue=venue,
                chain=chain,
                screening_details=screening_details,
                geo=geo,
                city=city,
                country=country,
                street_address=street_address,
                postal_code=postal_code,
                importer=importer,
            )
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
