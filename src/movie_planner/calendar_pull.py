"""Reads calendar events back and reconciles them against the local
store - the reverse of `calendar_sync.py`'s push-only
`build_vevent`/`build_description`/`_extra_properties`, and
deliberately kept as its own module: `calendar-sync-pull` is a
separate capability from `calendar-sync`, whose push-only contract
this never touches (issue #168/#235). Nothing here writes to the
store - `detect_candidates` only reports what could change; the
caller (`cli.py`'s `sync pull`) applies an approved candidate via
`Store.create_entry`/`update_entry`/`delete_entry`.
"""

from dataclasses import dataclass
from datetime import date, datetime, time

import icalendar

from movie_planner.store import Entry, Store
from movie_planner.venue_locations import KNOWN_VENUE_LOCATIONS


@dataclass(frozen=True)
class ParsedEvent:
    """A calendar VEVENT's structured fields, reverse-mapped from
    exactly the set `build_vevent`/`_extra_properties` write - see
    design.md's "Changed is scoped to what's actually parsed" decision.
    Ratings/Letterboxd/chain/notes are never reconstructed from
    DESCRIPTION - deliberately absent here, not just left unset, since
    that text has no reliable per-field boundary to parse.
    """

    uid: str
    title: str
    date: date
    start_time: time | None
    end_time: time | None
    venue_name: str | None
    director: str | None
    actors: str | None
    genre: str | None
    release_year: int | None
    poster_url: str | None
    row: str | None
    seat: str | None


def _text(vevent: icalendar.Event, name: str) -> str | None:
    value = vevent.get(name)
    return str(value) if value is not None else None


def _canonical_venue_name(name: str) -> str:
    """Alias resolution only - no store access, so this is safe to call
    while merely computing a diff, before anything is approved. The
    same table `Store.get_or_create_venue` itself consults (#196/#227);
    calling that method is what actually creates a venue row, and stays
    reserved for applying an approved candidate, never detection.
    """
    location = KNOWN_VENUE_LOCATIONS.get(name)
    return location.canonical_name if location is not None else name


def _resolve_venue_name(vevent: icalendar.Event) -> str | None:
    """design.md's "Venue resolution: exact-match strip, not a guess" -
    strips a trailing address suffix from LOCATION only when it exactly
    matches the event's own X-* properties; otherwise LOCATION is used
    verbatim, since a manually-typed-via-web LOCATION might not follow
    either shape at all.

    Two suffix shapes to try, mirroring cli.py's `_venue_location`
    exactly (issue #283's mutmut-testing-coverage regression, movie-
    planner-web#400's report of an entire history's venues collapsing
    into "Other locations"): a venue with a verified street address
    *and* postal code gets the fuller ", street, postal city, country"
    suffix, tried first since it's the more specific shape; every other
    venue only ever gets the plain ", city, country" one. Trying the
    plain suffix alone against the fuller LOCATION never matches - the
    postal code sits between the comma and the city - which is exactly
    what let the whole street/postal/city/country tail get treated as
    part of the venue name instead of stripped.
    """
    location = _text(vevent, "LOCATION")
    if location is None:
        return None
    city = _text(vevent, "X-CITY")
    country = _text(vevent, "X-COUNTRY")
    if not (city and country):
        return _canonical_venue_name(location)
    street_address = _text(vevent, "X-STREET-ADDRESS")
    postal_code = _text(vevent, "X-POSTAL-CODE")
    suffixes = []
    if street_address and postal_code:
        suffixes.append(f", {street_address}, {postal_code} {city}, {country}")
    suffixes.append(f", {city}, {country}")
    for suffix in suffixes:
        if location.endswith(suffix):
            return _canonical_venue_name(location[: -len(suffix)])
    return _canonical_venue_name(location)


def _dt(vevent: icalendar.Event, name: str) -> date | datetime:
    # vevent[name] is typed as icalendar's big property-value union -
    # only the DATE/DATE-TIME wrapper actually has .dt, same narrowing
    # calendar_sync's own tests already use for the forward direction.
    value = vevent[name]
    assert isinstance(value, icalendar.vDDDTypes)  # nosec B101 - narrows a real-server invariant
    assert isinstance(value.dt, date)  # nosec B101 - same
    return value.dt


