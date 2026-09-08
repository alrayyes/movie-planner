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


# --- import failures: issue #254 ---


def test_record_import_failure_and_list_it(store: Store) -> None:
    failure = store.record_import_failure(source="movies.csv", row_number=3, error="bad date")

    assert failure.source == "movies.csv"
    assert failure.row_number == 3
    assert failure.error == "bad date"

    (listed,) = store.list_import_failures()
    assert listed == failure


def test_list_import_failures_most_recent_first(store: Store) -> None:
    first = store.record_import_failure(source="a.csv", row_number=1, error="e1")
    second = store.record_import_failure(source="b.csv", row_number=2, error="e2")

    listed = store.list_import_failures()

    assert [f.id for f in listed] == [second.id, first.id]


def test_list_import_failures_empty_when_none_recorded(store: Store) -> None:
    assert store.list_import_failures() == []


def test_clear_import_failures_removes_everything_and_reports_the_count(store: Store) -> None:
    store.record_import_failure(source="a.csv", row_number=1, error="e1")
    store.record_import_failure(source="b.csv", row_number=2, error="e2")

    cleared = store.clear_import_failures()

    assert cleared == 2
    assert store.list_import_failures() == []


def test_clear_import_failures_returns_zero_when_none_recorded(store: Store) -> None:
    assert store.clear_import_failures() == 0


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
    assert {"entries", "media", "venues", "import_failures", "activity_log"} <= tables


# --- activity log: issue #276 ---


def _medium(store: Store) -> int:
    return store.add_medium("cinema", is_physical_place=True).id


def test_create_entry_records_a_create_activity(store: Store) -> None:
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=_medium(store))

    (activity,) = store.list_activity()
    assert activity.action == "create"
    assert activity.entry_id == entry.id
    assert activity.entry_title == "Dune"
    assert activity.changes is None


def test_update_entry_records_only_the_fields_that_actually_changed(store: Store) -> None:
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=_medium(store))

    store.update_entry(entry.id, title="Dune Part Two", notes="great")

    activities = store.list_activity()
    update = next(a for a in activities if a.action == "update")
    assert update.entry_id == entry.id
    assert update.entry_title == "Dune Part Two"
    assert update.changes == {
        "title": ("Dune", "Dune Part Two"),
        "notes": (None, "great"),
    }


def test_update_entry_passing_the_same_value_records_no_activity(store: Store) -> None:
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=_medium(store))

    store.update_entry(entry.id, title="Dune")

    activities = [a for a in store.list_activity() if a.action == "update"]
    assert activities == []


def test_delete_entry_records_a_delete_activity_with_the_titles(store: Store) -> None:
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=_medium(store))

    store.delete_entry(entry.id)

    (activity,) = [a for a in store.list_activity() if a.action == "delete"]
    assert activity.entry_id == entry.id
    assert activity.entry_title == "Dune"
    assert activity.changes is None


def test_list_activity_most_recent_first(store: Store) -> None:
    medium_id = _medium(store)
    first = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium_id)
    second = store.create_entry(title="Arrival", date=date(2026, 1, 2), medium_id=medium_id)

    activities = store.list_activity()

    assert [a.entry_id for a in activities] == [second.id, first.id]


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
    store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

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


def test_add_venue_matching_known_chain_gets_location(store: Store) -> None:
    venue = store.add_venue("Tuschinski")

    assert venue.chain == "Pathé"
    assert venue.city == "Amsterdam"
    assert venue.country == "Netherlands"


def test_add_venue_matching_known_independent_gets_no_chain(store: Store) -> None:
    venue = store.add_venue("Eye")

    assert venue.chain is None
    assert venue.city == "Amsterdam"
    assert venue.country == "Netherlands"


def test_add_venue_not_in_the_known_table_gets_no_location(store: Store) -> None:
    venue = store.add_venue("Grand Vista Cinema")

    assert venue.chain is None
    assert venue.city is None
    assert venue.country is None


def test_add_venue_with_known_coordinates_gets_them(store: Store) -> None:
    venue = store.add_venue("Tuschinski")

    assert venue.latitude == pytest.approx(52.3665062)
    assert venue.longitude == pytest.approx(4.8947073)


def test_add_venue_not_in_the_known_table_gets_no_coordinates(store: Store) -> None:
    venue = store.add_venue("Grand Vista Cinema")

    assert venue.latitude is None


