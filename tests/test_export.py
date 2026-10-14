"""`movie-planner export` writes the JSON the web app's "Export as JSON"
writes, so a file made by either tool imports into the other.
"""

import dataclasses
import json
from collections.abc import Iterator
from datetime import date, time
from pathlib import Path

import pytest
from fakes import FakeCalendar
from typer.testing import CliRunner

from movie_planner.calendar_sync import CalendarClient
from movie_planner.cli import app
from movie_planner.export import entry_to_export_row
from movie_planner.store import Store

runner = CliRunner()


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
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


@pytest.fixture
def store(tmp_path: Path, config_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "movies.db")
    yield s
    s.close()


@pytest.fixture
def calendar(monkeypatch: pytest.MonkeyPatch) -> FakeCalendar:
    fake = FakeCalendar()
    monkeypatch.setattr(
        CalendarClient, "connect", classmethod(lambda cls, **kw: CalendarClient(fake))
    )
    return fake


def _seed(store: Store) -> None:
    cinema = store.get_or_create_medium("cinema", is_physical_place=True)
    netflix = store.get_or_create_medium("netflix", is_physical_place=False)
    venue = store.get_or_create_venue("Grand Vista Cinema")
    dune = store.create_entry(
        title="Dune",
        date=date(2026, 2, 15),
        medium_id=cinema.id,
        start_time=time(19, 30),
        end_time=time(22, 15),
        venue_id=venue.id,
    )
    store.update_entry(
        dune.id,
        caldav_uid="abc@example.com",
        imdb_url="https://www.imdb.com/title/tt1160419/",
        imdb_rating="8.0",
        director="Denis Villeneuve",
        release_year=2021,
        notes="Loud",
        letterboxd_rating="4.5",
    )
    store.create_entry(title="Paddington", date=date(2026, 3, 1), medium_id=netflix.id)


def _export(config_path: Path, *args: str) -> str:
    result = runner.invoke(app, ["--config", str(config_path), "export", *args])
    assert result.exit_code == 0, result.output
    return result.stdout


def test_a_row_uses_the_web_apps_field_names_and_leaves_out_what_is_unset(store: Store) -> None:
    _seed(store)
    dune = store.list_entries()[0]
    medium = store.list_media()[0]
    venue = store.list_venues()[0]

    row = entry_to_export_row(dune, medium_name=medium.name, venue=venue)

    assert row == {
        "uid": "abc@example.com",
        "title": "Dune",
        "date": "2026-02-15",
        "start_time": "19:30",
        "end_time": "22:15",
        "medium": "cinema",
        "venue": "Grand Vista Cinema",
        "director": "Denis Villeneuve",
        "release_year": 2021,
        "imdb_rating": "8.0",
        "imdb_url": "https://www.imdb.com/title/tt1160419/",
        "letterboxd_rating": "4.5",
        "notes": "Loud",
    }


def test_a_row_never_carries_the_booking_reference(store: Store) -> None:
    _seed(store)
    entry = store.list_entries()[0]
    store.update_entry(entry.id, booking_ref="SECRET123")

    row = entry_to_export_row(store.list_entries()[0], medium_name="cinema", venue=None)

    assert "booking_ref" not in row


def test_export_writes_every_entry_as_a_json_array(config_path: Path, store: Store) -> None:
    _seed(store)

    rows = json.loads(_export(config_path))

    assert [r["title"] for r in rows] == ["Dune", "Paddington"]


