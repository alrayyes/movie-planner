"""`list` narrows by title, venue, director, actor, genre, year and rated, and
every filter given must match.
"""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from movie_planner.cli import app
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
    cinema = s.get_or_create_medium("cinema", is_physical_place=True)
    tuschinski = s.get_or_create_venue("Tuschinski")
    eye = s.get_or_create_venue("Eye")
    dune = s.create_entry(
        title="Dune: Part Two",
        date=date(2026, 1, 1),
        medium_id=cinema.id,
        venue_id=tuschinski.id,
    )
    s.update_entry(
        dune.id,
        director="Denis Villeneuve",
        actors="Timothée Chalamet, Zendaya",
        genre="Action, Adventure, Sci-Fi",
        release_year=2024,
        rated="PG-13",
    )
    arrival = s.create_entry(
        title="Arrival", date=date(2026, 1, 2), medium_id=cinema.id, venue_id=eye.id
    )
    s.update_entry(
        arrival.id,
        director="Denis Villeneuve",
        actors="Amy Adams",
        genre="Drama, Sci-Fi",
        release_year=2016,
        rated="PG-13",
    )
    paddington = s.create_entry(title="Paddington", date=date(2026, 1, 3), medium_id=cinema.id)
    s.update_entry(
        paddington.id,
        director="Paul King",
        actors="Hugh Bonneville",
        genre="Comedy, Family",
        release_year=2014,
        rated="PG",
    )
    s.create_entry(title="Home Video", date=date(2026, 1, 4), medium_id=cinema.id)
    yield s
    s.close()


def _titles(config_path: Path, *args: str) -> list[str]:
    result = runner.invoke(app, ["--config", str(config_path), "list", "--json", *args])
    assert result.exit_code == 0, result.output
    return [row["title"] for row in json.loads(result.output)]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--director", "Denis Villeneuve"], ["Dune: Part Two", "Arrival"]),
        (["--director", "villeneuve"], ["Dune: Part Two", "Arrival"]),
        (["--actor", "Zendaya"], ["Dune: Part Two"]),
        (["--actor", "amy adams"], ["Arrival"]),
        (["--genre", "Sci-Fi"], ["Dune: Part Two", "Arrival"]),
        (["--genre", "comedy"], ["Paddington"]),
        (["--title", "dune"], ["Dune: Part Two"]),
        (["--title", "ARRIV"], ["Arrival"]),
        (["--venue", "Eye"], ["Arrival"]),
        (["--venue", "tuschinski"], ["Dune: Part Two"]),
        (["--year", "2016"], ["Arrival"]),
        (["--rated", "PG"], ["Paddington"]),
        (["--rated", "pg-13"], ["Dune: Part Two", "Arrival"]),
    ],
)
def test_each_filter_lists_only_matching_entries(
    config_path: Path, store: Store, args: list[str], expected: list[str]
) -> None:
    assert _titles(config_path, *args) == expected


def test_filters_given_together_must_all_match(config_path: Path, store: Store) -> None:
    assert _titles(config_path, "--director", "Villeneuve", "--year", "2016") == ["Arrival"]
    assert _titles(config_path, "--director", "Villeneuve", "--rated", "PG") == []


def test_a_venue_nothing_was_seen_at_lists_nothing(config_path: Path, store: Store) -> None:
    assert _titles(config_path, "--venue", "No Such Cinema") == []


def test_filters_combine_with_the_existing_ones(config_path: Path, store: Store) -> None:
    assert _titles(config_path, "--genre", "Sci-Fi", "--from", "2026-01-02") == ["Arrival"]


def test_a_filter_with_no_match_prints_the_plain_message(config_path: Path, store: Store) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "list", "--director", "Nobody"])

    assert result.exit_code == 0, result.output
    assert "No entries." in result.output


def test_a_literal_percent_or_underscore_is_not_a_wildcard(config_path: Path, store: Store) -> None:
    assert _titles(config_path, "--title", "%") == []
    assert _titles(config_path, "--title", "Dune_Part") == []


def test_an_entry_without_omdb_data_never_matches_a_text_filter(
    config_path: Path, store: Store
) -> None:
    for args in (
        ["--director", "x"],
        ["--actor", "x"],
        ["--genre", "x"],
        ["--year", "2016"],
        ["--rated", "PG"],
        ["--venue", "Eye"],
    ):
        assert "Home Video" not in _titles(config_path, *args)
    assert _titles(config_path, "--title", "home") == ["Home Video"]


def test_an_unrated_entry_does_not_match_a_made_up_rating(config_path: Path, store: Store) -> None:
    assert _titles(config_path, "--rated", "XXXX") == []