def test_add_venue_with_known_street_address_gets_it(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    from movie_planner.venue_locations import KNOWN_VENUE_LOCATIONS, VenueLocation

    monkeypatch.setitem(
        KNOWN_VENUE_LOCATIONS,
        "Test Cinema",
        VenueLocation(
            chain=None,
            city="Amsterdam",
            country="Netherlands",
            street_address="Teststraat 1",
            postal_code="1000 AA",
            canonical_name="Test Cinema",
        ),
    )

    venue = store.add_venue("Test Cinema")

    assert venue.street_address == "Teststraat 1"
    assert venue.postal_code == "1000 AA"


def test_add_venue_not_in_the_known_table_gets_no_street_address(store: Store) -> None:
    venue = store.add_venue("Grand Vista Cinema")

    assert venue.street_address is None
    assert venue.postal_code is None
    assert venue.longitude is None


def test_migration_backfills_location_for_an_existing_known_venue(tmp_path: Path) -> None:
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
    conn.execute("INSERT INTO venues (name) VALUES ('Tuschinski')")
    conn.commit()
    conn.close()

    s = Store(db_path)
    try:
        (venue,) = s.list_venues()
        assert venue.chain == "Pathé"
        assert venue.city == "Amsterdam"
        assert venue.latitude == pytest.approx(52.3665062)
        assert venue.longitude == pytest.approx(4.8947073)
    finally:
        s.close()


def test_migration_backfills_coordinates_for_a_venue_already_migrated_by_111(
    tmp_path: Path,
) -> None:
    # movie-planner#185: a real, previously-used database already ran
    # the #111 chain/city/country migration, so those three columns
    # are non-NULL by the time #170's coordinate backfill runs - it
    # must not skip a venue just because chain/city/country are
    # already set, only latitude/longitude need filling here.
    import sqlite3

    db_path = tmp_path / "movies.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE media (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            is_physical_place INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE venues (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            chain TEXT, city TEXT, country TEXT
        );
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL,
            start_time TEXT, end_time TEXT,
            medium_id INTEGER NOT NULL REFERENCES media(id),
            venue_id INTEGER REFERENCES venues(id)
        );
        """
    )
    conn.execute(
        "INSERT INTO venues (name, chain, city, country) VALUES ('Tuschinski', 'Pathé', "
        "'Amsterdam', 'Netherlands')"
    )
    conn.commit()
    conn.close()

    s = Store(db_path)
    try:
        (venue,) = s.list_venues()
        assert venue.chain == "Pathé"
        assert venue.latitude == pytest.approx(52.3665062)
        assert venue.longitude == pytest.approx(4.8947073)
    finally:
        s.close()


def test_migration_backfills_street_address_for_an_existing_known_venue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Same shape as #170's coordinate backfill above (issue #283): a
    # venue row created before the table gained a verified street
    # address/postal code for it still needs to pick those up on the
    # next store open, not just brand-new rows.
    import sqlite3

    from movie_planner.venue_locations import KNOWN_VENUE_LOCATIONS, VenueLocation

    monkeypatch.setitem(
        KNOWN_VENUE_LOCATIONS,
        "Test Cinema",
        VenueLocation(
            chain=None,
            city="Amsterdam",
            country="Netherlands",
            street_address="Teststraat 1",
            postal_code="1000 AA",
            canonical_name="Test Cinema",
        ),
    )

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
    conn.execute("INSERT INTO venues (name) VALUES ('Test Cinema')")
    conn.commit()
    conn.close()

    s = Store(db_path)
    try:
        (venue,) = s.list_venues()
        assert venue.street_address == "Teststraat 1"
        assert venue.postal_code == "1000 AA"
    finally:
        s.close()


def test_migration_never_overwrites_an_already_set_street_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    from movie_planner.venue_locations import KNOWN_VENUE_LOCATIONS, VenueLocation

    monkeypatch.setitem(
        KNOWN_VENUE_LOCATIONS,
        "Test Cinema",
        VenueLocation(
            chain=None,
            city="Amsterdam",
            country="Netherlands",
            street_address="Teststraat 1",
            postal_code="1000 AA",
            canonical_name="Test Cinema",
        ),
    )

    db_path = tmp_path / "movies.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE media (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            is_physical_place INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE venues (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, street_address TEXT
        );
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL,
            start_time TEXT, end_time TEXT,
            medium_id INTEGER NOT NULL REFERENCES media(id),
            venue_id INTEGER REFERENCES venues(id)
        );
        """
    )
    conn.execute(
        "INSERT INTO venues (name, street_address) VALUES ('Test Cinema', 'Manually Set 5')"
    )
    conn.commit()
    conn.close()

    s = Store(db_path)
    try:
        (venue,) = s.list_venues()
        assert venue.street_address == "Manually Set 5"
    finally:
        s.close()


