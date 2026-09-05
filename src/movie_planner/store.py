"""The local SQLite store: media, venues, and entries. This is the source
of truth - see design.md's "Source of truth" decision. The calendar is a
synced mirror, never read back from.
"""

import datetime
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

_UNSET: Any = object()

SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_physical_place INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
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
    notes TEXT
);
"""

# Columns added to `entries` after its initial release, ALTERed in for a
# database created before each one existed - CREATE TABLE IF NOT EXISTS
# above only covers a brand-new database.
_MIGRATED_COLUMNS = (
    "caldav_uid",
    "imdb_rating",
    "rotten_tomatoes_rating",
    "metacritic_rating",
    "letterboxd_url",
    "letterboxd_rating",
    "imdb_url",
    "booking_ref",
    "notes",
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
    )


def _serialize_entry_field(name: str, value: object) -> object:
    if name == "date" and isinstance(value, datetime.date):
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
        for column in _MIGRATED_COLUMNS:
            if column not in columns:
                self._conn.execute(f"ALTER TABLE entries ADD COLUMN {column} TEXT")
        # Not UNIQUE: Pathé's own uniqueness guarantee for booking numbers
        # is unconfirmed - a plain index plus the caller's own confirmation
        # step is the safety net instead of a write that can fail outright.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entries_booking_ref ON entries(booking_ref)"
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
        try:
            cur = self._conn.execute("INSERT INTO venues (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError as e:
            raise StoreError(f"venue '{name}' already exists") from e
        self._conn.commit()
        # Invariant: sqlite always sets lastrowid on a successful INSERT.
        assert cur.lastrowid is not None  # nosec B101
        return Venue(id=cur.lastrowid, name=name)

    def list_venues(self) -> list[Venue]:
        rows = self._conn.execute("SELECT id, name FROM venues ORDER BY name")
        return [Venue(id=r[0], name=r[1]) for r in rows]

    def get_or_create_venue(self, name: str) -> Venue:
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
    ) -> Entry:
        cur = self._conn.execute(
            "INSERT INTO entries (title, date, start_time, end_time, medium_id, venue_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",  # caldav_uid is set later, once synced
            (
                title,
                date.isoformat(),
                start_time.isoformat() if start_time else None,
                end_time.isoformat() if end_time else None,
                medium_id,
                venue_id,
            ),
        )
        self._conn.commit()
        # Invariant: sqlite always sets lastrowid on a successful INSERT.
        assert cur.lastrowid is not None  # nosec B101
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
        cur = self._conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self._conn.commit()
        if cur.rowcount == 0:
            raise StoreError(f"no entry with id {entry_id}")
