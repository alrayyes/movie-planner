"""An IMDb ratings.csv imports like a native CSV, once the header says which
it is. IMDb records the day a title was rated, not watched, so that is the
date used, and the medium comes from `--medium`. The export lists series,
episodes and games too: those are skipped, with what each is, not failed.
"""

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from movie_planner.cli import app
from movie_planner.importers import ImportRow, MediumRequiredError, parse_csv, run_import
from movie_planner.store import Store

runner = CliRunner()

HEADER = (
    "Const,Your Rating,Date Rated,Title,Original Title,URL,Title Type,IMDb Rating,"
    "Runtime (mins),Year,Genres,Num Votes,Release Date,Directors\n"
)


def _row(title: str, *, kind: str = "movie", rating: str = "9", const: str = "tt1160419") -> str:
    return (
        f"{const},{rating},2026-02-01,{title},{title},https://www.imdb.com/title/{const}/,"
        f'{kind},8.0,155,2021,"Sci-Fi, Adventure",100,2021-10-22,Denis Villeneuve\n'
    )


def _ratings(tmp_path: Path, *rows: str, bom: bool = False) -> Path:
    path = tmp_path / "ratings.csv"
    path.write_bytes((("﻿" if bom else "") + HEADER + "".join(rows)).encode("utf-8"))
    return path


def test_a_film_row_maps_to_an_import_row_dated_by_date_rated(tmp_path: Path) -> None:
    rows = parse_csv(_ratings(tmp_path, _row("Dune")), "cinema")

    assert rows[0].error is None
    assert rows[0].skipped is None
    assert rows[0].row_number == 2
    assert rows[0].entry == ImportRow(
        title="Dune",
        date=date(2026, 2, 1),
        medium="cinema",
        release_year=2021,
        genre="Sci-Fi, Adventure",
        director="Denis Villeneuve",
        imdb_url="https://www.imdb.com/title/tt1160419/",
        imdb_rating="8.0",
        notes="Your IMDb rating: 9/10",
    )


def test_a_row_without_a_personal_rating_has_no_note(tmp_path: Path) -> None:
    rows = parse_csv(_ratings(tmp_path, _row("Dune", rating="")), "cinema")

    assert rows[0].entry is not None
    assert rows[0].entry.notes is None


@pytest.mark.parametrize(
    ("kind", "what"),
    [
        ("tvSeries", "a TV series"),
        ("TV Mini Series", "a TV miniseries"),
        ("tvEpisode", "a TV episode"),
        ("videoGame", "a video game"),
        ("podcast-series", "a podcast"),
        ("PODCAST_EPISODE", "a podcast"),
        ("musicVideo", "a music video"),
    ],
)
def test_a_known_non_film_is_skipped_with_what_it_is(tmp_path: Path, kind: str, what: str) -> None:
    rows = parse_csv(_ratings(tmp_path, _row("Severance", kind=kind)), "cinema")

    assert rows[0].entry is None
    assert rows[0].error is None
    assert rows[0].skipped == f'"Severance" is {what} on IMDb, not a movie'


@pytest.mark.parametrize("kind", ["somethingNew", "movie", "tvMovie", ""])
def test_any_other_type_is_read_as_a_film(tmp_path: Path, kind: str) -> None:
    rows = parse_csv(_ratings(tmp_path, _row("Dune", kind=kind)), "cinema")

    assert rows[0].entry is not None
    assert rows[0].skipped is None


def test_ratings_without_a_medium_are_refused(tmp_path: Path) -> None:
    with pytest.raises(MediumRequiredError) as raised:
        parse_csv(_ratings(tmp_path, _row("Dune")))

    assert "IMDb ratings export" in str(raised.value)
    assert "--medium" in str(raised.value)


def test_a_blank_medium_counts_as_missing(tmp_path: Path) -> None:
    with pytest.raises(MediumRequiredError):
        parse_csv(_ratings(tmp_path, _row("Dune")), "   ")