def test_a_fully_populated_row_carries_every_field_under_its_import_name(store: Store) -> None:
    medium = store.get_or_create_medium("cinema", is_physical_place=True)
    venue = store.get_or_create_venue("Grand Vista Cinema")
    entry = store.create_entry(
        title="Dune",
        date=date(2026, 2, 15),
        medium_id=medium.id,
        start_time=time(19, 30, 15),
        end_time=time(22, 15),
        venue_id=venue.id,
    )
    store.update_entry(
        entry.id,
        caldav_uid="abc@example.com",
        imdb_url="https://www.imdb.com/title/tt1160419/",
        imdb_rating="8.0",
        rotten_tomatoes_rating="83%",
        metacritic_rating="74",
        poster_url="https://example.com/dune.jpg",
        director="Denis Villeneuve",
        actors="Timothée Chalamet",
        genre="Sci-Fi",
        release_year=2021,
        letterboxd_url="https://letterboxd.com/film/dune-2021/",
        letterboxd_rating="4.5",
        notes="Loud",
        source="pathe.nl",
        row="12",
        seat="7",
    )

    row = entry_to_export_row(store.list_entries()[0], medium_name="cinema", venue=venue)

    assert row == {
        "uid": "abc@example.com",
        "title": "Dune",
        "date": "2026-02-15",
        "start_time": "19:30:15",
        "end_time": "22:15",
        "medium": "cinema",
        "venue": "Grand Vista Cinema",
        "director": "Denis Villeneuve",
        "actors": "Timothée Chalamet",
        "genre": "Sci-Fi",
        "release_year": 2021,
        "poster_url": "https://example.com/dune.jpg",
        "imdb_rating": "8.0",
        "rotten_tomatoes_rating": "83%",
        "metacritic_rating": "74",
        "imdb_url": "https://www.imdb.com/title/tt1160419/",
        "letterboxd_url": "https://letterboxd.com/film/dune-2021/",
        "letterboxd_rating": "4.5",
        "notes": "Loud",
        "source": "pathe.nl",
        "row": "12",
        "seat": "7",
    }


def test_export_filters_by_date_and_medium(config_path: Path, store: Store) -> None:
    _seed(store)

    assert [r["title"] for r in json.loads(_export(config_path, "--from", "2026-03-01"))] == [
        "Paddington"
    ]
    assert [r["title"] for r in json.loads(_export(config_path, "--to", "2026-02-28"))] == ["Dune"]
    assert [r["title"] for r in json.loads(_export(config_path, "--medium", "netflix"))] == [
        "Paddington"
    ]


def test_export_of_nothing_is_an_empty_array(config_path: Path, store: Store) -> None:
    assert json.loads(_export(config_path)) == []
    _seed(store)
    assert json.loads(_export(config_path, "--medium", "no-such-medium")) == []


def test_export_can_write_to_a_file(config_path: Path, store: Store, tmp_path: Path) -> None:
    _seed(store)
    out = tmp_path / "out.json"

    stdout = _export(config_path, "--output", str(out))

    assert [r["title"] for r in json.loads(out.read_text(encoding="utf-8"))] == [
        "Dune",
        "Paddington",
    ]
    assert "2 entries" in stdout


def test_an_export_imports_back_into_an_empty_store(
    config_path: Path, store: Store, tmp_path: Path, calendar: FakeCalendar
) -> None:
    _seed(store)
    out = tmp_path / "out.json"
    _export(config_path, "--output", str(out))

    other_config = tmp_path / "other.toml"
    other_config.write_text(
        config_path.read_text(encoding="utf-8").replace("movies.db", "other.db")
    )
    result = runner.invoke(
        app, ["--config", str(other_config), "import", str(out), "--no-metadata"]
    )

    assert result.exit_code == 0, result.output
    assert "2 imported, 0 skipped, 0 failed" in result.output
    other = Store(tmp_path / "other.db")
    try:
        dune = next(e for e in other.list_entries() if e.title == "Dune")
        assert (dune.date, dune.start_time, dune.end_time) == (
            date(2026, 2, 15),
            time(19, 30),
            time(22, 15),
        )
        assert dune.director == "Denis Villeneuve"
        assert dune.imdb_rating == "8.0"
        assert {m.id: m.name for m in other.list_media()}[dune.medium_id] == "cinema"
        assert dune.venue_id is not None
        assert {v.id: v.name for v in other.list_venues()}[dune.venue_id] == "Grand Vista Cinema"
        assert dune.release_year == 2021
        assert dune.notes == "Loud"
        assert dune.letterboxd_rating == "4.5"
    finally:
        other.close()


