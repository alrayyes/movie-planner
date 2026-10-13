"""Task 7.2 (log/list/update/delete against a real calendar) and 7.3
(the examples/movies.csv import walkthrough), run against a real Baikal
container rather than FakeCalendar - see baikal_container.py.

Slower than the rest of the suite (spins up a Docker container), so
kept in its own module rather than mixed into test_cli.py.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from baikal_container import BaikalTestServer, start_baikal
from typer.testing import CliRunner

from movie_planner.cli import app
from movie_planner.store import Store

runner = CliRunner()


@pytest.fixture(scope="module")
def baikal() -> Iterator[BaikalTestServer]:
    container, server = start_baikal()
    try:
        yield server
    finally:
        container.stop()


@pytest.fixture
def config_path(tmp_path: Path, baikal: BaikalTestServer) -> Path:
    db_path = tmp_path / "movies.db"
    path = tmp_path / "config.toml"
    path.write_text(
        f"""
        [caldav]
        url = "{baikal.caldav_url}"
        username = "{baikal.caldav_username}"
        password = "{baikal.caldav_password}"

        [omdb]
        api_key = "unused"

        [storage]
        db_path = "{db_path}"
        """
    )
    return path


@pytest.fixture(autouse=True)
def no_omdb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: None)


def _store(config_path: Path) -> Store:
    import tomllib

    with config_path.open("rb") as f:
        data = tomllib.load(f)
    return Store(Path(data["storage"]["db_path"]))


# --- task 7.2: end-to-end log, list, update, delete ---


def test_log_list_update_delete_against_a_real_calendar(config_path: Path) -> None:
    log_result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "log",
            "--title",
            "Dune",
            "--date",
            "2026-01-01",
            "--medium",
            "cinema",
            "--venue",
            "Grand Vista Cinema",
        ],
    )
    assert log_result.exit_code == 0, log_result.output

    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is not None
    store.close()

    list_result = runner.invoke(app, ["--config", str(config_path), "list"])
    assert "Dune" in list_result.output

    update_result = runner.invoke(
        app,
        ["--config", str(config_path), "update", str(entry.id), "--title", "Dune Part Two"],
    )
    assert update_result.exit_code == 0, update_result.output

    delete_result = runner.invoke(app, ["--config", str(config_path), "delete", str(entry.id)])
    assert delete_result.exit_code == 0, delete_result.output

    store = _store(config_path)
    assert store.list_entries() == []
    store.close()


# --- task 7.3: import examples/movies.csv against a real calendar ---


def test_import_examples_csv_against_a_real_calendar(config_path: Path) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "import", "examples/movies.csv"])

    assert result.exit_code == 0, result.output
    assert "3 imported" in result.output
    assert "0 skipped" in result.output
    assert "0 failed" in result.output

    store = _store(config_path)
    entries = store.list_entries()
    assert len(entries) == 3
    assert all(e.caldav_uid is not None for e in entries)
    store.close()
