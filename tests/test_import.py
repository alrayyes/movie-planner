from collections.abc import Iterator
from datetime import date, time
from pathlib import Path

import pytest

from movie_planner.importers import (
    ImportRow,
    ParsedRow,
    parse_csv,
    parse_json,
    parse_org,
    run_import,
)
from movie_planner.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "movies.db")
    yield s
    s.close()


# --- parse_csv: task 6.1 ---


def test_parse_csv_full_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text(
        "title,date,start_time,end_time,medium,venue,imdb_url\n"
        "The Clockmaker's Daughter,2026-01-03,14:00,16:32,cinema,Grand Vista Cinema,https://www.imdb.com/title/tt27543632/\n"
    )

    rows = parse_csv(csv_path)

    assert len(rows) == 1
    assert rows[0].error is None
    entry = rows[0].entry
    assert entry == ImportRow(
        title="The Clockmaker's Daughter",
        date=date(2026, 1, 3),
        medium="cinema",
        start_time=time(14, 0),
        end_time=time(16, 32),
        venue="Grand Vista Cinema",
        imdb_url="https://www.imdb.com/title/tt27543632/",
    )


def test_parse_csv_optional_fields_blank(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text(
        "title,date,start_time,end_time,medium,venue,imdb_url\n"
        "A Netflix Show,2026-01-01,,,netflix,,\n"
    )

    rows = parse_csv(csv_path)

    entry = rows[0].entry
    assert entry.start_time is None
    assert entry.end_time is None
    assert entry.venue is None
    assert entry.imdb_url is None


def test_parse_csv_missing_title_is_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\n,2026-01-01,cinema\n")

    rows = parse_csv(csv_path)

    assert rows[0].entry is None
    assert rows[0].error is not None
    assert rows[0].row_number == 2


def test_parse_csv_bad_date_is_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,not-a-date,cinema\n")

    rows = parse_csv(csv_path)

    assert rows[0].entry is None
    assert rows[0].error is not None


# --- parse_json: task 6.2 ---


def test_parse_json_full_row(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_text(
        """
        [
            {
                "title": "Dune",
                "date": "2026-01-01",
                "start_time": "19:00",
                "end_time": "21:35",
                "medium": "cinema",
                "venue": "Starlight Cinema",
                "imdb_url": "https://www.imdb.com/title/tt1160419/"
            }
        ]
        """
    )

    rows = parse_json(json_path)

    assert rows[0].entry == ImportRow(
        title="Dune",
        date=date(2026, 1, 1),
        medium="cinema",
        start_time=time(19, 0),
        end_time=time(21, 35),
        venue="Starlight Cinema",
        imdb_url="https://www.imdb.com/title/tt1160419/",
    )


def test_parse_json_missing_optional_keys(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_text('[{"title": "A show", "date": "2026-01-01", "medium": "netflix"}]')

    rows = parse_json(json_path)

    entry = rows[0].entry
    assert entry.start_time is None
    assert entry.venue is None


def test_parse_json_missing_medium_is_a_failed_row(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_text('[{"title": "Dune", "date": "2026-01-01"}]')

    rows = parse_json(json_path)

    assert rows[0].entry is None
    assert rows[0].error is not None


# --- parse_org: task 6.3 ---

ORG_SAMPLE = """#+TITLE: Movies

* Movies :movies:2026:
** Cinema :cinema:
*** The Clockmaker's Daughter
:PROPERTIES:
:CINEMA:   Grand Vista Cinema
:IMDB:     https://www.imdb.com/title/tt27543632/
:END:
<2026-01-03 Sat 14:00-16:32>
*** Midnight Ferry: Part Two - Movies
:PROPERTIES:
:IMDB:     https://www.imdb.com/title/tt33978029/
:END:
<2026-03-29 Sun 12:20-14:27>
:PROPERTIES:
:CINEMA:   Starlight Cinema
:END:
*** Solstice Run
<2026-05-19 Tue 16:10>
:PROPERTIES:
:IMDB:     https://www.imdb.com/title/tt17490712/
:CINEMA:   Riverside Multiplex
:END:
** Netflix :netflix:
*** Paper Constellations - Movies
<2026-03-14 Sat>
:PROPERTIES:
:IMDB:     https://www.imdb.com/title/tt39792948/
:END:
"""


def _org_file(tmp_path: Path) -> Path:
    path = tmp_path / "movies.org"
    path.write_text(ORG_SAMPLE)
    return path


def test_parse_org_full_range_entry(tmp_path: Path) -> None:
    rows = parse_org(_org_file(tmp_path))

    housemaid = next(r for r in rows if r.entry and r.entry.title == "The Clockmaker's Daughter")
    assert housemaid.entry == ImportRow(
        title="The Clockmaker's Daughter",
        date=date(2026, 1, 3),
        medium="cinema",
        start_time=time(14, 0),
        end_time=time(16, 32),
        venue="Grand Vista Cinema",
        imdb_url="https://www.imdb.com/title/tt27543632/",
    )


def test_parse_org_start_only_entry(tmp_path: Path) -> None:
    rows = parse_org(_org_file(tmp_path))

    mk2 = next(r for r in rows if r.entry and r.entry.title == "Solstice Run")
    assert mk2.entry.start_time == time(16, 10)
    assert mk2.entry.end_time is None
    assert mk2.entry.venue == "Riverside Multiplex"


def test_parse_org_date_only_entry_from_netflix_medium(tmp_path: Path) -> None:
    rows = parse_org(_org_file(tmp_path))

    louis = next(r for r in rows if r.entry and "Paper Constellations" in r.entry.title)
    assert louis.entry.date == date(2026, 3, 14)
    assert louis.entry.start_time is None
    assert louis.entry.medium == "netflix"
    assert louis.entry.venue is None


def test_parse_org_recovers_venue_from_duplicate_properties_drawer(tmp_path: Path) -> None:
    """The real log has an entry with two :PROPERTIES: drawers - one before
    the timestamp, one after. orgparse only parses the first into
    `.properties`; the second is left as raw text in `.body`.
    """
    rows = parse_org(_org_file(tmp_path))

    rrn2 = next(r for r in rows if r.entry and "Midnight Ferry: Part Two" in r.entry.title)
    assert rrn2.entry.venue == "Starlight Cinema"
    assert rrn2.entry.imdb_url == "https://www.imdb.com/title/tt33978029/"


def test_parse_org_produces_a_row_per_movie_entry_not_per_heading(tmp_path: Path) -> None:
    rows = parse_org(_org_file(tmp_path))

    # 4 movies, not the 2 medium headings or the 1 top-level heading
    assert len(rows) == 4


def test_parse_org_ambiguous_medium_is_a_failed_row(tmp_path: Path) -> None:
    org_path = tmp_path / "movies.org"
    org_path.write_text(
        "* Movies :movies:2026:\n** A film with no medium heading\n<2026-01-01 Thu>\n"
    )

    rows = parse_org(org_path)

    assert rows[0].entry is None
    assert rows[0].error is not None


# --- run_import: tasks 6.1-6.4, duplicate handling and the summary ---


def test_run_import_creates_entries_and_resolves_medium_and_venue(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Dune",
                date=date(2026, 1, 1),
                medium="cinema",
                venue="Grand Vista Cinema",
                imdb_url="https://www.imdb.com/title/tt1160419/",
            ),
            error=None,
        )
    ]

    summary = run_import(store, rows)

    assert summary.imported == 1
    assert summary.skipped_duplicates == 0
    assert summary.failed == 0
    (entry,) = store.list_entries()
    assert entry.title == "Dune"
    assert entry.imdb_url == "https://www.imdb.com/title/tt1160419/"
    medium = next(m for m in store.list_media() if m.name == "cinema")
    assert medium.is_physical_place is True
    assert [v.name for v in store.list_venues()] == ["Grand Vista Cinema"]


def test_run_import_reuses_existing_medium_and_venue(store: Store) -> None:
    existing_medium = store.add_medium("cinema", is_physical_place=True)
    existing_venue = store.add_venue("Grand Vista Cinema")
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Dune", date=date(2026, 1, 1), medium="cinema", venue="Grand Vista Cinema"
            ),
            error=None,
        )
    ]

    run_import(store, rows)

    assert len(store.list_media()) == 1
    assert len(store.list_venues()) == 1
    (entry,) = store.list_entries()
    assert entry.medium_id == existing_medium.id
    assert entry.venue_id == existing_venue.id


