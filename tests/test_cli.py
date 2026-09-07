from datetime import date, time
from pathlib import Path

import httpx
import icalendar
import pytest
from fakes import FakeCalendar
from fixtures import PATHE_BOOKING_REF, PATHE_EMAIL_PLAIN
from typer.testing import CliRunner

from movie_planner import config as config_module
from movie_planner.calendar_sync import CalendarClient, build_vevent
from movie_planner.cli import app
from movie_planner.omdb import MovieRatings, OmdbClient
from movie_planner.store import Store
from movie_planner.tmdb import TmdbClient

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
def config_path_with_tmdb(tmp_path: Path) -> Path:
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

        [tmdb]
        api_key = "test-tmdb-key"

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
    # Includes a poster, same as a real OMDb match would - a fixture
    # missing one made a fully-enriched entry look incomplete to
    # needs_omdb_fetch, breaking any test that logs via this fixture
    # then asserts a later refresh doesn't re-fetch it.
    ratings = MovieRatings(
        imdb="8.5/10",
        rotten_tomatoes="91%",
        metacritic="80",
        poster="https://m.media-amazon.com/images/dune-poster.jpg",
        director="Denis Villeneuve",
        actors="Timothée Chalamet, Rebecca Ferguson, Zendaya",
        genre="Action, Adventure, Drama",
        release_year=2021,
    )
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: ratings)


@pytest.fixture
def omdb_match_with_imdb_id(monkeypatch: pytest.MonkeyPatch) -> None:
    # A match that also carries imdb_id (real OMDb matches always do) -
    # this is what builds entry.imdb_url, which trailer lookup then reads
    # the imdb_id back out of (movie-planner#236).
    ratings = MovieRatings(
        imdb="8.5/10",
        rotten_tomatoes="91%",
        metacritic="80",
        imdb_id="tt1160419",
        poster="https://m.media-amazon.com/images/dune-poster.jpg",
        director="Denis Villeneuve",
        actors="Timothée Chalamet, Rebecca Ferguson, Zendaya",
        genre="Action, Adventure, Drama",
        release_year=2021,
    )
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


def test_log_pushes_a_known_venues_chain_and_location(
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
            "Tuschinski",
        ],
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "LOCATION:Tuschinski\\, Amsterdam\\, Netherlands" in ical_text
    assert "Chain: Pathé" in ical_text
    store.close()


def test_log_pushes_a_known_venues_geo_coordinates(
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
            "Tuschinski",
        ],
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "GEO:52.3665062;4.8947073" in ical_text
    store.close()


def test_log_venue_with_no_known_coordinates_omits_geo(
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
    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "GEO:" not in ical_text
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


def test_log_overlapping_screening_without_force_is_rejected_regardless_of_title(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    first = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "log",
            "--title",
            "Solstice Run",
            "--date",
            "2026-01-01",
            "--start-time",
            "19:00",
            "--end-time",
            "21:00",
            "--medium",
            "cinema",
        ],
    )
    assert first.exit_code == 0, first.output

    second = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "log",
            "--title",
            "A Completely Different Film",
            "--date",
            "2026-01-01",
            "--start-time",
            "19:30",
            "--end-time",
            "21:30",
            "--medium",
            "cinema",
        ],
    )

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


def test_log_stores_notes(config_path: Path, calendar: FakeCalendar, no_omdb_match: None) -> None:
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
            "--notes",
            "Enjoyed the soundtrack",
        ],
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.notes == "Enjoyed the soundtrack"
    store.close()


def test_update_sets_notes(config_path: Path, calendar: FakeCalendar, no_omdb_match: None) -> None:
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
        app, ["--config", str(config_path), "update", "1", "--notes", "Went with a friend"]
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.notes == "Went with a friend"
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


