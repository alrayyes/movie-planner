from collections.abc import Iterator
from datetime import date, time
from pathlib import Path

import pytest

from movie_planner.store import Store, StoreError


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "movies.db")
    yield s
    s.close()


def test_init_creates_all_tables_on_first_run(tmp_path: Path) -> None:
    db_path = tmp_path / "movies.db"

    Store(db_path).close()

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        conn.close()
    assert {"entries", "media", "venues"} <= tables


def test_add_and_list_media(store: Store) -> None:
    store.add_medium("cinema", is_physical_place=True)
    store.add_medium("netflix", is_physical_place=False)

    media = store.list_media()

    assert [m.name for m in media] == ["cinema", "netflix"]
    assert next(m for m in media if m.name == "cinema").is_physical_place is True
    assert next(m for m in media if m.name == "netflix").is_physical_place is False


def test_add_duplicate_medium_rejected(store: Store) -> None:
    store.add_medium("cinema", is_physical_place=True)

    with pytest.raises(StoreError, match="cinema"):
        store.add_medium("cinema", is_physical_place=True)


def test_remove_medium_not_in_use(store: Store) -> None:
    store.add_medium("netflix", is_physical_place=False)

    store.remove_medium("netflix")

    assert store.list_media() == []


def test_remove_unknown_medium_raises(store: Store) -> None:
    with pytest.raises(StoreError, match="netflix"):
        store.remove_medium("netflix")


