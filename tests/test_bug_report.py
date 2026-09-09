from datetime import date
from pathlib import Path

from movie_planner.bug_report import build_bug_report
from movie_planner.config import Config
from movie_planner.store import Store


def _cfg(db_path: Path, *, tmdb_api_key: str | None = None) -> Config:
    return Config(
        caldav_url="https://baikal.example.com/calendars/movies/",
        caldav_username="moviewatcher",
        caldav_password="super-secret-password",
        omdb_api_key="omdb-secret-key",
        db_path=db_path,
        tmdb_api_key=tmdb_api_key,
    )


def _store(tmp_path: Path) -> Store:
    return Store(tmp_path / "movies.db")


def test_never_includes_secret_config_values(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path / "movies.db", tmdb_api_key="tmdb-secret-key")
    store = _store(tmp_path)

    report = build_bug_report(cfg, store)

    assert "super-secret-password" not in report
    assert "moviewatcher" not in report
    assert "omdb-secret-key" not in report
    assert "tmdb-secret-key" not in report
    assert cfg.caldav_url not in report


def test_never_includes_entry_titles_notes_or_venue_names(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path / "movies.db")
    store = _store(tmp_path)
    medium = store.add_medium("cinema", is_physical_place=True)
    venue = store.add_venue("A Very Specific Local Cinema")
    store.create_entry(
        title="A Very Personal Movie Title",
        date=date(2026, 1, 1),
        medium_id=medium.id,
        venue_id=venue.id,
    )
    store.update_entry(1, notes="watched with someone specific")

    report = build_bug_report(cfg, store)

    assert "A Very Personal Movie Title" not in report
    assert "A Very Specific Local Cinema" not in report
    assert "watched with someone specific" not in report


def test_reports_environment_and_config_shape(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path / "movies.db")
    store = _store(tmp_path)

    report = build_bug_report(cfg, store)

    assert "movie-planner:" in report
    assert "Python:" in report
    assert "caldav: configured" in report
    assert "omdb: configured" in report
    assert "tmdb: not configured" in report


def test_reports_tmdb_configured_when_key_present(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path / "movies.db", tmdb_api_key="tmdb-secret-key")
    store = _store(tmp_path)

    report = build_bug_report(cfg, store)

    assert "tmdb: configured" in report
    assert "tmdb: not configured" not in report


def test_reports_store_counts_not_content(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path / "movies.db")
    store = _store(tmp_path)
    medium = store.add_medium("cinema", is_physical_place=True)
    store.add_venue("Some Cinema")
    store.create_entry(title="Movie One", date=date(2026, 1, 1), medium_id=medium.id)
    store.create_entry(title="Movie Two", date=date(2026, 2, 1), medium_id=medium.id)

    report = build_bug_report(cfg, store)

    assert "entries: 2" in report
    assert "venues: 1" in report
    assert "2026-01-01" in report
    assert "2026-02-01" in report


def test_reports_activity_log_action_counts(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path / "movies.db")
    store = _store(tmp_path)
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Movie One", date=date(2026, 1, 1), medium_id=medium.id)
    store.update_entry(1, title="Movie One (updated)")
    store.delete_entry(1)

    report = build_bug_report(cfg, store)

    assert "create: 1" in report
    assert "update: 1" in report
    assert "delete: 1" in report
    assert "Movie One" not in report
