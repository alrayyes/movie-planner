"""Bulk import from CSV and JSON. Every format parses to the same
ImportRow, and run_import applies the same validation and
duplicate-detection rules used by interactive logging.
"""

import csv
import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from movie_planner.duplicates import find_duplicate
from movie_planner.store import Entry, Store


@dataclass(frozen=True)
class ImportRow:
    title: str
    date: datetime.date
    medium: str
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    venue: str | None = None
    imdb_url: str | None = None
    notes: str | None = None
    imdb_rating: str | None = None
    rotten_tomatoes_rating: str | None = None
    metacritic_rating: str | None = None
    poster_url: str | None = None
    director: str | None = None
    actors: str | None = None
    genre: str | None = None
    release_year: int | None = None
    letterboxd_url: str | None = None
    letterboxd_rating: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class ParsedRow:
    """The result of parsing one input row: either `entry` is populated
    and `error` is None, or the reverse - never both.
    """

    row_number: int
    entry: ImportRow | None
    error: str | None


@dataclass(frozen=True)
class ImportedEntry:
    """An entry created by `run_import`. The calendar sync push looks up
    the venue (chain, city, country included) straight from `entry.venue_id`
    itself, so nothing extra needs to travel alongside it here.
    """

    entry: Entry


@dataclass(frozen=True)
class ImportSummary:
    imported: int
    skipped_duplicates: int
    failed: int
    skipped_details: list[str]
    failed_details: list[str]
    imported_entries: list[ImportedEntry]


def _parse_time(value: str | None) -> datetime.time | None:
    return datetime.time.fromisoformat(value) if value else None


def _parse_release_year(value: object) -> int | None:
    # CSV always hands this in as a string; JSON can hand in a plain int too.
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value != "":
        return int(value)
    return None


def _row_from_dict(row_number: int, raw: dict[str, Any]) -> ParsedRow:
    # A parsed CSV/JSON row is dynamically typed - Any is the honest
    # boundary here; the try/except below is what actually validates it.
    try:
        title = raw.get("title") or None
        if not title:
            raise ValueError("title is required")
        medium = raw.get("medium") or None
        if not medium:
            raise ValueError("medium is required")
        entry = ImportRow(
            title=title,
            date=datetime.date.fromisoformat(raw["date"]),
            medium=medium,
            start_time=_parse_time(raw.get("start_time")),
            end_time=_parse_time(raw.get("end_time")),
            venue=raw.get("venue") or None,
            imdb_url=raw.get("imdb_url") or None,
            notes=raw.get("notes") or None,
            imdb_rating=raw.get("imdb_rating") or None,
            rotten_tomatoes_rating=raw.get("rotten_tomatoes_rating") or None,
            metacritic_rating=raw.get("metacritic_rating") or None,
            poster_url=raw.get("poster_url") or None,
            director=raw.get("director") or None,
            actors=raw.get("actors") or None,
            genre=raw.get("genre") or None,
            release_year=_parse_release_year(raw.get("release_year")),
            letterboxd_url=raw.get("letterboxd_url") or None,
            letterboxd_rating=raw.get("letterboxd_rating") or None,
            source=raw.get("source") or None,
        )
    except (KeyError, ValueError) as e:
        return ParsedRow(row_number=row_number, entry=None, error=str(e))
    return ParsedRow(row_number=row_number, entry=entry, error=None)


def parse_csv(path: Path) -> list[ParsedRow]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Row 1 is the header, so the first data row is 2.
        return [_row_from_dict(i, raw) for i, raw in enumerate(reader, start=2)]


def parse_json(path: Path) -> list[ParsedRow]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [_row_from_dict(i, raw) for i, raw in enumerate(data, start=1)]


def run_import(
    store: Store,
    rows: list[ParsedRow],
    *,
    threshold: float = 90.0,
    force: bool = False,
) -> ImportSummary:
    existing: list[Entry] = store.list_entries()
    imported = 0
    skipped = 0
    failed = 0
    skipped_details = []
    failed_details = []
    imported_entries: list[ImportedEntry] = []

    for row in rows:
        if row.error is not None:
            failed += 1
            failed_details.append(f"row {row.row_number}: {row.error}")
            continue

        # Invariant: error is None here.
        assert row.entry is not None  # nosec B101
        r = row.entry
        duplicate = find_duplicate(r.title, r.date, existing, threshold=threshold)
        if duplicate is not None and not force:
            skipped += 1
            skipped_details.append(
                f"row {row.row_number}: '{r.title}' looks like a duplicate of "
                f"'{duplicate.title}' logged {duplicate.date}"
            )
            continue

        medium = store.get_or_create_medium(r.medium, is_physical_place=r.venue is not None)
        venue = store.get_or_create_venue(r.venue) if r.venue else None
        entry = store.create_entry(
            title=r.title,
            date=r.date,
            medium_id=medium.id,
            start_time=r.start_time,
            end_time=r.end_time,
            venue_id=venue.id if venue else None,
        )
        supplied_fields: dict[str, object] = {
            "imdb_url": r.imdb_url,
            "notes": r.notes,
            "imdb_rating": r.imdb_rating,
            "rotten_tomatoes_rating": r.rotten_tomatoes_rating,
            "metacritic_rating": r.metacritic_rating,
            "poster_url": r.poster_url,
            "director": r.director,
            "actors": r.actors,
            "genre": r.genre,
            "release_year": r.release_year,
            "letterboxd_url": r.letterboxd_url,
            "letterboxd_rating": r.letterboxd_rating,
            "source": r.source,
        }
        supplied_fields = {k: v for k, v in supplied_fields.items() if v is not None}
        if supplied_fields:
            # supplied_fields is a heterogeneous dict by design (only the
            # fields this row actually supplied) - mypy can't verify
            # update_entry's **kwargs against that without a per-field
            # TypedDict, which isn't worth the ceremony for one call site.
            entry = store.update_entry(entry.id, **supplied_fields)  # type: ignore[arg-type]
        existing.append(entry)
        imported_entries.append(ImportedEntry(entry=entry))
        imported += 1

    return ImportSummary(
        imported=imported,
        skipped_duplicates=skipped,
        failed=failed,
        skipped_details=skipped_details,
        failed_details=failed_details,
        imported_entries=imported_entries,
    )