def test_a_byte_order_mark_does_not_hide_the_header(tmp_path: Path) -> None:
    rows = parse_csv(_ratings(tmp_path, _row("Dune"), bom=True), "cinema")

    assert rows[0].entry is not None


def test_a_list_export_without_the_rating_columns_is_not_a_ratings_export(
    tmp_path: Path,
) -> None:
    path = tmp_path / "list.csv"
    path.write_text("Const,Title,URL\ntt1,Dune,https://x\n", encoding="utf-8")

    rows = parse_csv(path)

    assert rows[0].error is not None


def test_header_names_are_compared_trimmed(tmp_path: Path) -> None:
    path = tmp_path / "ratings.csv"
    path.write_text(
        "Const, Your Rating,Date Rated ,Title\ntt1,7,2026-02-01,Dune\n", encoding="utf-8"
    )

    rows = parse_csv(path, "cinema")

    assert rows[0].entry is not None
    assert rows[0].entry.notes == "Your IMDb rating: 7/10"


def test_a_skipped_row_is_counted_as_skipped_not_failed(tmp_path: Path) -> None:
    store = Store(tmp_path / "movies.db")
    try:
        rows = parse_csv(
            _ratings(tmp_path, _row("Dune"), _row("Severance", kind="tvSeries")), "cinema"
        )

        summary = run_import(store, rows)

        assert (summary.imported, summary.skipped_duplicates, summary.failed) == (1, 1, 0)
        assert summary.skipped_details == ['row 3: "Severance" is a TV series on IMDb, not a movie']
        assert [e.title for e in store.list_entries()] == ["Dune"]
    finally:
        store.close()


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(
        f"""
        [caldav]
        url = "https://baikal.example.com/calendars/movies/"
        username = "moviewatcher"
        password = "secret"

        [omdb]
        api_key = "test-key"

        [storage]
        db_path = "{tmp_path / "movies.db"}"
        """
    )
    return path


def test_the_command_imports_films_and_reports_the_skipped_rows(tmp_path: Path) -> None:
    config = _config(tmp_path)
    path = _ratings(tmp_path, _row("Dune"), _row("Severance", kind="tvSeries"))

    result = runner.invoke(
        app, ["--config", str(config), "import", str(path), "--medium", "cinema", "--no-metadata"]
    )

    assert result.exit_code == 0, result.output
    assert "1 imported, 1 skipped, 0 failed." in result.output
    assert 'skipped: row 3: "Severance" is a TV series on IMDb, not a movie' in result.output
    store = Store(tmp_path / "movies.db")
    try:
        assert [e.title for e in store.list_entries()] == ["Dune"]
        assert store.list_import_failures() == []
    finally:
        store.close()


def test_the_command_stops_before_writing_without_a_medium(tmp_path: Path) -> None:
    config = _config(tmp_path)

    result = runner.invoke(
        app, ["--config", str(config), "import", str(_ratings(tmp_path, _row("Dune")))]
    )

    assert result.exit_code == 1
    assert "--medium" in result.output
    store = Store(tmp_path / "movies.db")
    try:
        assert store.list_entries() == []
    finally:
        store.close()


def test_every_skipped_row_is_counted_and_the_rows_after_it_still_import(tmp_path: Path) -> None:
    store = Store(tmp_path / "movies.db")
    try:
        rows = parse_csv(
            _ratings(
                tmp_path,
                _row("Severance", kind="tvSeries"),
                _row("Arcane", kind="tvMiniSeries"),
                _row("Dune"),
            ),
            "cinema",
        )

        summary = run_import(store, rows)

        assert (summary.imported, summary.skipped_duplicates, summary.failed) == (1, 2, 0)
        assert len(summary.skipped_details) == 2
        assert [e.title for e in store.list_entries()] == ["Dune"]
    finally:
        store.close()


def test_a_skipped_row_with_no_title_still_says_what_it_is(tmp_path: Path) -> None:
    rows = parse_csv(_ratings(tmp_path, _row("", kind="tvSeries")), "cinema")

    assert rows[0].skipped == '"" is a TV series on IMDb, not a movie'