_VENUE_FIELDS = {"city", "country", "street_address", "postal_code", "latitude", "longitude"}


def test_a_row_carries_the_venues_location_under_the_web_apps_field_names(store: Store) -> None:
    _seed(store)
    venue = dataclasses.replace(
        store.list_venues()[0],
        city="Amsterdam",
        country="Netherlands",
        street_address="Kinoplein 1",
        postal_code="1011 AB",
        latitude=52.37,
        longitude=4.89,
    )

    row = entry_to_export_row(store.list_entries()[0], medium_name="cinema", venue=venue)

    assert {k: row[k] for k in row if k in _VENUE_FIELDS} == {
        "city": "Amsterdam",
        "country": "Netherlands",
        "street_address": "Kinoplein 1",
        "postal_code": "1011 AB",
        "latitude": 52.37,
        "longitude": 4.89,
    }


def test_a_row_for_a_venue_without_a_location_leaves_the_location_fields_out(
    store: Store,
) -> None:
    _seed(store)
    venue = store.list_venues()[0]

    row = entry_to_export_row(store.list_entries()[0], medium_name="cinema", venue=venue)

    assert _VENUE_FIELDS.isdisjoint(row)


# File name (the web app's) on the left, the Entry attribute on the right.
_EXTRAS = {
    "synopsis": "plot",
    "rated": "rated",
    "runtime": "runtime",
    "movie_language": "language",
    "movie_country": "country",
    "metascore": "metascore",
    "imdb_votes": "imdb_votes",
    "dvd": "dvd",
    "box_office": "box_office",
    "production": "production",
    "website": "website",
    "released": "released",
    "awards": "awards",
    "trailer_url": "trailer_url",
    "collection": "collection",
    "certification": "certification",
    "keywords": "keywords",
}


def _seed_extras(store: Store) -> None:
    _seed(store)
    dune = store.list_entries()[0]
    store.update_entry(
        dune.id,
        **{attr: f"{attr} value" for attr in _EXTRAS.values()},  # type: ignore[arg-type]
        budget=165000000,
        popularity=87.5,
    )


def test_a_row_carries_the_synopsis_and_extras_under_the_web_apps_names(store: Store) -> None:
    _seed_extras(store)

    row = entry_to_export_row(store.list_entries()[0], medium_name="cinema", venue=None)

    assert {name: row[name] for name in _EXTRAS} == {
        name: f"{attr} value" for name, attr in _EXTRAS.items()
    }
    assert row["budget"] == "165000000"
    assert row["popularity"] == "87.5"


def test_an_export_imports_back_with_its_synopsis_and_extras(
    config_path: Path, store: Store, tmp_path: Path
) -> None:
    _seed_extras(store)
    out = tmp_path / "out.json"
    _export(config_path, "--output", str(out))
    other_config = tmp_path / "other.toml"
    other_config.write_text(
        config_path.read_text(encoding="utf-8").replace("movies.db", "other.db")
    )

    result = runner.invoke(
        app, ["--config", str(other_config), "import", str(out), "--no-metadata"]
    )

    assert result.exit_code == 0, result.output
    other = Store(tmp_path / "other.db")
    try:
        dune = next(e for e in other.list_entries() if e.title == "Dune")
        for attr in _EXTRAS.values():
            assert getattr(dune, attr) == f"{attr} value", attr
        assert (dune.budget, dune.popularity) == (165000000, 87.5)
    finally:
        other.close()


def test_a_bad_budget_fails_only_its_row(config_path: Path, tmp_path: Path) -> None:
    rows = tmp_path / "rows.json"
    rows.write_text(
        '[{"title": "A", "date": "2026-01-01", "medium": "netflix", "budget": "lots"},'
        ' {"title": "B", "date": "2026-01-02", "medium": "netflix", "budget": 5}]'
    )

    result = runner.invoke(
        app, ["--config", str(config_path), "import", str(rows), "--no-metadata"]
    )

    assert "1 imported, 0 skipped, 1 failed" in result.output
    assert "budget" in result.output


