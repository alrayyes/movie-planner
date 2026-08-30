"""The local SQLite store: media, venues, and entries. This is the source
of truth - see design.md's "Source of truth" decision. The calendar is a
synced mirror, never read back from.
"""

import datetime
import sqlite3
from dataclasses import dataclass
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
    caldav_uid TEXT
);
"""


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
    start_time: datetime.time | None
    end_time: datetime.time | None
    medium_id: int
    venue_id: int | None
    caldav_uid: str | None


def _row_to_entry(row: tuple) -> Entry:
    entry_id, title, date_str, start_str, end_str, medium_id, venue_id, caldav_uid = row
    return Entry(
        id=entry_id,
        title=title,
        date=datetime.date.fromisoformat(date_str),
        start_time=datetime.time.fromisoformat(start_str) if start_str else None,
        end_time=datetime.time.fromisoformat(end_str) if end_str else None,
        medium_id=medium_id,
        venue_id=venue_id,
        caldav_uid=caldav_uid,
    )


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        # ALTER TABLE ADD COLUMN, guarded, for a database created before
        # this column existed - CREATE TABLE IF NOT EXISTS above only
        # covers a brand-new database.
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(entries)")}
        if "caldav_uid" not in columns:
            self._conn.execute("ALTER TABLE entries ADD COLUMN caldav_uid TEXT")

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
        assert cur.lastrowid is not None
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

    # --- venues ---

    def add_venue(self, name: str) -> Venue:
        try:
            cur = self._conn.execute("INSERT INTO venues (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError as e:
            raise StoreError(f"venue '{name}' already exists") from e
        self._conn.commit()
        assert cur.lastrowid is not None
        return Venue(id=cur.lastrowid, name=name)

    def list_venues(self) -> list[Venue]:
        rows = self._conn.execute("SELECT id, name FROM venues ORDER BY name")
        return [Venue(id=r[0], name=r[1]) for r in rows]

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
        assert cur.lastrowid is not None
        return self.get_entry(cur.lastrowid)

    def get_entry(self, entry_id: int) -> Entry:
        row = self._conn.execute(
            "SELECT id, title, date, start_time, end_time, medium_id, venue_id, caldav_uid "
            "FROM entries WHERE id = ?",
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
        query = (
            "SELECT id, title, date, start_time, end_time, medium_id, venue_id, caldav_uid "
            "FROM entries"
        )
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
    ) -> Entry:
        current = self.get_entry(entry_id)
        new_title = current.title if title is _UNSET else title
        new_date = current.date if date is _UNSET else date
        new_start = current.start_time if start_time is _UNSET else start_time
        new_end = current.end_time if end_time is _UNSET else end_time
        new_medium = current.medium_id if medium_id is _UNSET else medium_id
        new_venue = current.venue_id if venue_id is _UNSET else venue_id
        new_caldav_uid = current.caldav_uid if caldav_uid is _UNSET else caldav_uid
        self._conn.execute(
            "UPDATE entries SET title=?, date=?, start_time=?, end_time=?, "
            "medium_id=?, venue_id=?, caldav_uid=? WHERE id=?",
            (
                new_title,
                new_date.isoformat(),
                new_start.isoformat() if new_start else None,
                new_end.isoformat() if new_end else None,
                new_medium,
                new_venue,
                new_caldav_uid,
                entry_id,
            ),
        )
        self._conn.commit()
        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: int) -> None:
        cur = self._conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self._conn.commit()
        if cur.rowcount == 0:
            raise StoreError(f"no entry with id {entry_id}")