def parse_event(ical_text: str) -> ParsedEvent:
    calendar = icalendar.Calendar.from_ical(ical_text)
    (vevent,) = [c for c in calendar.subcomponents if c.name == "VEVENT"]
    assert isinstance(vevent, icalendar.Event)  # nosec B101 - narrows a real-server invariant

    dtstart = _dt(vevent, "dtstart")
    if isinstance(dtstart, datetime):
        entry_date = dtstart.date()
        start_time: time | None = dtstart.time()
    else:
        entry_date = dtstart
        start_time = None

    end_time: time | None = None
    if "dtend" in vevent:
        dtend = _dt(vevent, "dtend")
        # build_vevent only ever sets DTEND as DATE-TIME - narrows a real-server invariant.
        assert isinstance(dtend, datetime)  # nosec B101
        end_time = dtend.time()

    release_year_text = _text(vevent, "X-YEAR")

    return ParsedEvent(
        uid=str(vevent["uid"]),
        title=str(vevent["summary"]),
        date=entry_date,
        start_time=start_time,
        end_time=end_time,
        venue_name=_resolve_venue_name(vevent),
        director=_text(vevent, "X-DIRECTOR"),
        actors=_text(vevent, "X-ACTORS"),
        genre=_text(vevent, "X-GENRE"),
        release_year=int(release_year_text) if release_year_text else None,
        poster_url=_text(vevent, "X-POSTER-URL"),
        row=_text(vevent, "X-ROW"),
        seat=_text(vevent, "X-SEAT"),
    )


@dataclass(frozen=True)
class FieldDiff:
    field: str
    stored: object
    calendar: object


@dataclass(frozen=True)
class NewCandidate:
    parsed: ParsedEvent


@dataclass(frozen=True)
class ChangedCandidate:
    entry: Entry
    parsed: ParsedEvent
    diffs: list[FieldDiff]


@dataclass(frozen=True)
class RemovedCandidate:
    entry: Entry


Candidate = NewCandidate | ChangedCandidate | RemovedCandidate


def _venue_name_for_entry(store: Store, entry: Entry) -> str | None:
    if entry.venue_id is None:
        return None
    venue = next((v for v in store.list_venues() if v.id == entry.venue_id), None)
    return venue.name if venue is not None else None


def _diff_entry(entry: Entry, parsed: ParsedEvent, venue_name: str | None) -> list[FieldDiff]:
    # Exactly the structured fields spec.md's "Detect a local entry whose
    # linked event changed" requirement lists - nothing DESCRIPTION-
    # derived (ratings/Letterboxd/chain/notes) is ever compared.
    comparisons: tuple[tuple[str, object, object], ...] = (
        ("title", entry.title, parsed.title),
        ("date", entry.date, parsed.date),
        ("start_time", entry.start_time, parsed.start_time),
        ("end_time", entry.end_time, parsed.end_time),
        ("venue", venue_name, parsed.venue_name),
        ("director", entry.director, parsed.director),
        ("actors", entry.actors, parsed.actors),
        ("genre", entry.genre, parsed.genre),
        ("release_year", entry.release_year, parsed.release_year),
        ("poster_url", entry.poster_url, parsed.poster_url),
        ("row", entry.row, parsed.row),
        ("seat", entry.seat, parsed.seat),
    )
    return [
        FieldDiff(field=name, stored=stored, calendar=calendar_value)
        for name, stored, calendar_value in comparisons
        if stored != calendar_value
    ]


def detect_candidates(store: Store, ical_texts: list[str]) -> list[Candidate]:
    """Reads every event's UID and compares it against the local store's
    entries by `caldav_uid` - see spec.md's three detection
    requirements. Read-only: nothing here writes to the store, so
    running `sync pull` to see what it would do is always safe.
    """
    parsed_events = [parse_event(text) for text in ical_texts]
    events_by_uid = {p.uid: p for p in parsed_events}
    entries = store.list_entries()
    synced_entries_by_uid = {e.caldav_uid: e for e in entries if e.caldav_uid is not None}

    candidates: list[Candidate] = [
        NewCandidate(parsed=parsed)
        for parsed in parsed_events
        if parsed.uid not in synced_entries_by_uid
    ]

    for entry in entries:
        if entry.caldav_uid is None:
            continue
        parsed = events_by_uid.get(entry.caldav_uid)
        if parsed is None:
            candidates.append(RemovedCandidate(entry=entry))
            continue
        diffs = _diff_entry(entry, parsed, _venue_name_for_entry(store, entry))
        if diffs:
            candidates.append(ChangedCandidate(entry=entry, parsed=parsed, diffs=diffs))

    return candidates
