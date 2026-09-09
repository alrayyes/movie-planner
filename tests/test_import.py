import locale
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, time
from pathlib import Path

import pytest

from movie_planner.importers import (
    IMPORT_FORMATS,
    ImportRow,
    ParsedRow,
    parse_csv,
    parse_json,
    parse_json_text,
    run_import,
)
from movie_planner.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "movies.db")
    yield s
    s.close()


@contextmanager
def _c_locale() -> Iterator[None]:
    """Forces the POSIX "C" locale for the duration of the block - `open(...,
    encoding=None)` resolves to plain ASCII there, unlike almost every real
    deployment locale. Used to prove a read path pins `encoding="utf-8"`
    explicitly rather than relying on whatever the process locale happens to
    be, which would otherwise pass silently on any UTF-8-locale machine.
    """
    original = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        yield
    finally:
        locale.setlocale(locale.LC_ALL, original)


# --- IMPORT_FORMATS: issue #252, the registry cli.py dispatches through
# instead of a hardcoded if/elif on file suffix ---


def test_import_formats_registers_csv_and_json() -> None:
    assert set(IMPORT_FORMATS) == {".csv", ".json"}
    assert IMPORT_FORMATS[".csv"].name == "csv"
    assert IMPORT_FORMATS[".json"].name == "json"


def test_import_formats_csv_entry_parses_via_parse_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,2024-03-15,cinema\n")

    via_registry = IMPORT_FORMATS[".csv"].parse(csv_path)
    via_direct_call = parse_csv(csv_path)

    assert via_registry == via_direct_call