def test_list_shows_release_year_when_known(
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

    result = runner.invoke(app, ["--config", str(config_path), "list"])

    assert result.exit_code == 0, result.output
    assert "(2021)" in result.output


def test_list_filtered_by_chain(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Dune", "2026-01-01", venue="Tuschinski")
    _log(config_path, "Solstice Run", "2026-01-02", venue="Eye")

    result = runner.invoke(app, ["--config", str(config_path), "list", "--chain", "Pathé"])

    assert result.exit_code == 0, result.output
    assert "Dune" in result.output
    assert "Solstice Run" not in result.output


def test_list_limit_shows_only_the_most_recent_n(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Dune", "2026-01-01")
    _log(config_path, "Arrival", "2026-01-02")
    _log(config_path, "Solstice Run", "2026-01-03")

    result = runner.invoke(app, ["--config", str(config_path), "list", "--limit", "2"])

    assert result.exit_code == 0, result.output
    assert "Dune" not in result.output
    assert "Arrival" in result.output
    assert "Solstice Run" in result.output


def test_list_limit_combines_with_an_existing_filter(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Dune", "2026-01-01", venue="Tuschinski")
    _log(config_path, "Arrival", "2026-01-02", venue="Tuschinski")
    _log(config_path, "Solstice Run", "2026-01-03", venue="Eye")

    result = runner.invoke(
        app, ["--config", str(config_path), "list", "--chain", "Pathé", "--limit", "1"]
    )

    assert result.exit_code == 0, result.output
    assert "Dune" not in result.output
    assert "Arrival" in result.output
    assert "Solstice Run" not in result.output


def test_list_no_limit_keeps_full_output(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Dune", "2026-01-01")
    _log(config_path, "Arrival", "2026-01-02")

    result = runner.invoke(app, ["--config", str(config_path), "list"])

    assert result.exit_code == 0, result.output
    assert "Dune" in result.output
    assert "Arrival" in result.output


def test_list_limit_zero_or_negative_is_rejected(config_path: Path) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "list", "--limit", "0"])

    assert result.exit_code != 0


def test_list_omdb_no_match_shows_only_entries_with_no_match(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Not A Real Movie", "2026-01-01")

    result = runner.invoke(app, ["--config", str(config_path), "list", "--omdb-no-match"])

    assert result.exit_code == 0, result.output
    assert "Not A Real Movie" in result.output


def test_list_omdb_no_match_excludes_a_matched_entry(
    config_path: Path, calendar: FakeCalendar, omdb_match: None
) -> None:
    _log(config_path, "Dune", "2026-01-01")

    result = runner.invoke(app, ["--config", str(config_path), "list", "--omdb-no-match"])

    assert result.exit_code == 0, result.output
    assert "No entries." in result.output


def test_list_without_the_flag_shows_everything_regardless_of_match_state(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Not A Real Movie", "2026-01-01")

    result = runner.invoke(app, ["--config", str(config_path), "list"])

    assert result.exit_code == 0, result.output
    assert "Not A Real Movie" in result.output


def test_list_filtered_by_city_with_no_matching_venues_reports_no_entries(
    config_path: Path,
) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "list", "--city", "Nowhere"])

    assert result.exit_code == 0, result.output
    assert "no entries" in result.output.lower()


# --- show ---


def test_show_prints_structured_metadata(
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
            "--venue",
            "Grand Vista Cinema",
        ],
    )

    result = runner.invoke(app, ["--config", str(config_path), "show", "1"])

    assert result.exit_code == 0, result.output
    assert "Dune" in result.output
    assert "2026-01-01" in result.output
    assert "cinema" in result.output
    assert "Grand Vista Cinema" in result.output
    assert "8.5/10" in result.output
    assert "Denis Villeneuve" in result.output
    assert "Timothée Chalamet, Rebecca Ferguson, Zendaya" in result.output
    assert "Action, Adventure, Drama" in result.output
    assert "2021" in result.output


def test_show_missing_entry_errors(config_path: Path) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "show", "999"])

    assert result.exit_code != 0
    assert "no entry" in result.output.lower()


def test_show_with_no_terminal_protocol_skips_image(
    config_path: Path,
    calendar: FakeCalendar,
    no_omdb_match: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in ("KITTY_WINDOW_ID", "TERM", "TERM_PROGRAM"):
        monkeypatch.delenv(var, raising=False)
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

    result = runner.invoke(app, ["--config", str(config_path), "show", "1"])

    assert result.exit_code == 0, result.output
    assert "\033]1337" not in result.output
    assert "\033_G" not in result.output


def test_show_renders_poster_when_protocol_detected(
    config_path: Path,
    calendar: FakeCalendar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ratings = MovieRatings(
        imdb="8.5/10",
        rotten_tomatoes="91%",
        metacritic="80",
        imdb_id="tt1160419",
        poster="https://m.media-amazon.com/images/dune-poster.jpg",
    )
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: ratings)
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

    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    monkeypatch.setattr("movie_planner.cli._fetch_poster_bytes", lambda url: b"fake-image-bytes")

    result = runner.invoke(app, ["--config", str(config_path), "show", "1"])

    assert result.exit_code == 0, result.output
    assert "\033]1337;File=" in result.output


def test_show_uses_the_stored_poster_url_without_a_live_lookup(
    config_path: Path,
    calendar: FakeCalendar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ratings = MovieRatings(
        imdb="8.5/10",
        rotten_tomatoes="91%",
        metacritic="80",
        imdb_id="tt1160419",
        poster="https://m.media-amazon.com/images/dune-poster.jpg",
    )
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: ratings)
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

    calls = {"n": 0}

    def lookup_again(self: OmdbClient, **kw: object) -> MovieRatings:
        calls["n"] += 1
        return ratings

    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lookup_again)
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    monkeypatch.setattr("movie_planner.cli._fetch_poster_bytes", lambda url: b"fake-image-bytes")

    result = runner.invoke(app, ["--config", str(config_path), "show", "1"])

    assert result.exit_code == 0, result.output
    assert "\033]1337;File=" in result.output
    assert calls["n"] == 0


