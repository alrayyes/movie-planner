"""The rows `movie-planner export` writes validate against
examples/movies.schema.json. A file of its own because it reads examples/,
which mutmut's mutant sandbox doesn't mirror (see pyproject.toml).
"""

import json
from datetime import date, time
from pathlib import Path

import jsonschema
from typer.testing import CliRunner

from movie_planner.cli import app
from movie_planner.store import Store

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "examples" / "movies.schema.json").read_text(encoding="utf-8")
)


def test_an_export_validates_against_the_import_schema(tmp_path: Path) -> None:
    db = tmp_path / "movies.db"
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
        [caldav]
        url = "https://baikal.example.com/calendars/movies/"
        username = "moviewatcher"
        password = "secret"

        [omdb]
        api_key = "test-key"

        [storage]
        db_path = "{db}"
        """
    )
    store = Store(db)
    try:
        cinema = store.get_or_create_medium("cinema", is_physical_place=True)
        venue = store.get_or_create_venue("Grand Vista Cinema")
        entry = store.create_entry(
            title="Dune",
            date=date(2026, 2, 15),
            medium_id=cinema.id,
            start_time=time(19, 30),
            venue_id=venue.id,
        )
        store.update_entry(
            entry.id,
            imdb_url="https://www.imdb.com/title/tt1160419/",
            release_year=2021,
            poster_url="https://example.com/dune.jpg",
        )
        store.create_entry(title="Paddington", date=date(2026, 3, 1), medium_id=cinema.id)
    finally:
        store.close()

    result = CliRunner().invoke(app, ["--config", str(config), "export"])

    assert result.exit_code == 0, result.output
    jsonschema.validate(json.loads(result.stdout), SCHEMA)
