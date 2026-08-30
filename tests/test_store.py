from datetime import date, time
from pathlib import Path

import pytest

from movie_planner.store import Store, StoreError


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "movies.db")


def test_init_creates_all_tables_on_first_run(tmp_path: Path) -> None:
    db_path = tmp_path / "movies.db"

    Store(db_path)

    import sqlite3

    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
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
    store.add_venue("Grand Vista Cinema")
    store.add_venue("City")

    assert [v.name for v in store.list_venues()] == ["City", "Grand Vista Cinema"]


def test_add_duplicate_venue_rejected(store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    with pytest.raises(StoreError, match="Grand Vista Cinema"):
        store.add_venue("Grand Vista Cinema")


def test_remove_unknown_venue_raises(store: Store) -> None:
    with pytest.raises(StoreError, match="Grand Vista Cinema"):
        store.remove_venue("Grand Vista Cinema")


def test_remove_venue_not_in_use(store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    store.remove_venue("Grand Vista Cinema")

    assert store.list_venues() == []


def test_remove_venue_in_use_is_rejected(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    venue = store.add_venue("Grand Vista Cinema")
    store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id, venue_id=venue.id)

    with pytest.raises(StoreError, match="Grand Vista Cinema"):
        store.remove_venue("Grand Vista Cinema")


def test_create_entry_with_full_time_range(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    venue = store.add_venue("Grand Vista Cinema")

    entry = store.create_entry(
        title="The Clockmaker's Daughter",
        date=date(2026, 1, 3),
        start_time=time(14, 0),
        end_time=time(16, 32),
        medium_id=medium.id,
        venue_id=venue.id,
    )

    assert entry.title == "The Clockmaker's Daughter"
    assert entry.start_time == time(14, 0)
    assert entry.end_time == time(16, 32)
    assert entry.venue_id == venue.id


def test_create_entry_with_unknown_times(store: Store) -> None:
    medium = store.add_medium("netflix", is_physical_place=False)

    entry = store.create_entry(
        title="Paper Constellations", date=date(2026, 3, 14), medium_id=medium.id
    )

    assert entry.start_time is None
    assert entry.end_time is None
    assert entry.venue_id is None


def test_non_physical_medium_allows_no_venue(store: Store) -> None:
    medium = store.add_medium("netflix", is_physical_place=False)

    entry = store.create_entry(title="A show", date=date(2026, 1, 1), medium_id=medium.id)

    assert medium.is_physical_place is False
    assert entry.venue_id is None


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


def test_close_does_not_raise(store: Store) -> None:
    store.close()