def test_show_gracefully_handles_poster_fetch_failure(
    config_path: Path,
    calendar: FakeCalendar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ratings = MovieRatings(
        imdb="8.5/10",
        rotten_tomatoes="91%",
        metacritic="80",
        imdb_id="tt1160419",
        poster="https://m.media-amazon.com/images/dune-poster.jpg",
    )
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: ratings)
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

    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")

    def raise_error(url: str) -> bytes | None:
        raise httpx.HTTPError("boom")

    monkeypatch.setattr("movie_planner.cli._fetch_poster_bytes", raise_error)

    result = runner.invoke(app, ["--config", str(config_path), "show", "1"])

    assert result.exit_code == 0, result.output
    assert "Dune" in result.output


# --- init ---

_INIT_FLAGS = [
    "--caldav-url",
    "https://baikal.example.com/dav.php/calendars/moviewatcher/movies/",
    "--caldav-username",
    "moviewatcher",
    "--omdb-api-key",
    "abc123",
]


def test_init_writes_a_starter_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["--config", str(config_path), *_INIT_FLAGS, "init"])

    assert result.exit_code == 0, result.output
    assert config_path.is_file()
    loaded = config_module.load_config(config_path)
    assert loaded.caldav_url == "https://baikal.example.com/dav.php/calendars/moviewatcher/movies/"
    assert loaded.omdb_api_key == "abc123"


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    result = runner.invoke(app, ["--config", str(config_path), *_INIT_FLAGS, "init"])

    assert result.exit_code != 0
    assert config_path.read_text() == "existing content"


def test_init_force_overwrites(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    result = runner.invoke(app, ["--config", str(config_path), *_INIT_FLAGS, "init", "--force"])

    assert result.exit_code == 0, result.output
    assert config_path.read_text() != "existing content"


def test_init_writes_the_namespaced_section(tmp_path: Path) -> None:
    # issue #157: init writes the new [movie_planner]-namespaced shape,
    # ready to share a config file with pathe-mail-import.
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["--config", str(config_path), *_INIT_FLAGS, "init"])

    assert result.exit_code == 0, result.output
    assert "[movie_planner" in config_path.read_text()


def test_init_adds_its_section_to_an_existing_shared_config_without_force(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[mail_import]\nsource = "mbox"\n')

    result = runner.invoke(app, ["--config", str(config_path), *_INIT_FLAGS, "init"])

    assert result.exit_code == 0, result.output
    text = config_path.read_text()
    assert 'source = "mbox"' in text
    loaded = config_module.load_config(config_path)
    assert loaded.caldav_url


def test_init_refuses_to_overwrite_an_existing_section_without_force(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    runner.invoke(app, ["--config", str(config_path), *_INIT_FLAGS, "init"])

    result = runner.invoke(app, ["--config", str(config_path), *_INIT_FLAGS, "init"])

    assert result.exit_code != 0


# --- init prompts interactively: issue #144 ---


def test_init_non_interactive_missing_value_fails_clearly(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(
        app, ["--config", str(config_path), "--caldav-url", "https://example.com", "init"]
    )

    assert result.exit_code != 0
    assert "--caldav-username" in result.output
    assert not config_path.exists()


def test_init_interactive_prompts_for_missing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("movie_planner.cli._is_interactive", lambda: True)

    result = runner.invoke(
        app,
        ["--config", str(config_path), "init"],
        input="https://baikal.example.com/dav.php/calendars/moviewatcher/movies/\nmoviewatcher\nabc123\n",
    )

    assert result.exit_code == 0, result.output
    loaded = config_module.load_config(config_path)
    assert loaded.caldav_url == "https://baikal.example.com/dav.php/calendars/moviewatcher/movies/"
    assert loaded.caldav_username == "moviewatcher"
    assert loaded.omdb_api_key == "abc123"


def test_init_flag_skips_the_prompt_for_that_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("movie_planner.cli._is_interactive", lambda: True)

    result = runner.invoke(
        app,
        ["--config", str(config_path), "--caldav-url", "https://example.com", "init"],
        # only username and api key are prompted for
        input="moviewatcher\nabc123\n",
    )

    assert result.exit_code == 0, result.output
    loaded = config_module.load_config(config_path)
    assert loaded.caldav_url == "https://example.com"


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
    # Names the formats the registry actually supports (issue #252) -
    # not a hardcoded ".csv or .json" string that could drift from it.
    assert ".csv" in result.output
    assert ".json" in result.output


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


def test_update_refresh_metadata_fetches_ratings_for_that_entry_alone(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    _log(config_path, "Dune", "2026-01-01")
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating is None
    store.close()

    ratings = MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: ratings)
        result = runner.invoke(
            app, ["--config", str(config_path), "update", str(entry.id), "--refresh-metadata"]
        )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    refreshed = store.get_entry(entry.id)
    assert refreshed.imdb_rating == "8.5/10"
    store.close()


def test_update_refresh_metadata_overwrites_existing_ratings(
    config_path: Path, calendar: FakeCalendar
) -> None:
    old_ratings = MovieRatings(imdb="1.0/10", rotten_tomatoes="1%", metacritic="1")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: old_ratings)
        _log(config_path, "Dune", "2026-01-01")
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating == "1.0/10"
    store.close()

    new_ratings = MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: new_ratings)
        result = runner.invoke(
            app, ["--config", str(config_path), "update", str(entry.id), "--refresh-metadata"]
        )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    refreshed = store.get_entry(entry.id)
    assert refreshed.imdb_rating == "8.5/10"
    store.close()


def test_update_refresh_metadata_leaves_sibling_entries_on_the_same_date_untouched(
    config_path: Path, calendar: FakeCalendar
) -> None:
    dune_ratings = MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: dune_ratings)
        _log(config_path, "Dune", "2026-01-01")
        _log(config_path, "Arrival", "2026-01-01")
    store = _store(config_path)
    entries = {e.title: e for e in store.list_entries()}
    dune = entries["Dune"]
    arrival = entries["Arrival"]
    store.close()

    new_ratings = MovieRatings(imdb="9.9/10", rotten_tomatoes="99%", metacritic="99")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: new_ratings)
        result = runner.invoke(
            app, ["--config", str(config_path), "update", str(dune.id), "--refresh-metadata"]
        )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    assert store.get_entry(dune.id).imdb_rating == "9.9/10"
    assert store.get_entry(arrival.id).imdb_rating == "8.5/10"
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