@pytest.mark.parametrize(
    ("field", "value"),
    [("budget", 12.7), ("budget", True), ("popularity", "nan"), ("popularity", "inf")],
)
def test_a_number_field_that_is_not_a_plain_number_fails_its_row(
    config_path: Path, tmp_path: Path, field: str, value: object
) -> None:
    rows = tmp_path / "rows.json"
    rows.write_text(
        json.dumps([{"title": "A", "date": "2026-01-01", "medium": "netflix", field: value}])
    )

    result = runner.invoke(
        app, ["--config", str(config_path), "import", str(rows), "--no-metadata"]
    )

    assert "0 imported, 0 skipped, 1 failed" in result.output
    assert f"{field} must be a number" in result.output


def _import_into_other(config_path: Path, tmp_path: Path, file: Path) -> tuple[str, Store]:
    other_config = tmp_path / "other.toml"
    other_config.write_text(
        config_path.read_text(encoding="utf-8").replace("movies.db", "other.db")
    )
    result = runner.invoke(
        app, ["--config", str(other_config), "import", str(file), "--no-metadata"]
    )
    return result.output, Store(tmp_path / "other.db")


def test_an_export_imports_back_with_its_venues_location(
    config_path: Path, store: Store, tmp_path: Path
) -> None:
    _seed(store)
    store.update_venue(
        "Grand Vista Cinema",
        city="Amsterdam",
        country="Netherlands",
        street_address="Kinoplein 1",
        postal_code="1011 AB",
        latitude=52.37,
        longitude=4.89,
    )
    out = tmp_path / "out.json"
    _export(config_path, "--output", str(out))

    _, other = _import_into_other(config_path, tmp_path, out)

    try:
        (venue,) = other.list_venues()
        assert (
            venue.city,
            venue.country,
            venue.street_address,
            venue.postal_code,
            venue.latitude,
            venue.longitude,
        ) == ("Amsterdam", "Netherlands", "Kinoplein 1", "1011 AB", 52.37, 4.89)
    finally:
        other.close()


def test_import_fills_only_the_venue_fields_that_are_empty(
    config_path: Path, store: Store, tmp_path: Path
) -> None:
    store.get_or_create_venue("Grand Vista Cinema")
    store.update_venue("Grand Vista Cinema", city="Rotterdam")
    rows = tmp_path / "rows.json"
    rows.write_text(
        json.dumps(
            [
                {
                    "title": "A",
                    "date": "2026-01-01",
                    "medium": "cinema",
                    "venue": "Grand Vista Cinema",
                    "city": "Amsterdam",
                    "country": "Netherlands",
                }
            ]
        )
    )

    result = runner.invoke(
        app, ["--config", str(config_path), "import", str(rows), "--no-metadata"]
    )

    assert result.exit_code == 0, result.output
    (venue,) = Store(tmp_path / "movies.db").list_venues()
    assert (venue.city, venue.country) == ("Rotterdam", "Netherlands")


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"latitude": 52.37}, "latitude and longitude must both be given"),
        ({"longitude": 4.89}, "latitude and longitude must both be given"),
        ({"latitude": 91, "longitude": 4.89}, "latitude must be between -90 and 90"),
        ({"latitude": 52.37, "longitude": 181}, "longitude must be between -180 and 180"),
        ({"latitude": "north", "longitude": 4.89}, "latitude must be a number"),
    ],
)
def test_a_bad_venue_coordinate_fails_only_its_row(
    config_path: Path, tmp_path: Path, fields: dict[str, object], message: str
) -> None:
    base = {"date": "2026-01-01", "medium": "cinema", "venue": "Grand Vista Cinema"}
    rows = tmp_path / "rows.json"
    rows.write_text(json.dumps([{"title": "A", **base, **fields}, {"title": "B", **base}]))

    result = runner.invoke(
        app, ["--config", str(config_path), "import", str(rows), "--no-metadata"]
    )

    assert "1 imported, 0 skipped, 1 failed" in result.output
    assert message in result.output