def test_run_import_counts_failed_rows(store: Store) -> None:
    rows = [ParsedRow(row_number=5, entry=None, error="date is invalid")]

    summary = run_import(store, rows)

    assert summary.failed == 1
    assert summary.imported == 0
    assert "row 5" in summary.failed_details[0]
    assert "date is invalid" in summary.failed_details[0]


def test_run_import_skips_a_duplicate_by_default(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(
        title="Midnight Ferry: Part Two", date=date(2026, 3, 29), medium_id=medium.id
    )
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Midnight Ferry: Part Two - Movies",
                date=date(2026, 3, 29),
                medium="cinema",
            ),
            error=None,
        )
    ]

    summary = run_import(store, rows)

    assert summary.imported == 0
    assert summary.skipped_duplicates == 1
    assert len(store.list_entries()) == 1
    assert "row 1" in summary.skipped_details[0]


def test_run_import_force_persists_duplicates(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title="Dune", date=date(2026, 1, 1), medium="cinema"),
            error=None,
        )
    ]

    summary = run_import(store, rows, force=True)

    assert summary.imported == 1
    assert summary.skipped_duplicates == 0
    assert len(store.list_entries()) == 2


def test_run_import_detects_duplicates_within_the_same_batch(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title="Dune", date=date(2026, 1, 1), medium="cinema"),
            error=None,
        ),
        ParsedRow(
            row_number=2,
            entry=ImportRow(title="Dune", date=date(2026, 1, 1), medium="cinema"),
            error=None,
        ),
    ]

    summary = run_import(store, rows)

    assert summary.imported == 1
    assert summary.skipped_duplicates == 1


def test_run_import_one_bad_row_does_not_stop_the_rest(store: Store) -> None:
    rows = [
        ParsedRow(row_number=1, entry=None, error="bad date"),
        ParsedRow(
            row_number=2,
            entry=ImportRow(title="Dune", date=date(2026, 1, 1), medium="cinema"),
            error=None,
        ),
    ]

    summary = run_import(store, rows)

    assert summary.failed == 1
    assert summary.imported == 1