def test_import_formats_json_entry_parses_via_parse_json(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_text('[{"title": "Dune", "date": "2024-03-15", "medium": "cinema"}]')

    via_registry = IMPORT_FORMATS[".json"].parse(json_path)
    via_direct_call = parse_json(json_path)

    assert via_registry == via_direct_call


def test_import_formats_unsupported_suffix_is_absent() -> None:
    assert ".xlsx" not in IMPORT_FORMATS
    assert IMPORT_FORMATS.get(".xlsx") is None


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
    assert entry is not None
    assert entry.start_time is None
    assert entry.end_time is None
    assert entry.venue is None
    assert entry.imdb_url is None


def test_parse_csv_full_row_with_omdb_derived_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text(
        "title,date,medium,imdb_rating,rotten_tomatoes_rating,metacritic_rating,poster_url,"
        "director,actors,genre,release_year,source,letterboxd_url,letterboxd_rating\n"
        "Dune,2026-01-01,cinema,8.5/10,91%,80,"
        "https://m.media-amazon.com/images/dune-poster.jpg,Denis Villeneuve,"
        "Timothée Chalamet,Action,2021,pathe.nl,"
        "https://letterboxd.com/film/dune-2021/,4.5\n"
    )

    rows = parse_csv(csv_path)

    entry = rows[0].entry
    assert entry is not None
    assert entry.imdb_rating == "8.5/10"
    assert entry.rotten_tomatoes_rating == "91%"
    assert entry.metacritic_rating == "80"
    assert entry.poster_url == "https://m.media-amazon.com/images/dune-poster.jpg"
    assert entry.director == "Denis Villeneuve"
    assert entry.actors == "Timothée Chalamet"
    assert entry.genre == "Action"
    assert entry.release_year == 2021
    assert entry.source == "pathe.nl"
    assert entry.letterboxd_url == "https://letterboxd.com/film/dune-2021/"
    assert entry.letterboxd_rating == "4.5"


def test_parse_csv_full_row_with_row_and_seat(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium,row,seat\nDune,2026-01-01,cinema,5,17\n")

    rows = parse_csv(csv_path)

    entry = rows[0].entry
    assert entry is not None
    assert entry.row == "5"
    assert entry.seat == "17"


def test_parse_csv_preserves_a_crlf_embedded_inside_a_quoted_field(tmp_path: Path) -> None:
    # parse_csv must open with newline="" - without it, universal-newline
    # translation rewrites an embedded \r\n inside a quoted field to a bare
    # \n before csv.DictReader ever sees it, silently changing the value.
    csv_path = tmp_path / "movies.csv"
    csv_path.write_bytes(
        b'title,date,medium,notes\r\nDune,2024-03-15,cinema,"Line one\r\nLine two"\r\n'
    )

    rows = parse_csv(csv_path)

    entry = rows[0].entry
    assert entry is not None
    assert entry.notes == "Line one\r\nLine two"


def test_parse_csv_reads_as_utf8_regardless_of_the_process_locale(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_bytes("title,date,medium\nCafé Society,2024-01-01,cinema\n".encode())

    with _c_locale():
        rows = parse_csv(csv_path)

    entry = rows[0].entry
    assert entry is not None
    assert entry.title == "Café Society"


def test_parse_csv_ignores_a_booking_ref_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text(
        "title,date,medium,booking_ref\nDune,2026-01-01,cinema,BOOK123\n",
    )

    rows = parse_csv(csv_path)

    entry = rows[0].entry
    assert entry is not None
    assert not hasattr(entry, "booking_ref")


def test_parse_csv_bad_release_year_is_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium,release_year\nDune,2026-01-01,cinema,not-a-year\n")

    rows = parse_csv(csv_path)

    assert rows[0].entry is None
    assert rows[0].error is not None


def test_parse_csv_blank_release_year_is_none_not_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium,release_year\nDune,2026-01-01,cinema,\n")

    rows = parse_csv(csv_path)

    assert rows[0].error is None
    entry = rows[0].entry
    assert entry is not None
    assert entry.release_year is None


def test_parse_csv_missing_title_is_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\n,2024-01-01,cinema\n")

    rows = parse_csv(csv_path)

    assert rows[0].entry is None
    assert rows[0].error == "title is required"
    assert rows[0].row_number == 2


def test_parse_csv_missing_medium_is_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,2024-01-01,\n")

    rows = parse_csv(csv_path)

    assert rows[0].entry is None
    assert rows[0].error == "medium is required"


def test_parse_csv_bad_date_is_a_failed_row(tmp_path: Path) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nSolstice Run,not-a-date,cinema\n")

    rows = parse_csv(csv_path)

    assert rows[0].entry is None
    assert rows[0].error == "Invalid isoformat string: 'not-a-date'"


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
    assert entry is not None
    assert entry.start_time is None
    assert entry.venue is None


def test_parse_json_full_row_with_omdb_derived_fields(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_text(
        """
        [
            {
                "title": "Dune",
                "date": "2026-01-01",
                "medium": "cinema",
                "imdb_rating": "8.5/10",
                "poster_url": "https://m.media-amazon.com/images/dune-poster.jpg",
                "director": "Denis Villeneuve",
                "actors": "Timothée Chalamet",
                "genre": "Action",
                "release_year": 2021
            }
        ]
        """
    )

    rows = parse_json(json_path)

    entry = rows[0].entry
    assert entry is not None
    assert entry.imdb_rating == "8.5/10"
    assert entry.poster_url == "https://m.media-amazon.com/images/dune-poster.jpg"
    assert entry.director == "Denis Villeneuve"
    assert entry.actors == "Timothée Chalamet"
    assert entry.genre == "Action"
    assert entry.release_year == 2021


def test_parse_json_reads_as_utf8_regardless_of_the_process_locale(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_bytes(
        '[{"title": "Café Society", "date": "2024-01-01", "medium": "cinema"}]'.encode()
    )

    with _c_locale():
        rows = parse_json(json_path)

    entry = rows[0].entry
    assert entry is not None
    assert entry.title == "Café Society"


def test_parse_json_missing_medium_is_a_failed_row(tmp_path: Path) -> None:
    json_path = tmp_path / "movies.json"
    json_path.write_text('[{"title": "Solstice Run", "date": "2024-06-02"}]')

    rows = parse_json(json_path)

    assert rows[0].entry is None
    assert rows[0].error is not None


def test_parse_json_text_accepts_an_array() -> None:
    rows = parse_json_text('[{"title": "Solstice Run", "date": "2024-06-02", "medium": "cinema"}]')

    assert len(rows) == 1
    assert rows[0].entry is not None
    assert rows[0].entry.title == "Solstice Run"


def test_parse_json_text_accepts_a_bare_object_as_one_row() -> None:
    rows = parse_json_text('{"title": "Solstice Run", "date": "2024-06-02", "medium": "cinema"}')

    assert len(rows) == 1
    assert rows[0].entry is not None
    assert rows[0].entry.title == "Solstice Run"
    assert rows[0].row_number == 1


# --- run_import: tasks 6.1, 6.4, duplicate handling and the summary ---


def test_run_import_defaults_the_threshold_to_90(store: Store) -> None:
    # A title pair scoring ~90.2 - a duplicate under the documented default
    # of 90.0, but not under 91.0 or higher. Chosen this way, rather than
    # inspecting the parameter's default directly, because that default
    # only has to distinguish an actual call that omits `threshold` -
    # mutmut's own test harness swaps in the mutated function body while
    # leaving the importable wrapper's declared signature untouched, so
    # asserting on `inspect.signature` never observes the mutation at all.
    existing_title = "a very long and quite specific movie title used only for a threshold test"
    candidate_title = existing_title[:-13]
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title=existing_title, date=date(2024, 6, 2), medium_id=medium.id)
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title=candidate_title, date=date(2024, 6, 2), medium="cinema"),
            error=None,
        )
    ]

    summary = run_import(store, rows)

    assert summary.skipped_duplicates == 1
    assert summary.imported == 0


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


def test_run_import_creates_and_links_the_venue(store: Store) -> None:
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

    summary = run_import(store, rows)

    assert len(summary.imported_entries) == 1
    imported = summary.imported_entries[0]
    assert imported.entry.title == "The Clockmaker's Daughter"
    (venue,) = store.list_venues()
    assert venue.name == "Grand Vista Cinema"
    assert imported.entry.venue_id == venue.id


def test_run_import_stores_start_and_end_time_when_supplied(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Dune",
                date=date(2026, 1, 1),
                medium="cinema",
                start_time=time(19, 0),
                end_time=time(21, 15),
            ),
            error=None,
        )
    ]

    run_import(store, rows)

    (entry,) = store.list_entries()
    assert entry.start_time == time(19, 0)
    assert entry.end_time == time(21, 15)


