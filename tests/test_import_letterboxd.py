"""A Letterboxd diary.csv imports like a native CSV, once the header says
which it is. The columns are Letterboxd's own, so the medium comes from
`--medium`: a diary never records where a film was watched.
"""

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from movie_planner.cli import app
from movie_planner.importers import (
    IMPORT_FORMATS,
    ImportRow,
    MediumRequiredError,
    parse_csv,
)
from movie_planner.store import Store

runner = CliRunner()

HEADER = "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
DIARY = (
    HEADER
    + '2026-02-01,Dune: Part Two,2024,https://boxd.it/abc,4.5,,"sci-fi, imax",2026-01-30\n'
    + "2026-02-02,Arrival,2016,https://boxd.it/def,,Yes,,2026-02-02\n"
)


def _diary(tmp_path: Path, text: str = DIARY, *, bom: bool = False) -> Path:
    path = tmp_path / "diary.csv"
    path.write_bytes((("﻿" if bom else "") + text).encode("utf-8"))
    return path


def test_a_diary_row_maps_to_an_import_row_dated_by_watched_date(tmp_path: Path) -> None:
    rows = parse_csv(_diary(tmp_path), "netflix")

    assert rows[0].error is None
    assert rows[0].row_number == 2
    assert rows[0].entry == ImportRow(
        title="Dune: Part Two",
        date=date(2026, 1, 30),
        medium="netflix",
        release_year=2024,
        letterboxd_url="https://boxd.it/abc",
        letterboxd_rating="4.5",
        notes="Tags: sci-fi, imax",
    )
    assert rows[1].entry == ImportRow(
        title="Arrival",
        date=date(2026, 2, 2),
        medium="netflix",
        release_year=2016,
        letterboxd_url="https://boxd.it/def",
    )


def test_a_diary_without_a_medium_is_refused_before_any_row_is_read(tmp_path: Path) -> None:
    with pytest.raises(MediumRequiredError) as raised:
        parse_csv(_diary(tmp_path))

    assert str(raised.value) == (
        "This looks like a Letterboxd diary, which doesn't say where you watched. "
        "Pass --medium, for example --medium netflix."
    )


def test_a_byte_order_mark_does_not_hide_the_diary_header(tmp_path: Path) -> None:
    rows = parse_csv(_diary(tmp_path, bom=True), "netflix")

    assert [r.error for r in rows] == [None, None]
    assert rows[0].entry is not None
    assert rows[0].entry.title == "Dune: Part Two"


def test_a_native_csv_is_still_read_as_before(tmp_path: Path) -> None:
    path = tmp_path / "movies.csv"
    path.write_text("title,date,medium\nDune,2024-03-15,cinema\n", encoding="utf-8")

    rows = parse_csv(path, "ignored")

    assert rows[0].entry == ImportRow(title="Dune", date=date(2024, 3, 15), medium="cinema")


def test_a_diary_with_only_the_required_columns_is_still_a_diary(tmp_path: Path) -> None:
    path = tmp_path / "diary.csv"
    path.write_text(
        "Name,Letterboxd URI,Watched Date\nDune,https://boxd.it/a,2026-01-30\n", encoding="utf-8"
    )

    rows = parse_csv(path, "netflix")

    assert rows[0].entry == ImportRow(
        title="Dune",
        date=date(2026, 1, 30),
        medium="netflix",
        letterboxd_url="https://boxd.it/a",
    )


def test_diary_header_names_are_compared_trimmed(tmp_path: Path) -> None:
    path = tmp_path / "diary.csv"
    path.write_text(
        "Name, Letterboxd URI ,Watched Date\nDune,https://boxd.it/a,2026-01-30\n",
        encoding="utf-8",
    )

    rows = parse_csv(path, "netflix")

    assert rows[0].entry is not None
    assert rows[0].entry.letterboxd_url == "https://boxd.it/a"


def test_a_blank_medium_counts_as_missing(tmp_path: Path) -> None:
    with pytest.raises(MediumRequiredError):
        parse_csv(_diary(tmp_path), "   ")


def test_the_medium_is_trimmed(tmp_path: Path) -> None:
    rows = parse_csv(_diary(tmp_path), "  netflix ")

    assert rows[0].entry is not None
    assert rows[0].entry.medium == "netflix"


def test_a_header_missing_one_diary_column_is_a_native_csv(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("Name,Letterboxd URI\nDune,https://boxd.it/a\n", encoding="utf-8")

    rows = parse_csv(path)

    assert rows[0].error is not None


def test_a_diary_row_with_a_bad_date_fails_on_its_own(tmp_path: Path) -> None:
    text = HEADER + "2026-02-01,Dune,2021,https://boxd.it/a,,,,not-a-date\n"

    rows = parse_csv(_diary(tmp_path, text), "netflix")

    assert rows[0].entry is None
    assert rows[0].error is not None


def test_the_registry_passes_the_medium_through(tmp_path: Path) -> None:
    rows = IMPORT_FORMATS[".csv"].parse(_diary(tmp_path), "cinema")

    assert rows[0].entry is not None
    assert rows[0].entry.medium == "cinema"


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


def test_the_command_imports_a_diary_with_a_medium(tmp_path: Path) -> None:
    config = _config(tmp_path)

    result = runner.invoke(
        app,
        [
            "--config",
            str(config),
            "import",
            str(_diary(tmp_path)),
            "--medium",
            "netflix",
            "--no-metadata",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2 imported" in result.output
    store = Store(tmp_path / "movies.db")
    try:
        entries = store.list_entries()
        assert [e.title for e in entries] == ["Dune: Part Two", "Arrival"]
        assert entries[0].date == date(2026, 1, 30)
        assert entries[0].letterboxd_rating == "4.5"
        assert entries[0].notes == "Tags: sci-fi, imax"
        assert [m.name for m in store.list_media()] == ["netflix"]
    finally:
        store.close()


def test_the_command_stops_before_writing_when_a_diary_has_no_medium(tmp_path: Path) -> None:
    config = _config(tmp_path)

    result = runner.invoke(app, ["--config", str(config), "import", str(_diary(tmp_path))])

    assert result.exit_code == 1
    assert "--medium" in result.output
    store = Store(tmp_path / "movies.db")
    try:
        assert store.list_entries() == []
        assert store.list_import_failures() == []
    finally:
        store.close()
