from collections.abc import Iterator
from datetime import date, time
from pathlib import Path

import pytest

from movie_planner.importers import ImportRow, ParsedRow, parse_csv, parse_json, run_import
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
        "The Clockmaker's Daughter,2024-03-15,19:00,21:15,cinema,Grand Vista Cinema,"
        "https://www.imdb.com/title/tt0000101/\n"
    )

    rows = parse_csv(csv_path)

    assert len(rows) == 1
    assert rows[0].error is None
    entry = rows[0].entry
    assert entry == ImportRow(
        title="The Clockmaker's Daughter",
        date=date(2024, 3, 15),
        medium="cinema",
        start_time=time(19, 0),
        end_time=time(21, 15),
        venue="Grand Vista Cinema",
        imdb_url="https://www.imdb.com/title/tt0000101/",
    )


def test_parse_csv_optional_fields_blank(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text(
        "title,date,start_time,end_time,medium,venue,imdb_url\n"
        "Paper Constellations,2024-01-20,,,netflix,,\n"
    )

    rows = parse_csv(csv_path)

    entry = rows[0].entry
    assert entry.start_time is None
    assert entry.end_time is None
    assert entry.venue is None
    assert entry.imdb_url is None


def test_parse_csv_missing_title_is_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\n,2024-01-01,cinema\n")

    rows = parse_csv(csv_path)

    assert rows[0].entry is None
    assert rows[0].error is not None
    assert rows[0].row_number == 2


def test_parse_csv_bad_date_is_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nSolstice Run,not-a-date,cinema\n")

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
                "title": "Solstice Run",
                "date": "2024-06-02",
                "start_time": "20:30",
                "end_time": "22:10",
                "medium": "cinema",
                "venue": "Riverside Multiplex",
                "imdb_url": "https://www.imdb.com/title/tt0000102/"
            }
        ]
        """
    )

    rows = parse_json(json_path)

    assert rows[0].entry == ImportRow(
        title="Solstice Run",
        date=date(2024, 6, 2),
        medium="cinema",
        start_time=time(20, 30),
        end_time=time(22, 10),
        venue="Riverside Multiplex",
        imdb_url="https://www.imdb.com/title/tt0000102/",
    )


def test_parse_json_missing_optional_keys(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_text(
        '[{"title": "Paper Constellations", "date": "2024-01-20", "medium": "netflix"}]'
    )

    rows = parse_json(json_path)

    entry = rows[0].entry
    assert entry.start_time is None
    assert entry.venue is None


def test_parse_json_missing_medium_is_a_failed_row(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_text('[{"title": "Solstice Run", "date": "2024-06-02"}]')

    rows = parse_json(json_path)

    assert rows[0].entry is None
    assert rows[0].error is not None


# --- run_import: tasks 6.1, 6.4, duplicate handling and the summary ---


def test_run_import_creates_entries_and_resolves_medium_and_venue(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="The Clockmaker's Daughter",
                date=date(2024, 3, 15),
                medium="cinema",
                venue="Grand Vista Cinema",
                imdb_url="https://www.imdb.com/title/tt0000101/",
            ),
            error=None,
        )
    ]

    summary = run_import(store, rows)

    assert summary.imported == 1
    assert summary.skipped_duplicates == 0
    assert summary.failed == 0
    (entry,) = store.list_entries()
    assert entry.title == "The Clockmaker's Daughter"
    assert entry.imdb_url == "https://www.imdb.com/title/tt0000101/"
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
                title="The Clockmaker's Daughter",
                date=date(2024, 3, 15),
                medium="cinema",
                venue="Grand Vista Cinema",
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
        title="Solstice Run: Director's Cut", date=date(2024, 6, 2), medium_id=medium.id
    )
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Solstice Run: Director's Cut", date=date(2024, 6, 2), medium="cinema"
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
    store.create_entry(title="Solstice Run", date=date(2024, 6, 2), medium_id=medium.id)
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title="Solstice Run", date=date(2024, 6, 2), medium="cinema"),
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
            entry=ImportRow(title="Solstice Run", date=date(2024, 6, 2), medium="cinema"),
            error=None,
        ),
        ParsedRow(
            row_number=2,
            entry=ImportRow(title="Solstice Run", date=date(2024, 6, 2), medium="cinema"),
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
            entry=ImportRow(title="Solstice Run", date=date(2024, 6, 2), medium="cinema"),
            error=None,
        ),
    ]

    summary = run_import(store, rows)

    assert summary.failed == 1
    assert summary.imported == 1