# --- venues merge-aliases: issue #196 ---


def test_venues_merge_aliases_dry_run_by_default_reports_without_changing(
    config_path: Path,
) -> None:
    store = _store(config_path)
    store._conn.execute("INSERT INTO venues (name) VALUES ('De Munt 4DX')")
    store._conn.commit()
    store.close()

    result = runner.invoke(
        app, ["--config", str(config_path), "locations", "venues", "merge-aliases"]
    )

    assert result.exit_code == 0, result.output
    assert "De Munt 4DX" in result.output
    assert "De Munt" in result.output
    assert "--apply" in result.output
    store = _store(config_path)
    try:
        assert [v.name for v in store.list_venues()] == ["De Munt 4DX"]
    finally:
        store.close()


def test_venues_merge_aliases_apply_actually_merges(config_path: Path) -> None:
    store = _store(config_path)
    store._conn.execute("INSERT INTO venues (name) VALUES ('De Munt 4DX')")
    store._conn.commit()
    store.close()

    result = runner.invoke(
        app, ["--config", str(config_path), "locations", "venues", "merge-aliases", "--apply"]
    )

    assert result.exit_code == 0, result.output
    assert "De Munt 4DX" in result.output
    store = _store(config_path)
    try:
        assert [v.name for v in store.list_venues()] == ["De Munt"]
    finally:
        store.close()


def test_venues_merge_aliases_with_nothing_to_merge_says_so(config_path: Path) -> None:
    result = runner.invoke(
        app, ["--config", str(config_path), "locations", "venues", "merge-aliases"]
    )

    assert result.exit_code == 0, result.output
    assert "nothing to merge" in result.output.lower()


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