def test_remove_medium_in_use_is_rejected(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    with pytest.raises(StoreError, match="cinema"):
        store.remove_medium("cinema")

    assert store.list_media() == [medium]


def test_add_and_list_venues(store: Store) -> None:
    store.add_venue("Tuschinski")
    store.add_venue("City")

    assert [v.name for v in store.list_venues()] == ["City", "Tuschinski"]


def test_add_duplicate_venue_rejected(store: Store) -> None:
    store.add_venue("Tuschinski")

    with pytest.raises(StoreError, match="Tuschinski"):
        store.add_venue("Tuschinski")


def test_remove_unknown_venue_raises(store: Store) -> None:
    with pytest.raises(StoreError, match="Tuschinski"):
        store.remove_venue("Tuschinski")


def test_remove_venue_not_in_use(store: Store) -> None:
    store.add_venue("Tuschinski")

    store.remove_venue("Tuschinski")

    assert store.list_venues() == []


def test_remove_venue_in_use_is_rejected(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    venue = store.add_venue("Tuschinski")
    store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id, venue_id=venue.id)

    with pytest.raises(StoreError, match="Tuschinski"):
        store.remove_venue("Tuschinski")


def test_create_entry_with_full_time_range(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    venue = store.add_venue("Tuschinski")

    entry = store.create_entry(
        title="The Housemaid",
        date=date(2026, 1, 3),
        start_time=time(14, 0),
        end_time=time(16, 32),
        medium_id=medium.id,
        venue_id=venue.id,
    )

    assert entry.title == "The Housemaid"
    assert entry.start_time == time(14, 0)
    assert entry.end_time == time(16, 32)
    assert entry.venue_id == venue.id


def test_create_entry_with_unknown_times(store: Store) -> None:
    medium = store.add_medium("netflix", is_physical_place=False)

    entry = store.create_entry(
        title="Louis Theroux: Inside the Manosphere", date=date(2026, 3, 14), medium_id=medium.id
    )

    assert entry.start_time is None
    assert entry.end_time is None
    assert entry.venue_id is None


def test_non_physical_medium_allows_no_venue(store: Store) -> None:
    medium = store.add_medium("netflix", is_physical_place=False)

    entry = store.create_entry(title="A show", date=date(2026, 1, 1), medium_id=medium.id)

    assert medium.is_physical_place is False
    assert entry.venue_id is None


def test_new_entry_has_no_caldav_uid(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    assert entry.caldav_uid is None


def test_update_entry_sets_caldav_uid(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    updated = store.update_entry(entry.id, caldav_uid="abc-123")

    assert updated.caldav_uid == "abc-123"
    assert store.get_entry(entry.id).caldav_uid == "abc-123"


def test_migrates_a_database_created_before_caldav_uid_existed(tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "movies.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE media (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            is_physical_place INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE venues (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL,
            start_time TEXT, end_time TEXT,
            medium_id INTEGER NOT NULL REFERENCES media(id),
            venue_id INTEGER REFERENCES venues(id)
        );
        """
    )
    conn.commit()
    conn.close()

    s = Store(db_path)
    try:
        medium = s.add_medium("cinema", is_physical_place=True)
        entry = s.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
        assert entry.caldav_uid is None
    finally:
        s.close()


def test_list_entries_ordered_by_date(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Second", date=date(2026, 2, 1), medium_id=medium.id)
    store.create_entry(title="First", date=date(2026, 1, 1), medium_id=medium.id)

    entries = store.list_entries()

    assert [e.title for e in entries] == ["First", "Second"]


def test_list_entries_filtered_by_date_range(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="January", date=date(2026, 1, 15), medium_id=medium.id)
    store.create_entry(title="March", date=date(2026, 3, 15), medium_id=medium.id)

    entries = store.list_entries(date_from=date(2026, 2, 1), date_to=date(2026, 4, 1))

    assert [e.title for e in entries] == ["March"]


def test_list_entries_filtered_by_medium(store: Store) -> None:
    cinema = store.add_medium("cinema", is_physical_place=True)
    netflix = store.add_medium("netflix", is_physical_place=False)
    store.create_entry(title="Cinema movie", date=date(2026, 1, 1), medium_id=cinema.id)
    store.create_entry(title="Netflix movie", date=date(2026, 1, 1), medium_id=netflix.id)

    entries = store.list_entries(medium_id=cinema.id)

    assert [e.title for e in entries] == ["Cinema movie"]


def test_update_entry_changes_the_stored_date(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    updated = store.update_entry(entry.id, date=date(2026, 1, 2))

    assert updated.date == date(2026, 1, 2)
    assert store.get_entry(entry.id).date == date(2026, 1, 2)


def test_update_entry_leaves_unspecified_fields_alone(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune", date=date(2026, 1, 1), start_time=time(14, 0), medium_id=medium.id
    )

    updated = store.update_entry(entry.id, title="Dune Part Two")

    assert updated.title == "Dune Part Two"
    assert updated.start_time == time(14, 0)


def test_delete_entry_removes_it_from_list(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    store.delete_entry(entry.id)

    assert store.list_entries() == []


def test_delete_unknown_entry_raises(store: Store) -> None:
    with pytest.raises(StoreError, match="123"):
        store.delete_entry(123)


def test_get_unknown_entry_raises(store: Store) -> None:
    with pytest.raises(StoreError, match="123"):
        store.get_entry(123)


def test_new_entry_has_no_metadata(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    assert entry.imdb_rating is None
    assert entry.rotten_tomatoes_rating is None
    assert entry.metacritic_rating is None
    assert entry.letterboxd_url is None
    assert entry.letterboxd_rating is None


def test_update_entry_sets_omdb_ratings(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    updated = store.update_entry(
        entry.id,
        imdb_rating="8.5/10",
        rotten_tomatoes_rating="94%",
        metacritic_rating="82/100",
    )

    assert updated.imdb_rating == "8.5/10"
    assert updated.rotten_tomatoes_rating == "94%"
    assert updated.metacritic_rating == "82/100"
    reloaded = store.get_entry(entry.id)
    assert reloaded.imdb_rating == "8.5/10"


def test_update_entry_sets_letterboxd_link_and_rating(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)

    updated = store.update_entry(
        entry.id,
        letterboxd_url="https://letterboxd.com/film/dune-2021/",
        letterboxd_rating="4.5",
    )

    assert updated.letterboxd_url == "https://letterboxd.com/film/dune-2021/"
    assert updated.letterboxd_rating == "4.5"


def test_close_does_not_raise(store: Store) -> None:
    store.close()