def test_run_import_stores_omdb_derived_fields_when_supplied(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Dune",
                date=date(2026, 1, 1),
                medium="cinema",
                imdb_rating="8.5/10",
                rotten_tomatoes_rating="91%",
                metacritic_rating="80",
                poster_url="https://m.media-amazon.com/images/dune-poster.jpg",
                director="Denis Villeneuve",
                actors="Timothée Chalamet",
                genre="Action",
                release_year=2021,
            ),
            error=None,
        )
    ]

    run_import(store, rows)

    (entry,) = store.list_entries()
    assert entry.imdb_rating == "8.5/10"
    assert entry.rotten_tomatoes_rating == "91%"
    assert entry.metacritic_rating == "80"
    assert entry.poster_url == "https://m.media-amazon.com/images/dune-poster.jpg"
    assert entry.director == "Denis Villeneuve"
    assert entry.actors == "Timothée Chalamet"
    assert entry.genre == "Action"
    assert entry.release_year == 2021


def test_run_import_stores_letterboxd_when_supplied(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Dune",
                date=date(2026, 1, 1),
                medium="cinema",
                letterboxd_url="https://letterboxd.com/film/dune-2021/",
                letterboxd_rating="4.5",
            ),
            error=None,
        )
    ]

    run_import(store, rows)

    (entry,) = store.list_entries()
    assert entry.letterboxd_url == "https://letterboxd.com/film/dune-2021/"
    assert entry.letterboxd_rating == "4.5"


def test_run_import_stores_source_when_supplied(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Dune",
                date=date(2026, 1, 1),
                medium="cinema",
                source="pathe.nl",
            ),
            error=None,
        )
    ]

    run_import(store, rows)

    (entry,) = store.list_entries()
    assert entry.source == "pathe.nl"


def test_run_import_with_no_source_leaves_it_unset(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title="Dune", date=date(2026, 1, 1), medium="cinema"),
            error=None,
        )
    ]

    run_import(store, rows)

    (entry,) = store.list_entries()
    assert entry.source is None


