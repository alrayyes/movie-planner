from datetime import time
from pathlib import Path

import httpx
import pytest
from fakes import FakeCalendar
from fixtures import PATHE_BOOKING_REF, PATHE_EMAIL_PLAIN
from typer.testing import CliRunner

from movie_planner import config as config_module
from movie_planner.calendar_sync import CalendarClient
from movie_planner.cli import app
from movie_planner.omdb import MovieRatings, OmdbClient
from movie_planner.store import Store

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "movie-planner" in result.stdout


@pytest.mark.parametrize(
    "args", [["log", "--help"], ["locations", "media", "--help"], ["sync", "retry", "--help"]]
)
def test_subcommand_help_does_not_require_a_config_file(
    args: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`--config` isn't passed, so this only works if `--help` short-circuits
    before the app callback tries to load a (nonexistent) config file.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.output


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "movies.db"
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
        db_path = "{db_path}"
        """
    )
    return path


@pytest.fixture
def calendar(monkeypatch: pytest.MonkeyPatch) -> FakeCalendar:
    fake = FakeCalendar()
    monkeypatch.setattr(
        CalendarClient, "connect", classmethod(lambda cls, **kw: CalendarClient(fake))
    )
    return fake


@pytest.fixture
def no_omdb_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: None)


@pytest.fixture
def omdb_match(monkeypatch: pytest.MonkeyPatch) -> None:
    ratings = MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80")
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: ratings)


def _store(config_path: Path) -> Store:
    import tomllib

    with config_path.open("rb") as f:
        data = tomllib.load(f)
    return Store(Path(data["storage"]["db_path"]))


# --- log: tasks 3.3, 7.1 ---


def test_log_creates_entry_and_syncs_to_calendar(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    result = runner.invoke(
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

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.title == "Dune"
    assert entry.caldav_uid is not None
    assert entry.caldav_uid in calendar.events_by_uid
    store.close()


def test_log_venue_not_required_for_non_physical_medium(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "log",
            "--title",
            "Paper Constellations",
            "--date",
            "2026-01-01",
            "--medium",
            "netflix",
        ],
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.venue_id is None
    store.close()


def test_log_duplicate_without_force_is_rejected_non_interactively(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    common = [
        "--config",
        str(config_path),
        "log",
        "--title",
        "Solstice Run",
        "--date",
        "2026-01-01",
        "--medium",
        "cinema",
    ]
    first = runner.invoke(app, common)
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, common)

    assert second.exit_code != 0
    assert "duplicate" in second.output.lower()
    store = _store(config_path)
    assert len(store.list_entries()) == 1
    store.close()


def test_log_duplicate_with_force_is_persisted(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    common = [
        "--config",
        str(config_path),
        "log",
        "--title",
        "Solstice Run",
        "--date",
        "2026-01-01",
        "--medium",
        "cinema",
    ]
    first = runner.invoke(app, common)
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, [*common, "--force"])

    assert second.exit_code == 0, second.output
    store = _store(config_path)
    assert len(store.list_entries()) == 2
    store.close()


def test_log_fetches_omdb_ratings(
    config_path: Path, calendar: FakeCalendar, omdb_match: None
) -> None:
    result = runner.invoke(
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
        ],
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating == "8.5/10"
    store.close()


def test_log_sync_failure_still_persists_the_entry(config_path: Path, no_omdb_match: None) -> None:
    result = runner.invoke(
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
        ],
    )

    assert result.exit_code == 0, result.output
    assert "calendar" in result.output.lower()
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is None
    store.close()


# --- list ---


def test_list_shows_logged_entries(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    runner.invoke(
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

    result = runner.invoke(app, ["--config", str(config_path), "list"])

    assert result.exit_code == 0, result.output
    assert "Dune" in result.output
    assert "cinema" in result.output
    assert "Grand Vista Cinema" in result.output


# --- init ---


def test_init_writes_a_starter_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["--config", str(config_path), "init"])

    assert result.exit_code == 0, result.output
    assert config_path.is_file()
    loaded = config_module.load_config(config_path)
    assert loaded.caldav_url
    assert loaded.omdb_api_key


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    result = runner.invoke(app, ["--config", str(config_path), "init"])

    assert result.exit_code != 0
    assert config_path.read_text() == "existing content"


def test_init_force_overwrites(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    result = runner.invoke(app, ["--config", str(config_path), "init", "--force"])

    assert result.exit_code == 0, result.output
    assert config_path.read_text() != "existing content"


def test_missing_config_non_interactively_points_at_init(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["--config", str(config_path), "list"])

    assert result.exit_code != 0
    assert "movie-planner init" in result.output


def test_missing_config_interactively_offers_to_create_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("movie_planner.cli._is_interactive", lambda: True)

    result = runner.invoke(app, ["--config", str(config_path), "list"], input="y\n")

    assert result.exit_code != 0
    assert config_path.is_file()
    assert "wrote a starter config" in result.output.lower()


def test_missing_config_interactively_declined_does_not_write_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("movie_planner.cli._is_interactive", lambda: True)

    result = runner.invoke(app, ["--config", str(config_path), "list"], input="n\n")

    assert result.exit_code != 0
    assert not config_path.is_file()


# --- error paths ---


def test_log_without_title_fails_non_interactively(
    config_path: Path, calendar: FakeCalendar
) -> None:
    result = runner.invoke(
        app, ["--config", str(config_path), "log", "--date", "2026-01-01", "--medium", "cinema"]
    )

    assert result.exit_code != 0
    assert "title is required" in result.output.lower()


def test_log_with_invalid_date_fails(config_path: Path, calendar: FakeCalendar) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "log",
            "--title",
            "Dune",
            "--date",
            "not-a-date",
            "--medium",
            "cinema",
        ],
    )

    assert result.exit_code != 0
    assert "not a valid date" in result.output.lower()


def test_update_unknown_entry_fails(config_path: Path) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "update", "999", "--title", "X"])

    assert result.exit_code != 0
    assert "999" in result.output


def test_delete_unknown_entry_fails(config_path: Path) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "delete", "999"])

    assert result.exit_code != 0
    assert "999" in result.output


def test_locations_media_add_duplicate_fails(config_path: Path) -> None:
    runner.invoke(app, ["--config", str(config_path), "locations", "media", "add", "cinema"])

    result = runner.invoke(
        app, ["--config", str(config_path), "locations", "media", "add", "cinema"]
    )

    assert result.exit_code != 0
    assert "cinema" in result.output.lower()


def test_locations_venues_remove_unknown_fails(config_path: Path) -> None:
    result = runner.invoke(
        app, ["--config", str(config_path), "locations", "venues", "remove", "Nowhere"]
    )

    assert result.exit_code != 0
    assert "nowhere" in result.output.lower()


def test_import_unsupported_file_type_fails(config_path: Path, tmp_path: Path) -> None:
    bad_path = tmp_path / "movies.txt"
    bad_path.write_text("not a csv or json")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(bad_path)])

    assert result.exit_code != 0
    assert "unsupported" in result.output.lower()


# --- update / delete: task 7.2 ---


def test_update_changes_entry_and_propagates_to_calendar(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    runner.invoke(
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
        ],
    )
    store = _store(config_path)
    (entry,) = store.list_entries()
    store.close()

    result = runner.invoke(
        app,
        ["--config", str(config_path), "update", str(entry.id), "--title", "Dune Part Two"],
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    updated = store.get_entry(entry.id)
    assert updated.title == "Dune Part Two"
    assert updated.caldav_uid is not None
    assert "Dune Part Two" in calendar.events_by_uid[updated.caldav_uid].data
    store.close()


def test_delete_removes_entry_and_calendar_event(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    runner.invoke(
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
        ],
    )
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is not None
    uid = entry.caldav_uid
    store.close()

    result = runner.invoke(app, ["--config", str(config_path), "delete", str(entry.id)])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    assert store.list_entries() == []
    assert calendar.events_by_uid[uid].deleted is True
    store.close()


# --- locations ---


def test_locations_media_add_list_remove(config_path: Path) -> None:
    add = runner.invoke(
        app, ["--config", str(config_path), "locations", "media", "add", "cinema", "--physical"]
    )
    assert add.exit_code == 0, add.output

    listing = runner.invoke(app, ["--config", str(config_path), "locations", "media", "list"])
    assert "cinema" in listing.output

    remove = runner.invoke(
        app, ["--config", str(config_path), "locations", "media", "remove", "cinema"]
    )
    assert remove.exit_code == 0, remove.output
    listing_after = runner.invoke(app, ["--config", str(config_path), "locations", "media", "list"])
    assert "cinema" not in listing_after.output


def test_locations_venues_add_list_remove(config_path: Path) -> None:
    add = runner.invoke(
        app, ["--config", str(config_path), "locations", "venues", "add", "Grand Vista"]
    )
    assert add.exit_code == 0, add.output

    listing = runner.invoke(app, ["--config", str(config_path), "locations", "venues", "list"])
    assert "Grand Vista" in listing.output

    remove = runner.invoke(
        app, ["--config", str(config_path), "locations", "venues", "remove", "Grand Vista"]
    )
    assert remove.exit_code == 0, remove.output


def test_locations_remove_medium_in_use_is_rejected(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    runner.invoke(
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
        ],
    )

    result = runner.invoke(
        app, ["--config", str(config_path), "locations", "media", "remove", "cinema"]
    )

    assert result.exit_code != 0
    assert "cinema" in result.output.lower()


# --- import: tasks 3.4, 7.1, 7.3 ---


def test_import_csv_persists_rows_and_syncs_to_calendar(
    config_path: Path, calendar: FakeCalendar, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text(
        "title,date,start_time,end_time,medium,venue,imdb_url\n"
        "Dune,2026-01-01,,,cinema,Grand Vista Cinema,\n"
    )

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    assert "1 imported" in result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid in calendar.events_by_uid
    store.close()


def test_import_csv_fetches_omdb_ratings(
    config_path: Path, calendar: FakeCalendar, omdb_match: None, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,2026-01-01,cinema\n")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating == "8.5/10"
    store.close()


def test_import_no_metadata_skips_omdb(
    config_path: Path, calendar: FakeCalendar, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def lookup(self: OmdbClient, **kw: object) -> MovieRatings | None:
        calls["n"] += 1
        return MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80")

    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lookup)
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,2026-01-01,cinema\n")

    result = runner.invoke(
        app, ["--config", str(config_path), "import", str(csv_path), "--no-metadata"]
    )

    assert result.exit_code == 0, result.output
    assert calls["n"] == 0
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating is None
    assert entry.caldav_uid is not None
    store.close()


def test_import_reports_skipped_duplicates_in_summary(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    runner.invoke(
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
        ],
    )
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,2026-01-01,cinema\n")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    assert "1 skipped" in result.output
    store = _store(config_path)
    assert len(store.list_entries()) == 1
    store.close()


def test_import_force_persists_duplicates(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    runner.invoke(
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
        ],
    )
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,2026-01-01,cinema\n")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path), "--force"])

    assert result.exit_code == 0, result.output
    assert "1 imported" in result.output
    store = _store(config_path)
    assert len(store.list_entries()) == 2
    store.close()


# --- from-pathe-email: tasks 5.1-5.4 ---


def test_from_pathe_email_via_file_creates_new_entry(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    email_path = tmp_path / "ticket.eml"
    email_path.write_text(PATHE_EMAIL_PLAIN)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(email_path)], input="y\n"
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.title == "The Dog Stars"
    assert entry.booking_ref == PATHE_BOOKING_REF
    assert entry.caldav_uid in calendar.events_by_uid
    store.close()


def test_from_pathe_email_via_stdin_uses_tty_confirmation(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("movie_planner.cli._confirm_via_tty", lambda message: True)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email"], input=PATHE_EMAIL_PLAIN
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.booking_ref == PATHE_BOOKING_REF
    store.close()


def test_from_pathe_email_declined_confirmation_creates_nothing(
    config_path: Path, calendar: FakeCalendar, tmp_path: Path
) -> None:
    email_path = tmp_path / "ticket.eml"
    email_path.write_text(PATHE_EMAIL_PLAIN)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(email_path)], input="n\n"
    )

    assert result.exit_code != 0
    store = _store(config_path)
    assert store.list_entries() == []
    store.close()


def test_from_pathe_email_yes_flag_skips_confirmation(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    email_path = tmp_path / "ticket.eml"
    email_path.write_text(PATHE_EMAIL_PLAIN)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(email_path), "--yes"]
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    assert len(store.list_entries()) == 1
    store.close()


def test_from_pathe_email_matches_by_booking_ref_updates_existing(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    first_path = tmp_path / "first.eml"
    first_path.write_text(PATHE_EMAIL_PLAIN)
    runner.invoke(app, ["--config", str(config_path), "from-pathe-email", str(first_path), "--yes"])

    rescheduled = PATHE_EMAIL_PLAIN.replace(
        "Saturday 29/08/26, 12:40 Expected to end at 14:58",
        "Saturday 29/08/26, 15:00 Expected to end at 17:18",
    )
    second_path = tmp_path / "second.eml"
    second_path.write_text(rescheduled)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(second_path), "--yes"]
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.start_time == time(15, 0)
    assert entry.booking_ref == PATHE_BOOKING_REF
    store.close()


def test_from_pathe_email_falls_back_to_fuzzy_match(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "log",
            "--title",
            "The Dog Stars",
            "--date",
            "2026-08-29",
            "--medium",
            "cinema",
        ],
    )
    email_path = tmp_path / "ticket.eml"
    email_path.write_text(PATHE_EMAIL_PLAIN)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(email_path), "--yes"]
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    assert len(store.list_entries()) == 1  # attached, not duplicated
    (entry,) = store.list_entries()
    assert entry.booking_ref == PATHE_BOOKING_REF
    store.close()


def test_from_pathe_email_parse_failure_reports_error(config_path: Path, tmp_path: Path) -> None:
    bad_path = tmp_path / "garbage.eml"
    bad_path.write_text("this is not a Pathé booking confirmation at all")

    result = runner.invoke(app, ["--config", str(config_path), "from-pathe-email", str(bad_path)])

    assert result.exit_code != 0
    store = _store(config_path)
    assert store.list_entries() == []
    store.close()


def test_from_pathe_email_fetches_omdb_ratings(
    config_path: Path, calendar: FakeCalendar, omdb_match: None, tmp_path: Path
) -> None:
    email_path = tmp_path / "ticket.eml"
    email_path.write_text(PATHE_EMAIL_PLAIN)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(email_path), "--yes"]
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating == "8.5/10"
    store.close()


def test_from_pathe_email_description_includes_screening_details(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    email_path = tmp_path / "ticket.eml"
    email_path.write_text(PATHE_EMAIL_PLAIN)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(email_path), "--yes"]
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is not None
    assert "Auditorium 1 DOLBY - Row 5 Seat 17" in calendar.events_by_uid[entry.caldav_uid].data
    store.close()


# --- sync retry ---


def test_sync_retry_pushes_unsynced_entries(config_path: Path, no_omdb_match: None) -> None:
    runner.invoke(
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
        ],
    )
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is None  # no calendar reachable during log
    store.close()

    fake = FakeCalendar()
    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(CalendarClient, "connect", classmethod(lambda cls, **kw: CalendarClient(fake)))
        result = runner.invoke(app, ["--config", str(config_path), "sync", "retry"])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (retried,) = store.list_entries()
    assert retried.caldav_uid is not None
    assert retried.caldav_uid in fake.events_by_uid
    store.close()


# --- sync refresh: tasks 6.1, 6.2 ---


def test_refresh_backfills_missing_ratings_and_pushes(
    config_path: Path, calendar: FakeCalendar, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: None)
    runner.invoke(
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
        ],
    )
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating is None
    store.close()

    calls = {"n": 0}

    def lookup(self: OmdbClient, **kw: object) -> MovieRatings:
        calls["n"] += 1
        return MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80")

    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lookup)

    result = runner.invoke(app, ["--config", str(config_path), "sync", "refresh"])

    assert result.exit_code == 0, result.output
    assert calls["n"] == 1
    store = _store(config_path)
    (refreshed,) = store.list_entries()
    assert refreshed.imdb_rating == "8.5/10"
    assert refreshed.caldav_uid is not None
    assert "IMDb: 8.5/10" in calendar.events_by_uid[refreshed.caldav_uid].data
    store.close()


def test_refresh_does_not_refetch_entries_that_already_have_ratings(
    config_path: Path, calendar: FakeCalendar, omdb_match: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(
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
        ],
    )
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating == "8.5/10"
    store.close()

    calls = {"n": 0}

    def lookup(self: OmdbClient, **kw: object) -> MovieRatings:
        calls["n"] += 1
        return MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80")

    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lookup)

    result = runner.invoke(app, ["--config", str(config_path), "sync", "refresh"])

    assert result.exit_code == 0, result.output
    assert calls["n"] == 0


def test_refresh_force_refetches_entries_that_already_have_ratings(
    config_path: Path, calendar: FakeCalendar, omdb_match: None
) -> None:
    runner.invoke(
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
        ],
    )
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating == "8.5/10"
    store.close()

    calls = {"n": 0}

    def lookup(self: OmdbClient, **kw: object) -> MovieRatings:
        calls["n"] += 1
        return MovieRatings(imdb="9.0/10", rotten_tomatoes="91%", metacritic="80")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lookup)
        result = runner.invoke(app, ["--config", str(config_path), "sync", "refresh", "--force"])

    assert result.exit_code == 0, result.output
    assert calls["n"] == 1
    assert "1 metadata fetches" in result.output
    store = _store(config_path)
    (refreshed,) = store.list_entries()
    assert refreshed.imdb_rating == "9.0/10"
    store.close()


def test_refresh_force_respects_date_scoping(
    config_path: Path, calendar: FakeCalendar, omdb_match: None
) -> None:
    _log(config_path, "In Range", "2026-01-15")
    _log(config_path, "Out Of Range", "2026-02-15")

    calls = {"n": 0}

    def lookup(self: OmdbClient, **kw: object) -> MovieRatings:
        calls["n"] += 1
        return MovieRatings(imdb="9.0/10", rotten_tomatoes="91%", metacritic="80")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lookup)
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "sync",
                "refresh",
                "--force",
                "--date",
                "2026-01-15",
            ],
        )

    assert result.exit_code == 0, result.output
    assert calls["n"] == 1


def test_refresh_creates_event_for_a_never_synced_entry(
    config_path: Path, no_omdb_match: None
) -> None:
    runner.invoke(
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
        ],
    )
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is None
    store.close()

    fake = FakeCalendar()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(CalendarClient, "connect", classmethod(lambda cls, **kw: CalendarClient(fake)))
        result = runner.invoke(app, ["--config", str(config_path), "sync", "refresh"])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    assert store.get_entry(entry.id).caldav_uid is not None
    store.close()


def test_refresh_reports_a_summary(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    runner.invoke(
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
        ],
    )

    result = runner.invoke(app, ["--config", str(config_path), "sync", "refresh"])

    assert result.exit_code == 0, result.output
    assert "1" in result.output


def test_refresh_with_no_entries_reports_nothing_to_do(config_path: Path) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "sync", "refresh"])

    assert result.exit_code == 0, result.output
    assert "no entries" in result.output.lower()


def _log(config_path: Path, title: str, entry_date: str) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "log",
            "--title",
            title,
            "--date",
            entry_date,
            "--medium",
            "cinema",
        ],
    )
    assert result.exit_code == 0, result.output


def test_refresh_from_and_to_only_touches_entries_in_range(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Before", "2025-12-31")
    _log(config_path, "Dune", "2026-01-15")
    _log(config_path, "After", "2026-02-01")

    calls = {"n": 0}

    def lookup(self: OmdbClient, **kw: object) -> MovieRatings | None:
        calls["n"] += 1
        return None

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lookup)
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "sync",
                "refresh",
                "--from",
                "2026-01-01",
                "--to",
                "2026-01-31",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Refreshed 1 " in result.output
    assert calls["n"] == 1


def test_refresh_date_only_touches_that_single_day(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Dune", "2026-01-15")
    _log(config_path, "Other Day", "2026-01-16")

    calls = {"n": 0}

    def lookup(self: OmdbClient, **kw: object) -> MovieRatings | None:
        calls["n"] += 1
        return None

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lookup)
        result = runner.invoke(
            app,
            ["--config", str(config_path), "sync", "refresh", "--date", "2026-01-15"],
        )

    assert result.exit_code == 0, result.output
    assert "Refreshed 1 " in result.output
    assert calls["n"] == 1


def test_refresh_date_combined_with_from_is_rejected(config_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "sync",
            "refresh",
            "--date",
            "2026-01-15",
            "--from",
            "2026-01-01",
        ],
    )

    assert result.exit_code != 0
    assert "--date" in result.output


def test_refresh_date_combined_with_to_is_rejected(config_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "sync",
            "refresh",
            "--date",
            "2026-01-15",
            "--to",
            "2026-01-31",
        ],
    )

    assert result.exit_code != 0
    assert "--date" in result.output


def test_refresh_range_with_no_matching_entries_reports_nothing_to_do(
    config_path: Path,
) -> None:
    _log(config_path, "Dune", "2026-01-15")

    result = runner.invoke(
        app,
        ["--config", str(config_path), "sync", "refresh", "--date", "2026-06-01"],
    )

    assert result.exit_code == 0, result.output
    assert "no entries" in result.output.lower()


# --- config overrides: flags and env vars take precedence over the config
# file (rules/cli.md), except the CalDAV password, which never gets an
# override surface (kept config-file-only) ---


def test_db_path_flag_overrides_config_file(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    override_db_path = tmp_path / "override.db"

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--db-path",
            str(override_db_path),
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

    assert result.exit_code == 0, result.output
    store = Store(override_db_path)
    (entry,) = store.list_entries()
    assert entry.title == "Dune"
    store.close()


def test_db_path_env_var_overrides_config_file(
    config_path: Path,
    calendar: FakeCalendar,
    no_omdb_match: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_db_path = tmp_path / "override.db"
    monkeypatch.setenv("MOVIE_PLANNER_DB_PATH", str(override_db_path))

    result = runner.invoke(
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

    assert result.exit_code == 0, result.output
    store = Store(override_db_path)
    (entry,) = store.list_entries()
    assert entry.title == "Dune"
    store.close()


def test_caldav_url_flag_overrides_config_file(
    config_path: Path, no_omdb_match: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    def fake_connect(cls: type[CalendarClient], /, **kw: str) -> CalendarClient:
        captured.update(kw)
        return CalendarClient(FakeCalendar())

    monkeypatch.setattr(CalendarClient, "connect", classmethod(fake_connect))

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--caldav-url",
            "https://override.example.com/calendars/movies/",
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

    assert result.exit_code == 0, result.output
    assert captured["url"] == "https://override.example.com/calendars/movies/"


def test_omdb_api_key_flag_overrides_config_file(
    config_path: Path, calendar: FakeCalendar, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}
    original_init = OmdbClient.__init__

    def capturing_init(
        self: OmdbClient, api_key: str, http_client: httpx.Client | None = None
    ) -> None:
        captured["api_key"] = api_key
        original_init(self, api_key, http_client)

    monkeypatch.setattr(OmdbClient, "__init__", capturing_init)
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: None)

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--omdb-api-key",
            "override-key",
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

    assert result.exit_code == 0, result.output
    assert captured["api_key"] == "override-key"


def test_no_flag_or_env_override_exists_for_the_caldav_password() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "--caldav-password" not in result.output