def test_migration_never_overwrites_an_already_set_coordinate(tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "movies.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE media (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            is_physical_place INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE venues (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            chain TEXT, city TEXT, country TEXT, latitude REAL, longitude REAL
        );
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL,
            start_time TEXT, end_time TEXT,
            medium_id INTEGER NOT NULL REFERENCES media(id),
            venue_id INTEGER REFERENCES venues(id)
        );
        """
    )
    conn.execute(
        "INSERT INTO venues (name, chain, city, country, latitude, longitude) "
        "VALUES ('Tuschinski', 'Pathé', 'Amsterdam', 'Netherlands', 0.0, 0.0)"
    )
    conn.commit()
    conn.close()

    s = Store(db_path)
    try:
        (venue,) = s.list_venues()
        assert venue.latitude == 0.0
        assert venue.longitude == 0.0
    finally:
        s.close()


def test_remove_venue_not_in_use(store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    store.remove_venue("Grand Vista Cinema")

    assert store.list_venues() == []


def test_remove_venue_in_use_is_rejected(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    venue = store.add_venue("Grand Vista Cinema")
    store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id, venue_id=venue.id)

    with pytest.raises(StoreError, match="Grand Vista Cinema"):
        store.remove_venue("Grand Vista Cinema")


def test_create_entry_with_full_time_range(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    venue = store.add_venue("Grand Vista Cinema")

    entry = store.create_entry(
        title="The Clockmaker's Daughter",
        date=date(2024, 3, 15),
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
        title="Paper Constellations", date=date(2024, 1, 20), medium_id=medium.id
    )

    assert entry.start_time is None
    assert entry.end_time is None
    assert entry.venue_id is None


def test_non_physical_medium_allows_no_venue(store: Store) -> None:
    medium = store.add_medium("netflix", is_physical_place=False)

    entry = store.create_entry(title="A show", date=date(2024, 3, 15), medium_id=medium.id)

    assert medium.is_physical_place is False
    assert entry.venue_id is None


def test_new_entry_has_no_caldav_uid(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    assert entry.caldav_uid is None


def test_update_entry_sets_caldav_uid(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

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
        entry = s.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)
        assert entry.caldav_uid is None
    finally:
        s.close()


def test_list_entries_ordered_by_date(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    store.create_entry(title="Second", date=date(2026, 2, 1), medium_id=medium.id)
    store.create_entry(title="First", date=date(2024, 3, 15), medium_id=medium.id)

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
    store.create_entry(title="Cinema movie", date=date(2024, 3, 15), medium_id=cinema.id)
    store.create_entry(title="Netflix movie", date=date(2024, 3, 15), medium_id=netflix.id)

    entries = store.list_entries(medium_id=cinema.id)

    assert [e.title for e in entries] == ["Cinema movie"]


def test_update_entry_changes_the_stored_date(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(entry.id, date=date(2026, 1, 2))

    assert updated.date == date(2026, 1, 2)
    assert store.get_entry(entry.id).date == date(2026, 1, 2)


def test_update_entry_leaves_unspecified_fields_alone(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune", date=date(2024, 3, 15), start_time=time(14, 0), medium_id=medium.id
    )

    updated = store.update_entry(entry.id, title="Dune Part Two")

    assert updated.title == "Dune Part Two"
    assert updated.start_time == time(14, 0)


def test_delete_entry_removes_it_from_list(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

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

    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    assert entry.imdb_rating is None
    assert entry.rotten_tomatoes_rating is None
    assert entry.metacritic_rating is None
    assert entry.letterboxd_url is None
    assert entry.letterboxd_rating is None


def test_update_entry_sets_omdb_ratings(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

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
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(
        entry.id,
        letterboxd_url="https://letterboxd.com/film/dune-2021/",
        letterboxd_rating="4.5",
    )

    assert updated.letterboxd_url == "https://letterboxd.com/film/dune-2021/"
    assert updated.letterboxd_rating == "4.5"


def test_new_entry_has_no_notes(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    assert entry.notes is None


def test_update_entry_sets_notes(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(entry.id, notes="Enjoyed the soundtrack")

    assert updated.notes == "Enjoyed the soundtrack"
    reloaded = store.get_entry(entry.id)
    assert reloaded.notes == "Enjoyed the soundtrack"


# --- row/seat: issue #218 ---


def test_new_entry_has_no_row_or_seat(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    assert entry.row is None
    assert entry.seat is None


def test_create_entry_sets_row_and_seat(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(
        title="Dune", date=date(2024, 3, 15), medium_id=medium.id, row="5", seat="17"
    )

    assert entry.row == "5"
    assert entry.seat == "17"


def test_update_entry_sets_row_and_seat(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(entry.id, row="5", seat="17")

    assert updated.row == "5"
    assert updated.seat == "17"
    reloaded = store.get_entry(entry.id)
    assert reloaded.row == "5"
    assert reloaded.seat == "17"


def test_migrates_a_database_created_before_row_and_seat_existed(tmp_path: Path) -> None:
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
        entry = s.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)
        assert entry.row is None
        assert entry.seat is None
        updated = s.update_entry(entry.id, row="5", seat="17")
        assert updated.row == "5"
        assert updated.seat == "17"
    finally:
        s.close()


def test_new_entry_has_no_poster_url(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    assert entry.poster_url is None


def test_update_entry_sets_poster_url(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(
        entry.id, poster_url="https://m.media-amazon.com/images/dune-poster.jpg"
    )

    assert updated.poster_url == "https://m.media-amazon.com/images/dune-poster.jpg"
    reloaded = store.get_entry(entry.id)
    assert reloaded.poster_url == "https://m.media-amazon.com/images/dune-poster.jpg"


def test_new_entry_has_no_omdb_last_no_match(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    assert entry.omdb_last_no_match is None


def test_update_entry_sets_omdb_last_no_match(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(entry.id, omdb_last_no_match=date(2026, 9, 7))

    assert updated.omdb_last_no_match == date(2026, 9, 7)
    reloaded = store.get_entry(entry.id)
    assert reloaded.omdb_last_no_match == date(2026, 9, 7)


def test_update_entry_clears_omdb_last_no_match(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)
    entry = store.update_entry(entry.id, omdb_last_no_match=date(2026, 9, 7))

    updated = store.update_entry(entry.id, omdb_last_no_match=None)

    assert updated.omdb_last_no_match is None


def test_new_entry_has_no_trailer_url(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    assert entry.trailer_url is None


def test_update_entry_sets_trailer_url(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(
        entry.id, trailer_url="https://www.youtube.com/watch?v=8g18jFHCLXk"
    )

    assert updated.trailer_url == "https://www.youtube.com/watch?v=8g18jFHCLXk"
    reloaded = store.get_entry(entry.id)
    assert reloaded.trailer_url == "https://www.youtube.com/watch?v=8g18jFHCLXk"


def test_new_entry_has_no_director_actors_genre_or_release_year(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    assert entry.director is None
    assert entry.actors is None
    assert entry.genre is None
    assert entry.release_year is None


def test_update_entry_sets_director_actors_genre_and_release_year(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(
        entry.id,
        director="Denis Villeneuve",
        actors="Timothée Chalamet, Rebecca Ferguson, Zendaya",
        genre="Action, Adventure, Drama",
        release_year=2021,
    )

    assert updated.director == "Denis Villeneuve"
    assert updated.actors == "Timothée Chalamet, Rebecca Ferguson, Zendaya"
    assert updated.genre == "Action, Adventure, Drama"
    assert updated.release_year == 2021
    reloaded = store.get_entry(entry.id)
    assert reloaded.director == "Denis Villeneuve"
    assert reloaded.actors == "Timothée Chalamet, Rebecca Ferguson, Zendaya"
    assert reloaded.genre == "Action, Adventure, Drama"
    assert reloaded.release_year == 2021


def test_migrates_a_database_created_before_director_actors_genre_and_release_year_existed(
    tmp_path: Path,
) -> None:
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
        entry = s.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)
        assert entry.director is None
        assert entry.release_year is None
        updated = s.update_entry(entry.id, director="Denis Villeneuve", release_year=2021)
        assert updated.director == "Denis Villeneuve"
        assert updated.release_year == 2021
    finally:
        s.close()


def test_update_entry_sets_imdb_url(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)

    updated = store.update_entry(entry.id, imdb_url="https://www.imdb.com/title/tt1160419/")

    assert updated.imdb_url == "https://www.imdb.com/title/tt1160419/"


def test_get_or_create_medium_returns_existing(store: Store) -> None:
    created = store.add_medium("cinema", is_physical_place=True)

    fetched = store.get_or_create_medium("cinema", is_physical_place=False)

    assert fetched == created
    assert len(store.list_media()) == 1


def test_get_or_create_medium_creates_when_missing(store: Store) -> None:
    medium = store.get_or_create_medium("netflix", is_physical_place=False)

    assert medium.name == "netflix"
    assert medium.is_physical_place is False
    assert store.list_media() == [medium]


def test_get_or_create_venue_returns_existing(store: Store) -> None:
    created = store.add_venue("Grand Vista Cinema")

    fetched = store.get_or_create_venue("Grand Vista Cinema")

    assert fetched == created
    assert len(store.list_venues()) == 1


def test_get_or_create_venue_creates_when_missing(store: Store) -> None:
    venue = store.get_or_create_venue("City")

    assert venue.name == "City"
    assert store.list_venues() == [venue]


# --- alias resolution: issue #196 ---


def test_add_venue_with_a_known_alias_creates_the_canonical_venue_instead(store: Store) -> None:
    venue = store.add_venue("De Munt 4DX")

    assert venue.name == "De Munt"
    assert venue.chain == "Pathé"


def test_get_or_create_venue_resolves_a_known_alias_to_its_canonical_venue(store: Store) -> None:
    venue = store.get_or_create_venue("De Munt 4DX")

    assert venue.name == "De Munt"
    assert store.list_venues() == [venue]


def test_get_or_create_venue_with_two_different_aliases_returns_the_same_venue(
    store: Store,
) -> None:
    first = store.get_or_create_venue("De Munt 4DX")
    second = store.get_or_create_venue("De Munt Relax")

    assert first == second
    assert len(store.list_venues()) == 1


def test_get_or_create_venue_with_an_alias_finds_an_already_canonical_venue(
    store: Store,
) -> None:
    canonical = store.add_venue("De Munt")

    fetched = store.get_or_create_venue("De Munt 4DX")

    assert fetched == canonical
    assert len(store.list_venues()) == 1


# --- merge_venue_aliases: issue #196's migration for already-split data ---
#
# `add_venue`/`get_or_create_venue` above stop a *new* alias-named row
# from ever being created - these tests are about data that predates
# that fix, so they seed a legacy split venue row directly via SQL
# rather than through the store's own (now alias-resolving) API, the
# same way test_migration_backfills_location_for_an_existing_known_venue
# above simulates pre-migration data.


def _seed_legacy_venue(store: Store, name: str) -> int:
    cur = store._conn.execute("INSERT INTO venues (name) VALUES (?)", (name,))
    store._conn.commit()
    assert cur.lastrowid is not None  # nosec B101
    return cur.lastrowid


def test_dry_run_reports_a_merge_without_changing_anything(store: Store) -> None:
    alias_id = _seed_legacy_venue(store, "De Munt 4DX")
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune", date=date(2024, 3, 15), medium_id=medium.id, venue_id=alias_id
    )

    (merge,) = store.merge_venue_aliases(apply=False)

    assert merge.alias_name == "De Munt 4DX"
    assert merge.canonical_name == "De Munt"
    assert merge.entries_moved == 1
    assert merge.canonical_venue_id is None  # doesn't exist yet - not created by a dry run
    # Nothing actually changed:
    assert [v.name for v in store.list_venues()] == ["De Munt 4DX"]
    assert store.get_entry(entry.id).venue_id == alias_id


def test_dry_run_finds_an_already_existing_canonical_venue(store: Store) -> None:
    canonical = store.add_venue("De Munt")
    _seed_legacy_venue(store, "De Munt 4DX")

    (merge,) = store.merge_venue_aliases(apply=False)

    assert merge.canonical_venue_id == canonical.id


def test_apply_creates_the_canonical_venue_and_moves_entries(store: Store) -> None:
    alias_id = _seed_legacy_venue(store, "De Munt 4DX")
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune", date=date(2024, 3, 15), medium_id=medium.id, venue_id=alias_id
    )

    (merge,) = store.merge_venue_aliases(apply=True)

    assert merge.entries_moved == 1
    venues = store.list_venues()
    assert [v.name for v in venues] == ["De Munt"]
    canonical = venues[0]
    assert merge.canonical_venue_id == canonical.id
    assert store.get_entry(entry.id).venue_id == canonical.id


def test_apply_reuses_an_already_existing_canonical_venue(store: Store) -> None:
    canonical = store.add_venue("De Munt")
    alias_id = _seed_legacy_venue(store, "De Munt 4DX")
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(
        title="Dune", date=date(2024, 3, 15), medium_id=medium.id, venue_id=alias_id
    )

    store.merge_venue_aliases(apply=True)

    assert [v.name for v in store.list_venues()] == ["De Munt"]
    assert store.get_entry(entry.id).venue_id == canonical.id


def test_apply_merges_multiple_alias_venues_into_one_canonical_venue(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    alias_a = _seed_legacy_venue(store, "De Munt 4DX")
    alias_b = _seed_legacy_venue(store, "De Munt Relax")
    entry_a = store.create_entry(
        title="Dune", date=date(2024, 3, 15), medium_id=medium.id, venue_id=alias_a
    )
    entry_b = store.create_entry(
        title="Nope", date=date(2024, 3, 16), medium_id=medium.id, venue_id=alias_b
    )

    merges = store.merge_venue_aliases(apply=True)

    assert {m.alias_name for m in merges} == {"De Munt 4DX", "De Munt Relax"}
    venues = store.list_venues()
    assert [v.name for v in venues] == ["De Munt"]
    canonical_id = venues[0].id
    assert store.get_entry(entry_a.id).venue_id == canonical_id
    assert store.get_entry(entry_b.id).venue_id == canonical_id


def test_apply_removes_the_orphaned_alias_row_even_with_no_entries(store: Store) -> None:
    _seed_legacy_venue(store, "De Munt 4DX")

    store.merge_venue_aliases(apply=True)

    # The alias row itself is gone; the canonical venue still gets
    # created even though nothing referenced the alias to move over.
    assert [v.name for v in store.list_venues()] == ["De Munt"]


def test_no_aliases_present_returns_an_empty_list_and_changes_nothing(store: Store) -> None:
    store.add_venue("De Munt")
    store.add_venue("Grand Vista Cinema")

    merges = store.merge_venue_aliases(apply=True)

    assert merges == []
    assert {v.name for v in store.list_venues()} == {"De Munt", "Grand Vista Cinema"}


def test_a_venue_not_in_the_known_table_is_never_touched(store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    merges = store.merge_venue_aliases(apply=True)

    assert merges == []
    assert [v.name for v in store.list_venues()] == ["Grand Vista Cinema"]


def test_close_does_not_raise(store: Store) -> None:
    store.close()


def test_new_entry_has_no_booking_ref(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)

    entry = store.create_entry(title="The Dog Stars", date=date(2026, 8, 29), medium_id=medium.id)

    assert entry.booking_ref is None


def test_update_entry_sets_booking_ref(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="The Dog Stars", date=date(2026, 8, 29), medium_id=medium.id)

    updated = store.update_entry(entry.id, booking_ref="N°WWBXKM8")

    assert updated.booking_ref == "N°WWBXKM8"
    assert store.get_entry(entry.id).booking_ref == "N°WWBXKM8"


def test_get_entry_by_booking_ref_finds_a_match(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="The Dog Stars", date=date(2026, 8, 29), medium_id=medium.id)
    store.update_entry(entry.id, booking_ref="N°WWBXKM8")

    found = store.get_entry_by_booking_ref("N°WWBXKM8")

    assert found is not None
    assert found.id == entry.id


def test_get_entry_by_booking_ref_no_match_returns_none(store: Store) -> None:
    assert store.get_entry_by_booking_ref("N°NOMATCH") is None


def test_booking_ref_is_not_required_to_be_unique(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    first = store.create_entry(title="The Dog Stars", date=date(2026, 8, 29), medium_id=medium.id)
    second = store.create_entry(title="The Dog Stars", date=date(2026, 8, 30), medium_id=medium.id)

    store.update_entry(first.id, booking_ref="N°WWBXKM8")
    store.update_entry(second.id, booking_ref="N°WWBXKM8")  # does not raise

    assert store.get_entry(first.id).booking_ref == store.get_entry(second.id).booking_ref


def test_migrates_a_database_created_before_booking_ref_existed(tmp_path: Path) -> None:
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
        entry = s.create_entry(title="Dune", date=date(2024, 3, 15), medium_id=medium.id)
        assert entry.booking_ref is None
        updated = s.update_entry(entry.id, booking_ref="N°WWBXKM8")
        assert updated.booking_ref == "N°WWBXKM8"
    finally:
        s.close()