def test_run_import_stores_row_and_seat_when_supplied(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="Dune",
                date=date(2026, 1, 1),
                medium="cinema",
                row="5",
                seat="17",
            ),
            error=None,
        )
    ]

    run_import(store, rows)

    (entry,) = store.list_entries()
    assert entry.row == "5"
    assert entry.seat == "17"


def test_run_import_with_no_row_or_seat_leaves_them_unset(store: Store) -> None:
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title="Dune", date=date(2026, 1, 1), medium="cinema"),
            error=None,
        )
    ]

    run_import(store, rows)

    (entry,) = store.list_entries()
    assert entry.row is None
    assert entry.seat is None


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


def test_run_import_skips_an_overlapping_screening_regardless_of_title(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(
        title="Solstice Run",
        date=date(2024, 6, 2),
        medium_id=medium.id,
        start_time=time(19, 0),
        end_time=time(21, 0),
    )
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="A Completely Different Film",
                date=date(2024, 6, 2),
                medium="cinema",
                start_time=time(19, 30),
                end_time=time(21, 30),
            ),
            error=None,
        )
    ]

    summary = run_import(store, rows)

    assert summary.imported == 0
    assert summary.skipped_duplicates == 1
    assert len(store.list_entries()) == 1


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


def test_run_import_counts_more_than_one_failed_row(store: Store) -> None:
    rows = [
        ParsedRow(row_number=1, entry=None, error="bad date"),
        ParsedRow(row_number=2, entry=None, error="bad medium"),
    ]

    summary = run_import(store, rows)

    assert summary.failed == 2


def test_run_import_counts_more_than_one_skipped_duplicate(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Solstice Run", date=date(2024, 6, 2), medium_id=medium.id)
    store.create_entry(title="Paper Constellations", date=date(2024, 1, 20), medium_id=medium.id)
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title="Solstice Run", date=date(2024, 6, 2), medium="cinema"),
            error=None,
        ),
        ParsedRow(
            row_number=2,
            entry=ImportRow(title="Paper Constellations", date=date(2024, 1, 20), medium="cinema"),
            error=None,
        ),
    ]

    summary = run_import(store, rows)

    assert summary.skipped_duplicates == 2


def test_run_import_continues_past_a_duplicate_to_later_rows(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Solstice Run", date=date(2024, 6, 2), medium_id=medium.id)
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title="Solstice Run", date=date(2024, 6, 2), medium="cinema"),
            error=None,
        ),
        ParsedRow(
            row_number=2,
            entry=ImportRow(
                title="A Totally Different Film", date=date(2024, 1, 1), medium="cinema"
            ),
            error=None,
        ),
    ]

    summary = run_import(store, rows)

    assert summary.skipped_duplicates == 1
    assert summary.imported == 1


def test_run_import_forwards_end_time_to_the_duplicate_check(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    # A short existing screening that only the candidate's *end* time reaches.
    store.create_entry(
        title="A Short Trailer Screening",
        date=date(2024, 6, 2),
        medium_id=medium.id,
        start_time=time(20, 0),
        end_time=time(20, 5),
    )
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(
                title="A Completely Different Film",
                date=date(2024, 6, 2),
                medium="cinema",
                start_time=time(18, 0),
                end_time=time(21, 0),
            ),
            error=None,
        )
    ]

    summary = run_import(store, rows)

    assert summary.imported == 0
    assert summary.skipped_duplicates == 1


def test_run_import_respects_a_custom_threshold(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Solstice Run", date=date(2024, 6, 2), medium_id=medium.id)
    rows = [
        ParsedRow(
            row_number=1,
            entry=ImportRow(title="Solstice Run", date=date(2024, 6, 2), medium="cinema"),
            error=None,
        )
    ]

    # An exact title match scores 100 - a threshold above that means no
    # title-based match is possible, even though the module-level default
    # (90.0, which happens to equal duplicates.DEFAULT_THRESHOLD) would flag
    # it. Proves run_import actually forwards its own threshold rather than
    # letting find_duplicate fall back to its own default.
    summary = run_import(store, rows, threshold=101.0)

    assert summary.imported == 1
    assert summary.skipped_duplicates == 0
