"""Bulk import from CSV and JSON. Every format parses to the same
ImportRow, and run_import applies the same validation and
duplicate-detection rules used by interactive logging.
"""

import csv
import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

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
    row: str | None = None
    seat: str | None = None
    # The web app's export writes the calendar event's uid and, for a viewing
    # the CLI logged, a blank medium (no X-MEDIUM was ever written). Such a row
    # is a re-import of something already stored, so a blank medium is only
    # an error once it turns out not to be a duplicate.
    uid: str | None = None


@dataclass(frozen=True)
class ParsedRow:
    """The result of parsing one input row: either `entry` is populated
    and `error` is None, or the reverse - never both.
    """

    row_number: int
    entry: ImportRow | None
    error: str | None
    # Why a row that parsed fine is left out on purpose (an IMDb series, say).
    # It is reported as skipped, not failed, and `entry` and `error` are None.
    skipped: str | None = None


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
    # (row number, error) for rows that parsed but still failed once checked
    # against the store. The caller records these beside the parse-time ones.
    run_failures: list[tuple[int, str]] = field(default_factory=list)


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
        uid = raw.get("uid") or None
        medium = raw.get("medium") or None
        if not medium and not uid:
            raise ValueError("medium is required")
        entry = ImportRow(
            title=title,
            date=datetime.date.fromisoformat(raw["date"]),
            medium=medium or "",
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
            row=raw.get("row") or None,
            seat=raw.get("seat") or None,
            uid=uid,
        )
    except (KeyError, ValueError) as e:
        return ParsedRow(row_number=row_number, entry=None, error=str(e))
    return ParsedRow(row_number=row_number, entry=entry, error=None)


def parse_json_text(text: str) -> list[ParsedRow]:
    """Parses JSON already in memory - a `movies.json`-shaped array, or a
    single bare row object (treated as a one-element array), the shape
    a caller piping one row at a time naturally produces. Shared by
    `parse_json` (a file) and `import`'s stdin path (no file at all).
    """
    data = json.loads(text)
    rows = [data] if isinstance(data, dict) else data
    return [_row_from_dict(i, raw) for i, raw in enumerate(rows, start=1)]


class MediumRequiredError(ValueError):
    """The file can't say where it was watched, and no `--medium` was given."""


_LETTERBOXD_DIARY_HEADERS = frozenset({"Name", "Letterboxd URI", "Watched Date"})
_IMDB_RATINGS_HEADERS = frozenset({"Const", "Title", "Your Rating", "Date Rated"})
_DIARY_NEEDS_MEDIUM = (
    "This looks like a Letterboxd diary, which doesn't say where you watched. "
    "Pass --medium, for example --medium netflix."
)
_IMDB_NEEDS_MEDIUM = (
    "This looks like an IMDb ratings export, which doesn't say where you watched. "
    "Pass --medium, for example --medium cinema."
)

# IMDb's ratings.csv also lists series, episodes and games. It spells the
# `Title Type` as a code ("tvMiniSeries") in some exports and as a display name
# ("TV Mini Series") in others, so the type is compared lowercased with spaces,
# dashes and underscores removed. Only these known non-films are skipped, per
# row; any other type, or none, is read as a film, so an unfamiliar one never
# blocks a whole file.
_IMDB_NOT_FILM = {
    "tvseries": "a TV series",
    "tvminiseries": "a TV miniseries",
    "tvepisode": "a TV episode",
    "videogame": "a video game",
    "podcastseries": "a podcast",
    "podcastepisode": "a podcast episode",
    "musicvideo": "a music video",
}


def _letterboxd_record(raw: dict[str, Any], medium: str) -> dict[str, Any]:
    # `Date` is the day the film was logged; `Watched Date` is the day it was
    # seen, and the one that belongs on the calendar.
    tags = (raw.get("Tags") or "").strip()
    return {
        "title": raw.get("Name"),
        "date": raw.get("Watched Date"),
        "medium": medium,
        "release_year": raw.get("Year"),
        "letterboxd_url": raw.get("Letterboxd URI"),
        "letterboxd_rating": raw.get("Rating"),
        "notes": f"Tags: {tags}" if tags else None,
    }


def _imdb_not_a_film(raw: dict[str, Any]) -> str | None:
    kind = re.sub(r"[\s_-]", "", raw.get("Title Type") or "").lower()
    name = _IMDB_NOT_FILM.get(kind)
    if name is None:
        return None
    return f'"{(raw.get("Title") or "").strip()}" is {name} on IMDb, not a movie'


