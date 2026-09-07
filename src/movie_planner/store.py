"""The local SQLite store: media, venues, and entries. This is the source
of truth - see design.md's "Source of truth" decision. The calendar is a
synced mirror, never read back from.
"""

import datetime
import json
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from movie_planner.venue_locations import KNOWN_VENUE_LOCATIONS

_UNSET: Any = object()

SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_physical_place INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    chain TEXT,
    city TEXT,
    country TEXT,
    latitude REAL,
    longitude REAL
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    medium_id INTEGER NOT NULL REFERENCES media(id),
    venue_id INTEGER REFERENCES venues(id),
    caldav_uid TEXT,
    imdb_rating TEXT,
    rotten_tomatoes_rating TEXT,
    metacritic_rating TEXT,
    letterboxd_url TEXT,
    letterboxd_rating TEXT,
    imdb_url TEXT,
    booking_ref TEXT,
    notes TEXT,
    poster_url TEXT,
    director TEXT,
    actors TEXT,
    genre TEXT,
    release_year INTEGER,
    source TEXT
);

CREATE TABLE IF NOT EXISTS import_failures (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    error TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    entry_id INTEGER NOT NULL,
    entry_title TEXT NOT NULL,
    changes TEXT,
    created_at TEXT NOT NULL
);
"""

# Columns added to `entries` after its initial release, ALTERed in for a
# database created before each one existed - CREATE TABLE IF NOT EXISTS
# above only covers a brand-new database. Each pair is (column, SQL type);
# nearly all of these are TEXT, so a plain string is TEXT and only a
# column needing a different affinity (release_year) spells it out.
_MIGRATED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("caldav_uid", "TEXT"),
    ("imdb_rating", "TEXT"),
    ("rotten_tomatoes_rating", "TEXT"),
    ("metacritic_rating", "TEXT"),
    ("letterboxd_url", "TEXT"),
    ("letterboxd_rating", "TEXT"),
    ("imdb_url", "TEXT"),
    ("booking_ref", "TEXT"),
    ("notes", "TEXT"),
    ("poster_url", "TEXT"),
    ("director", "TEXT"),
    ("actors", "TEXT"),
    ("genre", "TEXT"),
    ("release_year", "INTEGER"),
    ("source", "TEXT"),
    ("row", "TEXT"),
    ("seat", "TEXT"),
    ("rated", "TEXT"),
    ("released", "TEXT"),
    ("runtime", "TEXT"),
    ("writer", "TEXT"),
    ("plot", "TEXT"),
    ("language", "TEXT"),
    ("country", "TEXT"),
    ("awards", "TEXT"),
    ("metascore", "TEXT"),
    ("imdb_votes", "TEXT"),
    ("dvd", "TEXT"),
    ("box_office", "TEXT"),
    ("production", "TEXT"),
    ("website", "TEXT"),
    # TMDb's own YouTube trailer link (issue #236) - not an OMDb field,
    # looked up separately by imdb_id once OMDb has matched a title. Same
    # "never on create_entry" convention as the OMDb-derived fields above.
    ("trailer_url", "TEXT"),
    # The date of the most recent OMDb lookup that found no match for
    # this entry (issue #255) - distinct from "never looked up", which
    # is every OMDb-derived field staying None. Cleared (set back to
    # None) the moment a later lookup does find a match, so this is
    # always "the last attempt's outcome", never a permanent scar.
    ("omdb_last_no_match", "TEXT"),
)

_MIGRATED_VENUE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("chain", "TEXT"),
    ("city", "TEXT"),
    ("country", "TEXT"),
    ("latitude", "REAL"),
    ("longitude", "REAL"),
)


class StoreError(Exception):
    """Raised for a store-level constraint violation - a duplicate name,
    removing a medium/venue still referenced by an entry, or looking up an
    entry that doesn't exist. The message is shown to the user as-is.
    """


@dataclass(frozen=True)
class Medium:
    id: int
    name: str
    is_physical_place: bool


@dataclass(frozen=True)
class Venue:
    id: int
    name: str
    chain: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class VenueMerge:
    """One alias venue Store.merge_venue_aliases found (or, with
    apply=True, actually merged) into its canonical venue.
    """

    alias_name: str
    alias_venue_id: int
    canonical_name: str
    # None on a dry run when the canonical venue doesn't exist yet -
    # apply=True would create it, but a dry run never does.
    canonical_venue_id: int | None
    entries_moved: int


@dataclass(frozen=True)
class ImportFailure:
    """One row `run_import` (issue #254) couldn't parse - persisted so
    `movie-planner import-failures list` can show it after the run that
    produced it has scrolled away, not just at the moment it happened.
    """

    id: int
    source: str
    row_number: int
    error: str
    created_at: datetime.datetime


@dataclass(frozen=True)
class ActivityLogEntry:
    """One create/update/delete `create_entry`/`update_entry`/`delete_entry`
    made (issue #276) - the CLI's own local activity log, mirroring
    movie-planner-web#349's, but not a shared trail between the two apps.
    `entry_title` is a snapshot taken at the time of the action (the
    post-update title for an update, since that's what a person would
    recognize the entry by afterwards) rather than a live join to
    `entries`, so a `delete` still has something to display once the row
    it refers to is gone. `changes` is only set for `action == "update"` -
    field name to a (before, after) pair, and only for fields whose value
    actually changed, not every field `update_entry` was called with.
    """

    id: int
    action: str
    entry_id: int
    entry_title: str
    changes: dict[str, tuple[object, object]] | None
    created_at: datetime.datetime


@dataclass(frozen=True)
class Entry:
    id: int
    title: str
    date: datetime.date
    medium_id: int
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    venue_id: int | None = None
    caldav_uid: str | None = None
    imdb_rating: str | None = None
    rotten_tomatoes_rating: str | None = None
    metacritic_rating: str | None = None
    letterboxd_url: str | None = None
    letterboxd_rating: str | None = None
    imdb_url: str | None = None
    booking_ref: str | None = None
    notes: str | None = None
    poster_url: str | None = None
    director: str | None = None
    actors: str | None = None
    genre: str | None = None
    release_year: int | None = None
    source: str | None = None
    # Row/seat as structured values (movie-planner#218) - only ever set
    # from a Pathé booking parse, never manually via `log`/`update`.
    row: str | None = None
    seat: str | None = None
    # The rest of OMDb's response (issue #237) - see MovieRatings in
    # omdb.py for why these don't factor into needs_omdb_fetch.
    rated: str | None = None
    released: str | None = None
    runtime: str | None = None
    writer: str | None = None
    plot: str | None = None
    language: str | None = None
    country: str | None = None
    awards: str | None = None
    metascore: str | None = None
    imdb_votes: str | None = None
    dvd: str | None = None
    box_office: str | None = None
    production: str | None = None
    website: str | None = None
    # TMDb's own YouTube trailer link (issue #236) - see MovieRatings in
    # omdb.py; this one comes from tmdb.py instead, looked up by imdb_id
    # once OMDb has matched a title.
    trailer_url: str | None = None
    # The date of the most recent OMDb lookup that found no match for
    # this entry (issue #255) - see _MIGRATED_COLUMNS above for why this
    # is distinct from "never looked up" and always reflects only the
    # latest attempt.
    omdb_last_no_match: datetime.date | None = None


_ENTRY_COLUMNS = (
    "id",
    "title",
    "date",
    "start_time",
    "end_time",
    "medium_id",
    "venue_id",
    "caldav_uid",
    "imdb_rating",
    "rotten_tomatoes_rating",
    "metacritic_rating",
    "letterboxd_url",
    "letterboxd_rating",
    "imdb_url",
    "booking_ref",
    "notes",
    "poster_url",
    "director",
    "actors",
    "genre",
    "release_year",
    "source",
    "row",
    "seat",
    "rated",
    "released",
    "runtime",
    "writer",
    "plot",
    "language",
    "country",
    "awards",
    "metascore",
    "imdb_votes",
    "dvd",
    "box_office",
    "production",
    "website",
    "trailer_url",
    "omdb_last_no_match",
)


def _row_to_entry(row: tuple[Any, ...]) -> Entry:
    # A sqlite3 row is dynamically typed - Any is the honest boundary here,
    # not object; the schema (not mypy) is what guarantees each column's
    # real type below.
    values = dict(zip(_ENTRY_COLUMNS, row, strict=True))
    return Entry(
        id=values["id"],
        title=values["title"],
        date=datetime.date.fromisoformat(values["date"]),
        start_time=datetime.time.fromisoformat(values["start_time"])
        if values["start_time"]
        else None,
        end_time=datetime.time.fromisoformat(values["end_time"]) if values["end_time"] else None,
        medium_id=values["medium_id"],
        venue_id=values["venue_id"],
        caldav_uid=values["caldav_uid"],
        imdb_rating=values["imdb_rating"],
        rotten_tomatoes_rating=values["rotten_tomatoes_rating"],
        metacritic_rating=values["metacritic_rating"],
        letterboxd_url=values["letterboxd_url"],
        letterboxd_rating=values["letterboxd_rating"],
        imdb_url=values["imdb_url"],
        booking_ref=values["booking_ref"],
        notes=values["notes"],
        poster_url=values["poster_url"],
        director=values["director"],
        actors=values["actors"],
        genre=values["genre"],
        release_year=values["release_year"],
        source=values["source"],
        row=values["row"],
        seat=values["seat"],
        rated=values["rated"],
        released=values["released"],
        runtime=values["runtime"],
        writer=values["writer"],
        plot=values["plot"],
        language=values["language"],
        country=values["country"],
        awards=values["awards"],
        metascore=values["metascore"],
        imdb_votes=values["imdb_votes"],
        dvd=values["dvd"],
        box_office=values["box_office"],
        production=values["production"],
        website=values["website"],
        trailer_url=values["trailer_url"],
        omdb_last_no_match=datetime.date.fromisoformat(values["omdb_last_no_match"])
        if values["omdb_last_no_match"]
        else None,
    )


def _serialize_entry_field(name: str, value: object) -> object:
    if name in ("date", "omdb_last_no_match") and isinstance(value, datetime.date):
        return value.isoformat()
    if name in ("start_time", "end_time"):
        return value.isoformat() if isinstance(value, datetime.time) else None
    return value


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(entries)")}
        for column, sql_type in _MIGRATED_COLUMNS:
            if column not in columns:
                self._conn.execute(f"ALTER TABLE entries ADD COLUMN {column} {sql_type}")
        # Not UNIQUE: Pathé's own uniqueness guarantee for booking numbers
        # is unconfirmed - a plain index plus the caller's own confirmation
        # step is the safety net instead of a write that can fail outright.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entries_booking_ref ON entries(booking_ref)"
        )

        venue_columns = {row[1] for row in self._conn.execute("PRAGMA table_info(venues)")}
        for column, sql_type in _MIGRATED_VENUE_COLUMNS:
            if column not in venue_columns:
                self._conn.execute(f"ALTER TABLE venues ADD COLUMN {column} {sql_type}")
        self._backfill_known_venue_locations()

    def _backfill_known_venue_locations(self) -> None:
        # COALESCE fills only a column that's still NULL, one column at
        # a time - never overwrites a value already set (an earlier
        # backfill or a manual edit), and crucially doesn't gate on
        # every column being NULL together: a database that already
        # ran an older migration (chain/city/country from #111) still
        # needs this one to fill in latitude/longitude, which a single
        # "WHERE chain IS NULL AND city IS NULL AND country IS NULL"
        # check would skip entirely (movie-planner#185).
        for name, location in KNOWN_VENUE_LOCATIONS.items():
            latitude, longitude = location.coordinates or (None, None)
            self._conn.execute(
                "UPDATE venues SET "
                "chain = COALESCE(chain, ?), "
                "city = COALESCE(city, ?), "
                "country = COALESCE(country, ?), "
                "latitude = COALESCE(latitude, ?), "
                "longitude = COALESCE(longitude, ?) "
                "WHERE name = ?",
                (location.chain, location.city, location.country, latitude, longitude, name),
            )

    def close(self) -> None:
        self._conn.close()

    # --- media ---

    def add_medium(self, name: str, *, is_physical_place: bool) -> Medium:
        try:
            cur = self._conn.execute(
                "INSERT INTO media (name, is_physical_place) VALUES (?, ?)",
                (name, int(is_physical_place)),
            )
        except sqlite3.IntegrityError as e:
            raise StoreError(f"medium '{name}' already exists") from e
        self._conn.commit()
        # Invariant: sqlite always sets lastrowid on a successful INSERT.
        assert cur.lastrowid is not None  # nosec B101
        return Medium(id=cur.lastrowid, name=name, is_physical_place=is_physical_place)

    def list_media(self) -> list[Medium]:
        rows = self._conn.execute("SELECT id, name, is_physical_place FROM media ORDER BY name")
        return [Medium(id=r[0], name=r[1], is_physical_place=bool(r[2])) for r in rows]

    def remove_medium(self, name: str) -> None:
        row = self._conn.execute("SELECT id FROM media WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise StoreError(f"medium '{name}' does not exist")
        medium_id = row[0]
        (count,) = self._conn.execute(
            "SELECT COUNT(*) FROM entries WHERE medium_id = ?", (medium_id,)
        ).fetchone()
        if count:
            entries_word = "entry" if count == 1 else "entries"
            raise StoreError(f"medium '{name}' is referenced by {count} {entries_word}")
        self._conn.execute("DELETE FROM media WHERE id = ?", (medium_id,))
        self._conn.commit()

    def get_or_create_medium(self, name: str, *, is_physical_place: bool) -> Medium:
        existing = next((m for m in self.list_media() if m.name == name), None)
        return existing or self.add_medium(name, is_physical_place=is_physical_place)

    # --- venues ---

    def add_venue(self, name: str) -> Venue:
        # A known alias (a screen/format-suffixed name like "De Munt
        # 4DX") always resolves to its canonical venue before anything
        # else happens - never its own separate row (issue #196).
        location = KNOWN_VENUE_LOCATIONS.get(name)
        if location is not None:
            name = location.canonical_name
        chain = location.chain if location else None
        city = location.city if location else None
        country = location.country if location else None
        latitude, longitude = (location.coordinates or (None, None)) if location else (None, None)
        try:
            cur = self._conn.execute(
                "INSERT INTO venues (name, chain, city, country, latitude, longitude) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, chain, city, country, latitude, longitude),
            )
        except sqlite3.IntegrityError as e:
            raise StoreError(f"venue '{name}' already exists") from e
        self._conn.commit()
        # Invariant: sqlite always sets lastrowid on a successful INSERT.
        assert cur.lastrowid is not None  # nosec B101
        return Venue(
            id=cur.lastrowid,
            name=name,
            chain=chain,
            city=city,
            country=country,
            latitude=latitude,
            longitude=longitude,
        )

    def list_venues(self) -> list[Venue]:
        rows = self._conn.execute(
            "SELECT id, name, chain, city, country, latitude, longitude FROM venues ORDER BY name"
        )
        return [
            Venue(
                id=r[0],
                name=r[1],
                chain=r[2],
                city=r[3],
                country=r[4],
                latitude=r[5],
                longitude=r[6],
            )
            for r in rows
        ]

    def get_or_create_venue(self, name: str) -> Venue:
        # Resolve a known alias before searching, so two different
        # aliases of the same real venue both find (or both create)
        # the one canonical row, never two (issue #196).
        location = KNOWN_VENUE_LOCATIONS.get(name)
        if location is not None:
            name = location.canonical_name
        existing = next((v for v in self.list_venues() if v.name == name), None)
        return existing or self.add_venue(name)

    def remove_venue(self, name: str) -> None:
        row = self._conn.execute("SELECT id FROM venues WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise StoreError(f"venue '{name}' does not exist")
        venue_id = row[0]
        (count,) = self._conn.execute(
            "SELECT COUNT(*) FROM entries WHERE venue_id = ?", (venue_id,)
        ).fetchone()
        if count:
            entries_word = "entry" if count == 1 else "entries"
            raise StoreError(f"venue '{name}' is referenced by {count} {entries_word}")
        self._conn.execute("DELETE FROM venues WHERE id = ?", (venue_id,))
        self._conn.commit()

    def merge_venue_aliases(self, *, apply: bool = False) -> list[VenueMerge]:
        """Finds every venue row already in the database whose name is
        a known alias (a screen/format-suffixed name like "De Munt
        4DX") of another venue's canonical name - data that predates
        add_venue/get_or_create_venue's own alias resolution above
        (issue #196). `apply=False` (the default) only reports what
        would merge; `apply=True` actually reassigns the alias's
        entries to the canonical venue (creating it first if it
        doesn't exist yet) and removes the now-orphaned alias row, all
        in one transaction - either every merge in this call succeeds,
        or none of them are applied.
        """
        merges = []
        for venue in sorted(self.list_venues(), key=lambda v: v.name):
            location = KNOWN_VENUE_LOCATIONS.get(venue.name)
            if location is None or location.canonical_name == venue.name:
                continue  # not a known alias - already canonical, or unknown entirely

            (entries_moved,) = self._conn.execute(
                "SELECT COUNT(*) FROM entries WHERE venue_id = ?", (venue.id,)
            ).fetchone()
            canonical_row = self._conn.execute(
                "SELECT id FROM venues WHERE name = ?", (location.canonical_name,)
            ).fetchone()
            canonical_id = canonical_row[0] if canonical_row is not None else None

            if apply:
                if canonical_id is None:
                    # Not self.add_venue() - that commits immediately,
                    # which would break this method's own all-or-
                    # nothing guarantee for a later alias in the same
                    # call. location's chain/city/country/coordinates
                    # already apply to the canonical name too - _add()
                    # gives every alias in a group the same
                    # VenueLocation object.
                    latitude, longitude = location.coordinates or (None, None)
                    cur = self._conn.execute(
                        "INSERT INTO venues (name, chain, city, country, latitude, longitude) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            location.canonical_name,
                            location.chain,
                            location.city,
                            location.country,
                            latitude,
                            longitude,
                        ),
                    )
                    assert cur.lastrowid is not None  # nosec B101
                    canonical_id = cur.lastrowid
                self._conn.execute(
                    "UPDATE entries SET venue_id = ? WHERE venue_id = ?",
                    (canonical_id, venue.id),
                )
                self._conn.execute("DELETE FROM venues WHERE id = ?", (venue.id,))

            merges.append(
                VenueMerge(
                    alias_name=venue.name,
                    alias_venue_id=venue.id,
                    canonical_name=location.canonical_name,
                    canonical_venue_id=canonical_id,
                    entries_moved=entries_moved,
                )
            )

        if apply:
            self._conn.commit()
        return merges

    # --- entries ---

    def create_entry(
        self,
        *,
        title: str,
        date: datetime.date,
        medium_id: int,
        start_time: datetime.time | None = None,
        end_time: datetime.time | None = None,
        venue_id: int | None = None,
        row: str | None = None,
        seat: str | None = None,
    ) -> Entry:
        cur = self._conn.execute(
            "INSERT INTO entries (title, date, start_time, end_time, medium_id, venue_id, "
            "row, seat) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",  # caldav_uid is set later, once synced
            (
                title,
                date.isoformat(),
                start_time.isoformat() if start_time else None,
                end_time.isoformat() if end_time else None,
                medium_id,
                venue_id,
                row,
                seat,
            ),
        )
        # Invariant: sqlite always sets lastrowid on a successful INSERT.
        assert cur.lastrowid is not None  # nosec B101
        self._record_activity(
            action="create", entry_id=cur.lastrowid, entry_title=title, changes=None
        )
        self._conn.commit()
        return self.get_entry(cur.lastrowid)

    def get_entry(self, entry_id: int) -> Entry:
        row = self._conn.execute(
            # _ENTRY_COLUMNS is a fixed internal tuple, never user input; the value is parameterized below
            f"SELECT {', '.join(_ENTRY_COLUMNS)} FROM entries WHERE id = ?",  # nosec B608
            (entry_id,),
        ).fetchone()
        if row is None:
            raise StoreError(f"no entry with id {entry_id}")
        return _row_to_entry(row)

    def list_entries(
        self,
        *,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        medium_id: int | None = None,
        venue_ids: list[int] | None = None,
    ) -> list[Entry]:
        # _ENTRY_COLUMNS is a fixed internal tuple, never user input; every filter value below is parameterized
        query = f"SELECT {', '.join(_ENTRY_COLUMNS)} FROM entries"  # nosec B608
        clauses = []
        params: list[object] = []
        if date_from is not None:
            clauses.append("date >= ?")
            params.append(date_from.isoformat())
        if date_to is not None:
            clauses.append("date <= ?")
            params.append(date_to.isoformat())
        if medium_id is not None:
            clauses.append("medium_id = ?")
            params.append(medium_id)
        if venue_ids is not None:
            clauses.append(f"venue_id IN ({', '.join('?' * len(venue_ids))})")
            params.extend(venue_ids)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY date"
        rows = self._conn.execute(query, params)
        return [_row_to_entry(r) for r in rows]

    def update_entry(
        self,
        entry_id: int,
        *,
        title: str = _UNSET,
        date: datetime.date = _UNSET,
        start_time: datetime.time | None = _UNSET,
        end_time: datetime.time | None = _UNSET,
        medium_id: int = _UNSET,
        venue_id: int | None = _UNSET,
        caldav_uid: str | None = _UNSET,
        imdb_rating: str | None = _UNSET,
        rotten_tomatoes_rating: str | None = _UNSET,
        metacritic_rating: str | None = _UNSET,
        letterboxd_url: str | None = _UNSET,
        letterboxd_rating: str | None = _UNSET,
        imdb_url: str | None = _UNSET,
        booking_ref: str | None = _UNSET,
        notes: str | None = _UNSET,
        poster_url: str | None = _UNSET,
        director: str | None = _UNSET,
        actors: str | None = _UNSET,
        genre: str | None = _UNSET,
        release_year: int | None = _UNSET,
        source: str | None = _UNSET,
        row: str | None = _UNSET,
        seat: str | None = _UNSET,
        rated: str | None = _UNSET,
        released: str | None = _UNSET,
        runtime: str | None = _UNSET,
        writer: str | None = _UNSET,
        plot: str | None = _UNSET,
        language: str | None = _UNSET,
        country: str | None = _UNSET,
        awards: str | None = _UNSET,
        metascore: str | None = _UNSET,
        imdb_votes: str | None = _UNSET,
        dvd: str | None = _UNSET,
        box_office: str | None = _UNSET,
        production: str | None = _UNSET,
        website: str | None = _UNSET,
        trailer_url: str | None = _UNSET,
        omdb_last_no_match: datetime.date | None = _UNSET,
    ) -> Entry:
        current = self.get_entry(entry_id)
        changes = {
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "medium_id": medium_id,
            "venue_id": venue_id,
            "caldav_uid": caldav_uid,
            "imdb_rating": imdb_rating,
            "rotten_tomatoes_rating": rotten_tomatoes_rating,
            "metacritic_rating": metacritic_rating,
            "letterboxd_url": letterboxd_url,
            "letterboxd_rating": letterboxd_rating,
            "imdb_url": imdb_url,
            "booking_ref": booking_ref,
            "notes": notes,
            "poster_url": poster_url,
            "director": director,
            "actors": actors,
            "genre": genre,
            "release_year": release_year,
            "source": source,
            "row": row,
            "seat": seat,
            "rated": rated,
            "released": released,
            "runtime": runtime,
            "writer": writer,
            "plot": plot,
            "language": language,
            "country": country,
            "awards": awards,
            "metascore": metascore,
            "imdb_votes": imdb_votes,
            "dvd": dvd,
            "box_office": box_office,
            "production": production,
            "website": website,
            "trailer_url": trailer_url,
            "omdb_last_no_match": omdb_last_no_match,
        }
        # changes is a heterogeneous dict by design (the _UNSET-sentinel
        # pattern needs one dict covering every field) - mypy can't verify
        # dataclasses.replace's **kwargs against that without a per-field
        # TypedDict, which isn't worth the ceremony for one call site.
        updated = replace(
            current,
            **{k: v for k, v in changes.items() if v is not _UNSET},  # type: ignore[arg-type]
        )
        columns = _ENTRY_COLUMNS[1:]  # everything but id
        set_clause = ", ".join(f"{column}=?" for column in columns)
        values = [_serialize_entry_field(column, getattr(updated, column)) for column in columns]
        self._conn.execute(
            # set_clause is built purely from _ENTRY_COLUMNS, never user input; every value is parameterized
            f"UPDATE entries SET {set_clause} WHERE id=?",  # nosec B608
            (*values, entry_id),
        )
        # Only fields whose serialized value actually differs - a caller
        # passing the same value it already had (update_entry(id,
        # title="Dune") on an entry already titled "Dune") isn't a real
        # change, and shouldn't read as one in the activity log.
        field_diff = {
            field: (
                _serialize_entry_field(field, getattr(current, field)),
                _serialize_entry_field(field, getattr(updated, field)),
            )
            for field, passed in changes.items()
            if passed is not _UNSET
            and _serialize_entry_field(field, getattr(current, field))
            != _serialize_entry_field(field, getattr(updated, field))
        }
        if field_diff:
            self._record_activity(
                action="update",
                entry_id=entry_id,
                entry_title=updated.title,
                changes=field_diff,
            )
        self._conn.commit()
        return self.get_entry(entry_id)

    def get_entry_by_booking_ref(self, booking_ref: str) -> Entry | None:
        row = self._conn.execute(
            # _ENTRY_COLUMNS is a fixed internal tuple, never user input; the value is parameterized below
            f"SELECT {', '.join(_ENTRY_COLUMNS)} FROM entries WHERE booking_ref = ?",  # nosec B608
            (booking_ref,),
        ).fetchone()
        return _row_to_entry(row) if row else None

    def delete_entry(self, entry_id: int) -> None:
        # Fetched first so there's still a title to record once the row is
        # gone (issue #276) - also gives the "no entry with id" error for
        # a nonexistent id, same message as before, just raised before
        # the now-unnecessary DELETE rather than after it.
        entry = self.get_entry(entry_id)
        self._conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self._record_activity(
            action="delete", entry_id=entry_id, entry_title=entry.title, changes=None
        )
        self._conn.commit()

    def _record_activity(
        self,
        *,
        action: str,
        entry_id: int,
        entry_title: str,
        changes: dict[str, tuple[object, object]] | None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO activity_log (action, entry_id, entry_title, changes, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                action,
                entry_id,
                entry_title,
                json.dumps(changes) if changes is not None else None,
                datetime.datetime.now(datetime.UTC).isoformat(),
            ),
        )

    def list_activity(self) -> list[ActivityLogEntry]:
        rows = self._conn.execute(
            "SELECT id, action, entry_id, entry_title, changes, created_at FROM activity_log "
            "ORDER BY created_at DESC, id DESC"
        )
        return [
            ActivityLogEntry(
                id=r[0],
                action=r[1],
                entry_id=r[2],
                entry_title=r[3],
                changes={k: tuple(v) for k, v in json.loads(r[4]).items()} if r[4] else None,
                created_at=datetime.datetime.fromisoformat(r[5]),
            )
            for r in rows
        ]

    def record_import_failure(self, *, source: str, row_number: int, error: str) -> ImportFailure:
        created_at = datetime.datetime.now(datetime.UTC).isoformat()
        cur = self._conn.execute(
            "INSERT INTO import_failures (source, row_number, error, created_at) "
            "VALUES (?, ?, ?, ?)",
            (source, row_number, error, created_at),
        )
        self._conn.commit()
        # Invariant: sqlite always sets lastrowid on a successful INSERT.
        assert cur.lastrowid is not None  # nosec B101
        return ImportFailure(
            id=cur.lastrowid,
            source=source,
            row_number=row_number,
            error=error,
            created_at=datetime.datetime.fromisoformat(created_at),
        )

    def list_import_failures(self) -> list[ImportFailure]:
        rows = self._conn.execute(
            "SELECT id, source, row_number, error, created_at FROM import_failures "
            "ORDER BY created_at DESC"
        )
        return [
            ImportFailure(
                id=r[0],
                source=r[1],
                row_number=r[2],
                error=r[3],
                created_at=datetime.datetime.fromisoformat(r[4]),
            )
            for r in rows
        ]

    def clear_import_failures(self) -> int:
        cur = self._conn.execute("DELETE FROM import_failures")
        self._conn.commit()
        return cur.rowcount
