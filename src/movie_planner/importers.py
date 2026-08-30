"""Bulk import from CSV, JSON, and the existing org-mode log format. Every
format parses to the same ImportRow, and run_import applies the same
validation and duplicate-detection rules used by interactive logging.
"""

import csv
import datetime
import json
import re
from dataclasses import dataclass
from pathlib import Path

import orgparse

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


@dataclass(frozen=True)
class ParsedRow:
    """The result of parsing one input row: either `entry` is populated
    and `error` is None, or the reverse - never both.
    """

    row_number: int
    entry: ImportRow | None
    error: str | None


@dataclass(frozen=True)
class ImportSummary:
    imported: int
    skipped_duplicates: int
    failed: int
    skipped_details: list[str]
    failed_details: list[str]


def _parse_time(value: str | None) -> datetime.time | None:
    return datetime.time.fromisoformat(value) if value else None


def _row_from_dict(row_number: int, raw: dict) -> ParsedRow:
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


def _org_node_to_row(row_number: int, node: object) -> ParsedRow:
    try:
        timestamp = node.rangelist[0] if node.rangelist else node.datelist[0]
        start = timestamp.start
        end = getattr(timestamp, "end", None)
        if isinstance(start, datetime.datetime):
            entry_date = start.date()
            start_time = start.time()
            end_time = end.time() if end else None
        else:
            entry_date = start
            start_time = None
            end_time = None

        medium_tags = node.parent.shallow_tags if node.parent is not None else set()
        if len(medium_tags) != 1:
            raise ValueError(f"cannot tell the medium from heading tags {sorted(medium_tags)!r}")
        medium = next(iter(medium_tags))

        venue = node.properties.get("CINEMA")
        if venue is None:
            # A second :PROPERTIES: drawer after the timestamp - orgparse
            # only parses the first one into `.properties`; the rest is
            # left as raw text in `.body`. Recover it from there.
            match = re.search(r"^:CINEMA:\s*(.+?)\s*$", node.body, re.MULTILINE)
            venue = match.group(1) if match else None

        entry = ImportRow(
            title=node.heading,
            date=entry_date,
            medium=medium,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            imdb_url=node.properties.get("IMDB"),
        )
    except (ValueError, AttributeError, IndexError) as e:
        return ParsedRow(row_number=row_number, entry=None, error=str(e))
    return ParsedRow(row_number=row_number, entry=entry, error=None)


def parse_org(path: Path) -> list[ParsedRow]:
    root = orgparse.load(str(path))
    rows = []
    row_number = 0
    for node in root[1:]:
        if not (node.rangelist or node.datelist):
            continue  # a structural heading (e.g. "Cinema"), not a movie
        row_number += 1
        rows.append(_org_node_to_row(row_number, node))
    return rows


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

    for row in rows:
        if row.error is not None:
            failed += 1
            failed_details.append(f"row {row.row_number}: {row.error}")
            continue

        assert row.entry is not None
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
        if r.imdb_url:
            entry = store.update_entry(entry.id, imdb_url=r.imdb_url)
        existing.append(entry)
        imported += 1

    return ImportSummary(
        imported=imported,
        skipped_duplicates=skipped,
        failed=failed,
        skipped_details=skipped_details,
        failed_details=failed_details,
    )