def _imdb_record(raw: dict[str, Any], medium: str) -> dict[str, Any]:
    # IMDb keeps no watched date; the day a title was rated is the closest.
    rating = (raw.get("Your Rating") or "").strip()
    return {
        "title": raw.get("Title"),
        "date": raw.get("Date Rated"),
        "medium": medium,
        "release_year": raw.get("Year"),
        "genre": raw.get("Genres"),
        "director": raw.get("Directors"),
        "imdb_url": raw.get("URL"),
        "imdb_rating": raw.get("IMDb Rating"),
        "notes": f"Your IMDb rating: {rating}/10" if rating else None,
    }


def parse_csv(path: Path, medium: str | None = None) -> list[ParsedRow]:
    """A native `movies.csv`, a Letterboxd `diary.csv` or an IMDb
    `ratings.csv`, told apart by their headers. The last two name no medium,
    so `medium` is required for them and ignored for a native file, which has
    its own column.
    """
    # utf-8-sig drops a byte-order mark so it can't hide the first header.
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip() for name in reader.fieldnames or []]
        headers = set(reader.fieldnames)
        wanted = (medium or "").strip()
        # Row 1 is the header, so the first data row is 2.
        if headers >= _LETTERBOXD_DIARY_HEADERS:
            if not wanted:
                raise MediumRequiredError(_DIARY_NEEDS_MEDIUM)
            return [
                _row_from_dict(i, _letterboxd_record(raw, wanted))
                for i, raw in enumerate(reader, start=2)
            ]
        if headers >= _IMDB_RATINGS_HEADERS:
            if not wanted:
                raise MediumRequiredError(_IMDB_NEEDS_MEDIUM)
            return [
                _skipped_row(i, reason)
                if (reason := _imdb_not_a_film(raw))
                else _row_from_dict(i, _imdb_record(raw, wanted))
                for i, raw in enumerate(reader, start=2)
            ]
        return [_row_from_dict(i, raw) for i, raw in enumerate(reader, start=2)]


def _skipped_row(row_number: int, reason: str) -> ParsedRow:
    return ParsedRow(row_number=row_number, entry=None, error=None, skipped=reason)


def parse_json(path: Path, medium: str | None = None) -> list[ParsedRow]:
    return parse_json_text(path.read_text(encoding="utf-8"))


class Parser(Protocol):
    """`medium` is the `--medium` flag, for a format that doesn't carry one."""

    def __call__(self, path: Path, medium: str | None = None) -> list[ParsedRow]: ...


@dataclass(frozen=True)
class ImportFormat:
    """One bulk-import format `movie-planner import` can read - a name
    (also the source movie-planner#257 will eventually stamp on the
    calendar as provenance) and a parser from a file path to rows.

    Adding a new format (issue #252) means writing one function
    matching `parse`'s shape and registering it in IMPORT_FORMATS below
    - see CONTRIBUTING.md's "Adding a new import format". `cli.py`
    never branches on a specific format; it only ever consults this
    registry, the same way `mail_import`'s IMAP/mbox/Maildir sources
    are adapters behind `MailClient` rather than hardcoded branches.
    """

    name: str
    parse: Parser


IMPORT_FORMATS: dict[str, ImportFormat] = {
    ".csv": ImportFormat(name="csv", parse=parse_csv),
    ".json": ImportFormat(name="json", parse=parse_json),
}


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
    run_failures: list[tuple[int, str]] = []
    imported_entries: list[ImportedEntry] = []

    for row in rows:
        if row.skipped is not None:
            skipped += 1
            skipped_details.append(f"row {row.row_number}: {row.skipped}")
            continue
        if row.error is not None:
            failed += 1
            failed_details.append(f"row {row.row_number}: {row.error}")
            continue

        # Invariant: error is None here.
        assert row.entry is not None  # nosec B101
        r = row.entry
        duplicate = find_duplicate(
            r.title,
            r.date,
            existing,
            threshold=threshold,
            start_time=r.start_time,
            end_time=r.end_time,
        )
        if duplicate is not None and not force:
            skipped += 1
            skipped_details.append(
                f"row {row.row_number}: '{r.title}' looks like a duplicate of "
                f"'{duplicate.title}' logged {duplicate.date}"
            )
            continue

        if not r.medium:
            failed += 1
            failed_details.append(f"row {row.row_number}: medium is required")
            run_failures.append((row.row_number, "medium is required"))
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
            "row": r.row,
            "seat": r.seat,
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
        run_failures=run_failures,
    )