def test_import_csv_persists_notes(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium,notes\nDune,2026-01-01,cinema,Enjoyed the soundtrack\n")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.notes == "Enjoyed the soundtrack"
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


def test_import_skips_omdb_lookup_when_row_supplies_every_field(
    config_path: Path, calendar: FakeCalendar, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def lookup(self: OmdbClient, **kw: object) -> MovieRatings | None:
        calls["n"] += 1
        return MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80")

    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lookup)
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text(
        "title,date,medium,imdb_rating,poster_url,director,actors,genre,release_year\n"
        "Dune,2026-01-01,cinema,8.5/10,"
        "https://m.media-amazon.com/images/dune-poster.jpg,Denis Villeneuve,"
        "Timothée Chalamet,Action,2021\n"
    )

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    assert calls["n"] == 0
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.director == "Denis Villeneuve"
    store.close()


def test_import_still_fetches_omdb_when_row_supplies_only_some_fields(
    config_path: Path, calendar: FakeCalendar, omdb_match: None, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium,director\nDune,2026-01-01,cinema,Denis Villeneuve\n")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_rating == "8.5/10"
    store.close()


def test_import_never_overwrites_an_imported_imdb_url_on_later_fetch(
    config_path: Path, calendar: FakeCalendar, omdb_match: None, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text(
        "title,date,medium,imdb_url\nDune,2026-01-01,cinema,https://www.imdb.com/title/tt-manual/\n"
    )

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.imdb_url == "https://www.imdb.com/title/tt-manual/"
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


def test_import_records_a_failure_for_a_bad_row(
    config_path: Path, calendar: FakeCalendar, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nSolstice Run,not-a-date,cinema\n")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    assert "1 failed" in result.output
    store = _store(config_path)
    (failure,) = store.list_import_failures()
    assert failure.source == str(csv_path)
    assert failure.row_number == 2
    store.close()


def test_import_failures_list_shows_a_recorded_failure(
    config_path: Path, calendar: FakeCalendar, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nSolstice Run,not-a-date,cinema\n")
    runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    result = runner.invoke(app, ["--config", str(config_path), "import-failures", "list"])

    assert result.exit_code == 0, result.output
    assert str(csv_path) in result.output
    assert "row 2" in result.output


def test_import_failures_list_empty_says_so(config_path: Path) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "import-failures", "list"])

    assert result.exit_code == 0, result.output
    assert "no import failures" in result.output.lower()


def test_import_failures_clear_removes_them(
    config_path: Path, calendar: FakeCalendar, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nSolstice Run,not-a-date,cinema\n")
    runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    result = runner.invoke(app, ["--config", str(config_path), "import-failures", "clear"])

    assert result.exit_code == 0, result.output
    assert "1" in result.output
    store = _store(config_path)
    assert store.list_import_failures() == []
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


# --- import from stdin: task 8.3 (add-imap-pathe-mail-import) ---


def test_import_from_stdin_single_object(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    row = '{"title": "Dune", "date": "2026-01-01", "medium": "cinema"}'

    result = runner.invoke(app, ["--config", str(config_path), "import"], input=row)

    assert result.exit_code == 0, result.output
    assert "1 imported" in result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.title == "Dune"
    assert entry.caldav_uid in calendar.events_by_uid
    store.close()


def test_import_from_stdin_array(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    rows = (
        '[{"title": "Dune", "date": "2026-01-01", "medium": "cinema"}, '
        '{"title": "Solstice Run", "date": "2026-01-02", "medium": "cinema"}]'
    )

    result = runner.invoke(app, ["--config", str(config_path), "import"], input=rows)

    assert result.exit_code == 0, result.output
    assert "2 imported" in result.output
    store = _store(config_path)
    assert len(store.list_entries()) == 2
    store.close()


def test_import_with_a_path_argument_does_not_read_stdin(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,2026-01-01,cinema\n")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.title == "Dune"
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
    assert entry.row == "5"
    assert entry.seat == "17"
    store.close()


def test_from_pathe_email_matching_by_booking_ref_updates_row_and_seat(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    # A re-sent confirmation (movie-planner#166's own matching logic)
    # should refresh row/seat too, same as every other Pathé-sourced
    # field already does.
    first_path = tmp_path / "first.eml"
    first_path.write_text(PATHE_EMAIL_PLAIN)
    runner.invoke(app, ["--config", str(config_path), "from-pathe-email", str(first_path), "--yes"])

    second_path = tmp_path / "second.eml"
    second_path.write_text(PATHE_EMAIL_PLAIN.replace("Row 5 Seat 17", "Row 9 Seat 3"))
    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(second_path), "--yes"]
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.row == "9"
    assert entry.seat == "3"
    store.close()


def test_from_pathe_email_via_file_handles_a_real_html_only_confirmation(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    # movie-planner#162: a real Pathé confirmation piped/pointed at
    # directly, with no text/plain part at all, still logs the booking
    # instead of failing on "could not find a text/plain part".
    from fixtures import PATHE_EMAIL_HTML_ONLY, PATHE_HTML_BOOKING_REF

    email_path = tmp_path / "ticket.eml"
    email_path.write_text(PATHE_EMAIL_HTML_ONLY)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(email_path)], input="y\n"
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.title == "Spider-Man: Brand New Day"
    assert entry.booking_ref == PATHE_HTML_BOOKING_REF
    store.close()


def test_from_pathe_email_via_file_handles_a_mislabeled_attachment(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    # movie-planner#193: the same bug #191 fixed in mail_import's own
    # extraction - a PDF ticket mislabeled Content-Type: text/plain by
    # Pathé's own template shouldn't be picked as the body just because
    # Content-Disposition says attachment.
    from fixtures import PATHE_EMAIL_MISLABELED_ATTACHMENT, PATHE_MISLABELED_ATTACHMENT_BOOKING_REF

    email_path = tmp_path / "ticket.eml"
    email_path.write_text(PATHE_EMAIL_MISLABELED_ATTACHMENT)

    result = runner.invoke(
        app, ["--config", str(config_path), "from-pathe-email", str(email_path)], input="y\n"
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.title == "Spider-Man: Brand New Day"
    assert entry.booking_ref == PATHE_MISLABELED_ATTACHMENT_BOOKING_REF
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
    # Parsed rather than a raw substring check on the wire text: a long
    # enough DESCRIPTION gets RFC 5545 line-folded, and where the fold
    # lands shifts with unrelated content (LOCATION length, other
    # description lines) - parsing unfolds it the same way a real
    # CalDAV client would.
    cal = icalendar.Calendar.from_ical(calendar.events_by_uid[entry.caldav_uid].data)
    (event,) = [c for c in cal.subcomponents if c.name == "VEVENT"]
    assert "Auditorium 1 DOLBY - Row 5 Seat 17" in str(event["description"])
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


def test_refresh_backfills_a_rated_entry_still_missing_its_poster(
    config_path: Path, calendar: FakeCalendar, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ratings but no poster - as if logged before poster_url existed.
    monkeypatch.setattr(
        "movie_planner.cli.OmdbClient.lookup",
        lambda self, **kw: MovieRatings(imdb="8.5/10", rotten_tomatoes="91%", metacritic="80"),
    )
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
    assert entry.poster_url is None
    store.close()

    calls = {"n": 0}

    def lookup_with_poster(self: OmdbClient, **kw: object) -> MovieRatings:
        calls["n"] += 1
        return MovieRatings(
            imdb="8.5/10",
            rotten_tomatoes="91%",
            metacritic="80",
            poster="https://m.media-amazon.com/images/dune-poster.jpg",
        )

    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lookup_with_poster)

    result = runner.invoke(app, ["--config", str(config_path), "sync", "refresh"])

    assert result.exit_code == 0, result.output
    assert calls["n"] == 1
    store = _store(config_path)
    (refreshed,) = store.list_entries()
    assert refreshed.poster_url == "https://m.media-amazon.com/images/dune-poster.jpg"
    store.close()


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


def _log(config_path: Path, title: str, entry_date: str, *, venue: str | None = None) -> None:
    args = [
        "--config",
        str(config_path),
        "log",
        "--title",
        title,
        "--date",
        entry_date,
        "--medium",
        "cinema",
    ]
    if venue:
        args += ["--venue", venue]
    result = runner.invoke(app, args)
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


def test_log_fetches_trailer_when_tmdb_configured(
    config_path_with_tmdb: Path,
    calendar: FakeCalendar,
    omdb_match_with_imdb_id: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_imdb_ids: list[str] = []

    def lookup(self: TmdbClient, *, imdb_id: str) -> str | None:
        seen_imdb_ids.append(imdb_id)
        return "https://www.youtube.com/watch?v=8g18jFHCLXk"

    monkeypatch.setattr("movie_planner.cli.TmdbClient.lookup_trailer_url", lookup)

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path_with_tmdb),
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
    assert seen_imdb_ids == ["tt1160419"]
    store = _store(config_path_with_tmdb)
    (entry,) = store.list_entries()
    assert entry.trailer_url == "https://www.youtube.com/watch?v=8g18jFHCLXk"
    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "X-TRAILER-URL:https://www.youtube.com/watch?v=8g18jFHCLXk" in ical_text
    store.close()


def test_log_skips_trailer_lookup_without_tmdb_configured(
    config_path: Path, calendar: FakeCalendar, omdb_match_with_imdb_id: None
) -> None:
    """`config_path` (unlike `config_path_with_tmdb`) has no [tmdb] section -
    trailer lookup is simply skipped, not an error, and TmdbClient is never
    even constructed.
    """
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
    assert entry.trailer_url is None
    store.close()


def test_tmdb_api_key_flag_overrides_config_file(
    config_path_with_tmdb: Path, calendar: FakeCalendar, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}
    original_init = TmdbClient.__init__

    def capturing_init(
        self: TmdbClient, api_key: str, http_client: httpx.Client | None = None
    ) -> None:
        captured["api_key"] = api_key
        original_init(self, api_key, http_client)

    monkeypatch.setattr(TmdbClient, "__init__", capturing_init)
    monkeypatch.setattr("movie_planner.cli.TmdbClient.lookup_trailer_url", lambda self, **kw: None)
    ratings = MovieRatings(imdb=None, rotten_tomatoes=None, metacritic=None, imdb_id="tt1160419")
    monkeypatch.setattr("movie_planner.cli.OmdbClient.lookup", lambda self, **kw: ratings)

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path_with_tmdb),
            "--tmdb-api-key",
            "override-tmdb-key",
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
    assert captured["api_key"] == "override-tmdb-key"


def test_no_flag_or_env_override_exists_for_the_caldav_password() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "--caldav-password" not in result.output


# --- sync pull: issue #235, task group 4 ---


def test_sync_pull_nothing_to_pull_when_calendar_matches_store(
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
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"])

    assert result.exit_code == 0, result.output
    assert "Nothing to pull" in result.output


def test_sync_pull_approved_new_candidate_creates_an_entry(
    config_path: Path, calendar: FakeCalendar
) -> None:
    ical = build_vevent(
        uid="web-uid-1",
        title="Arrival",
        entry_date=date(2026, 2, 1),
        start_time=None,
        end_time=None,
        venue="Grand Vista Cinema",
    )
    calendar.add_event(ical)

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="y\ncinema\n")

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.title == "Arrival"
    assert entry.date == date(2026, 2, 1)
    assert entry.caldav_uid == "web-uid-1"
    venue = next(v for v in store.list_venues() if v.id == entry.venue_id)
    assert venue.name == "Grand Vista Cinema"
    medium = next(m for m in store.list_media() if m.id == entry.medium_id)
    assert medium.name == "cinema"
    assert medium.is_physical_place is True
    store.close()


def test_sync_pull_new_candidate_medium_defaults_to_cinema_when_venue_present(
    config_path: Path, calendar: FakeCalendar
) -> None:
    ical = build_vevent(
        uid="web-uid-2",
        title="Arrival",
        entry_date=date(2026, 2, 1),
        start_time=None,
        end_time=None,
        venue="Grand Vista Cinema",
    )
    calendar.add_event(ical)

    # Just accepting the default ("cinema") shown on the medium prompt.
    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="y\n\n")

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    medium = next(m for m in store.list_media() if m.id == entry.medium_id)
    assert medium.name == "cinema"
    store.close()


def test_sync_pull_new_candidate_no_venue_has_no_default_medium(
    config_path: Path, calendar: FakeCalendar
) -> None:
    ical = build_vevent(
        uid="web-uid-3",
        title="Some Netflix Movie",
        entry_date=date(2026, 2, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.add_event(ical)

    result = runner.invoke(
        app, ["--config", str(config_path), "sync", "pull"], input="y\nnetflix\n"
    )

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    medium = next(m for m in store.list_media() if m.id == entry.medium_id)
    assert medium.name == "netflix"
    assert medium.is_physical_place is False
    store.close()


def test_sync_pull_declined_new_candidate_creates_nothing(
    config_path: Path, calendar: FakeCalendar
) -> None:
    ical = build_vevent(
        uid="web-uid-4",
        title="Arrival",
        entry_date=date(2026, 2, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.add_event(ical)

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="n\n")

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    assert store.list_entries() == []
    store.close()


def test_sync_pull_declined_candidate_is_offered_again_next_run(
    config_path: Path, calendar: FakeCalendar
) -> None:
    ical = build_vevent(
        uid="web-uid-5",
        title="Arrival",
        entry_date=date(2026, 2, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.add_event(ical)

    first = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="n\n")
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="n\n")

    assert second.exit_code == 0, second.output
    assert "Arrival" in second.output


def test_sync_pull_approved_changed_candidate_updates_the_entry(
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
        ],
    )
    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is not None
    uid = entry.caldav_uid
    store.close()

    # movie-planner-web edited the title directly on the calendar.
    ical = build_vevent(
        uid=uid,
        title="Dune: Part One",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.events_by_uid[uid].data = ical

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="y\n")

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (updated,) = store.list_entries()
    assert updated.title == "Dune: Part One"
    store.close()


def test_sync_pull_declined_changed_candidate_leaves_entry_unchanged(
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
        ],
    )
    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    uid = entry.caldav_uid
    assert uid is not None
    store.close()

    ical = build_vevent(
        uid=uid,
        title="Dune: Part One",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.events_by_uid[uid].data = ical

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="n\n")

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (unchanged,) = store.list_entries()
    assert unchanged.title == "Dune"
    store.close()


def test_sync_pull_missing_x_property_diff_shown_as_unknown(
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
        ],
    )
    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    uid = entry.caldav_uid
    assert uid is not None
    store.update_entry(entry.id, row="5", seat="17")
    store.close()

    # No X-ROW/X-SEAT on the re-pushed event at all.
    ical = build_vevent(
        uid=uid,
        title="Dune",
        entry_date=date(2026, 1, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.events_by_uid[uid].data = ical

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="n\n")

    assert result.exit_code == 0, result.output
    assert "unknown" in result.output.lower()
    assert "'5'" in result.output


def test_sync_pull_approved_removed_candidate_deletes_the_entry(
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
        ],
    )
    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    uid = entry.caldav_uid
    assert uid is not None
    store.close()
    del calendar.events_by_uid[uid]

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="y\n")

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    assert store.list_entries() == []
    store.close()


def test_sync_pull_declined_removed_candidate_keeps_the_entry(
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
        ],
    )
    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    uid = entry.caldav_uid
    assert uid is not None
    store.close()
    del calendar.events_by_uid[uid]

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="n\n")

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (kept,) = store.list_entries()
    assert kept.id == entry.id
    store.close()


def test_sync_pull_does_not_write_to_the_store_when_no_candidates_are_approved(
    config_path: Path, calendar: FakeCalendar
) -> None:
    ical = build_vevent(
        uid="web-uid-6",
        title="Arrival",
        entry_date=date(2026, 2, 1),
        start_time=None,
        end_time=None,
        venue=None,
    )
    calendar.add_event(ical)

    result = runner.invoke(app, ["--config", str(config_path), "sync", "pull"], input="n\n")

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    assert store.list_entries() == []
    assert store.list_venues() == []
    assert store.list_media() == []
    store.close()


def test_list_and_show_do_not_touch_the_calendar(
    config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sync pull is the only command that reads the calendar back
    (task 4.4) - `list` never even connects to it.
    """

    def fail_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("list should never connect to the calendar")

    monkeypatch.setattr(CalendarClient, "connect", classmethod(fail_connect))

    result = runner.invoke(app, ["--config", str(config_path), "list"])

    assert result.exit_code == 0, result.output


# --- X-IMPORTER/X-IMPORTER-VERSION: issue #257 ---


def test_log_stamps_x_importer_and_version(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    from importlib.metadata import version

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
    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "X-IMPORTER:log" in ical_text
    assert f"X-IMPORTER-VERSION:{version('movie-planner')}" in ical_text
    store.close()


def test_import_csv_stamps_x_importer_with_the_format(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None, tmp_path: Path
) -> None:
    csv_path = tmp_path / "movies.csv"
    csv_path.write_text("title,date,medium\nDune,2026-01-01,cinema\n")

    result = runner.invoke(app, ["--config", str(config_path), "import", str(csv_path)])

    assert result.exit_code == 0, result.output
    store = _store(config_path)
    (entry,) = store.list_entries()
    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "X-IMPORTER:import:csv" in ical_text
    store.close()


def test_update_stamps_x_importer(
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
        app, ["--config", str(config_path), "update", str(entry.id), "--title", "Dune Part Two"]
    )

    assert result.exit_code == 0, result.output
    assert entry.caldav_uid is not None
    ical_text = calendar.events_by_uid[entry.caldav_uid].data
    assert "X-IMPORTER:update" in ical_text


# --- --verbose: issue #258 ---


def test_help_documents_verbose_once_at_the_top_level() -> None:
    top_level = runner.invoke(app, ["--help"])
    subcommand = runner.invoke(app, ["log", "--help"])

    assert "--verbose" in top_level.stdout
    assert "--verbose" not in subcommand.stdout


def _log_args(config_path: Path) -> list[str]:
    return [
        "--config",
        str(config_path),
        "log",
        "--title",
        "Dune",
        "--date",
        "2026-01-01",
        "--medium",
        "cinema",
    ]


def test_verbose_does_not_change_stdout(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    plain = runner.invoke(app, _log_args(config_path))
    store = _store(config_path)
    store.delete_entry(store.list_entries()[0].id)
    store.close()

    verbose = runner.invoke(app, ["--verbose", *_log_args(config_path)])

    assert plain.exit_code == verbose.exit_code == 0
    assert plain.stdout == verbose.stdout


def test_verbose_prints_the_calendar_payload_and_duplicate_check_to_stderr(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    # OMDb/TMDb debug logging is covered directly against the real HTTP
    # layer in test_omdb.py/test_tmdb.py - the no_omdb_match fixture here
    # replaces OmdbClient.lookup wholesale, bypassing that logging, so
    # this only checks the two paths this fixture setup can actually
    # exercise: the calendar push and duplicate detection.
    result = runner.invoke(app, ["--verbose", *_log_args(config_path)])

    assert result.exit_code == 0, result.output
    assert "BEGIN:VCALENDAR" in result.stderr
    assert "no duplicate found" in result.stderr


def test_without_verbose_nothing_is_printed_to_stderr(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    result = runner.invoke(app, _log_args(config_path))

    assert result.exit_code == 0, result.output
    assert result.stderr == ""


# --- activity: issue #276 ---


def test_activity_shows_a_logged_entry(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    runner.invoke(app, _log_args(config_path))

    result = runner.invoke(app, ["--config", str(config_path), "activity"])

    assert result.exit_code == 0, result.output
    assert "create" in result.output
    assert "Dune" in result.output


def test_activity_shows_field_changes_on_an_update(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    runner.invoke(app, _log_args(config_path))
    store = _store(config_path)
    (entry,) = store.list_entries()
    store.close()

    runner.invoke(
        app, ["--config", str(config_path), "update", str(entry.id), "--title", "Dune Part Two"]
    )

    result = runner.invoke(app, ["--config", str(config_path), "activity"])

    assert result.exit_code == 0, result.output
    assert "update" in result.output
    assert "Dune" in result.output
    assert "Dune Part Two" in result.output


def test_activity_shows_a_delete(
    config_path: Path, calendar: FakeCalendar, no_omdb_match: None
) -> None:
    runner.invoke(app, _log_args(config_path))
    store = _store(config_path)
    (entry,) = store.list_entries()
    store.close()

    runner.invoke(app, ["--config", str(config_path), "delete", str(entry.id)])

    result = runner.invoke(app, ["--config", str(config_path), "activity"])

    assert result.exit_code == 0, result.output
    assert "delete" in result.output


def test_activity_empty_says_so(config_path: Path) -> None:
    result = runner.invoke(app, ["--config", str(config_path), "activity"])

    assert result.exit_code == 0, result.output
    assert "no activity" in result.output.lower()
