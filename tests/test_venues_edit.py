"""`locations venues edit` fixes a venue's address and coordinates, and lists
show them. A venue added with just a name can't gain these any other way.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes import FakeCalendar
from typer.testing import CliRunner

from movie_planner.calendar_sync import CalendarClient
from movie_planner.cli import _format_venue, app
from movie_planner.store import Store, StoreError, Venue

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
def calendar(monkeypatch: pytest.MonkeyPatch) -> FakeCalendar:
    fake = FakeCalendar()
    monkeypatch.setattr(
        CalendarClient, "connect", classmethod(lambda cls, **kw: CalendarClient(fake))
    )
    return fake


@pytest.fixture
def store(tmp_path: Path, config_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "movies.db")
    yield s
    s.close()


def _cli(config_path: Path, *args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["--config", str(config_path), *args])
    return result.exit_code, result.output


def _edit(config_path: Path, *args: str) -> tuple[int, str]:
    return _cli(config_path, "locations", "venues", "edit", "Grand Vista Cinema", *args)


def test_edit_stores_the_address_and_list_shows_it(config_path: Path, store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    code, output = _edit(
        config_path,
        "--street",
        "1 Main St",
        "--postal-code",
        "1011AB",
        "--city",
        "Amsterdam",
        "--country",
        "NL",
    )

    assert code == 0, output
    venue = next(v for v in store.list_venues() if v.name == "Grand Vista Cinema")
    assert (venue.street_address, venue.postal_code, venue.city, venue.country) == (
        "1 Main St",
        "1011AB",
        "Amsterdam",
        "NL",
    )
    _, listing = _cli(config_path, "locations", "venues", "list")
    assert "Grand Vista Cinema" in listing
    assert "1 Main St" in listing
    assert "1011AB Amsterdam" in listing
    assert "NL" in listing


def test_edit_stores_the_chain_and_coordinates(config_path: Path, store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    code, output = _edit(config_path, "--chain", "Vista", "--lat", "52.37", "--lon", "4.89")

    assert code == 0, output
    venue = store.list_venues()[0]
    assert (venue.chain, venue.latitude, venue.longitude) == ("Vista", 52.37, 4.89)
    _, listing = _cli(config_path, "locations", "venues", "list")
    assert "52.37" in listing
    assert "4.89" in listing


def test_edit_leaves_fields_it_was_not_given_alone(config_path: Path, store: Store) -> None:
    store.add_venue("Grand Vista Cinema")
    _edit(config_path, "--city", "Amsterdam", "--country", "NL")

    _edit(config_path, "--street", "1 Main St")

    venue = store.list_venues()[0]
    assert (venue.city, venue.country, venue.street_address) == ("Amsterdam", "NL", "1 Main St")


@pytest.mark.parametrize(
    "args",
    [
        ["--lat", "91", "--lon", "4"],
        ["--lat", "-91", "--lon", "4"],
        ["--lat", "52", "--lon", "181"],
        ["--lat", "52", "--lon", "-181"],
        ["--lat", "north", "--lon", "4"],
        ["--lat", "52"],
        ["--lon", "4"],
    ],
)
def test_a_bad_or_lonely_coordinate_is_refused_and_changes_nothing(
    config_path: Path, store: Store, args: list[str]
) -> None:
    store.add_venue("Grand Vista Cinema")

    code, _ = _edit(config_path, "--city", "Amsterdam", *args)

    assert code != 0
    venue = store.list_venues()[0]
    assert (venue.city, venue.latitude, venue.longitude) == (None, None, None)


def test_the_boundary_coordinates_are_accepted(config_path: Path, store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    code, output = _edit(config_path, "--lat", "-90", "--lon", "180")

    assert code == 0, output
    assert (store.list_venues()[0].latitude, store.list_venues()[0].longitude) == (-90, 180)


def test_an_unknown_venue_fails_naming_it_and_changes_nothing(
    config_path: Path, store: Store
) -> None:
    store.add_venue("Other Cinema")

    code, output = _edit(config_path, "--city", "Amsterdam")

    assert code == 1
    assert "Grand Vista Cinema" in output
    assert [v.city for v in store.list_venues()] == [None]


def test_edit_with_nothing_to_change_is_refused(config_path: Path, store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    code, output = _edit(config_path)

    assert code == 1
    assert "Nothing to change" in output


def test_an_empty_value_clears_the_field(config_path: Path, store: Store) -> None:
    store.add_venue("Grand Vista Cinema")
    _edit(config_path, "--street", "1 Main St")

    code, _ = _edit(config_path, "--street", "")

    assert code == 0
    assert store.list_venues()[0].street_address is None


def test_the_calendar_events_carry_the_new_location_and_geo(
    config_path: Path, calendar: FakeCalendar
) -> None:
    code, output = _cli(
        config_path,
        "log",
        "--title",
        "Dune",
        "--date",
        "2026-01-01",
        "--medium",
        "cinema",
        "--venue",
        "Grand Vista Cinema",
        "--no-metadata",
    )
    assert code == 0, output
    before = next(iter(calendar.events_by_uid.values())).data
    assert "GEO:" not in before

    code, output = _edit(
        config_path,
        "--street",
        "1 Main St",
        "--postal-code",
        "1011AB",
        "--city",
        "Amsterdam",
        "--country",
        "NL",
        "--lat",
        "52.37",
        "--lon",
        "4.89",
    )

    assert code == 0, output
    ical = next(iter(calendar.events_by_uid.values())).data
    assert "LOCATION:Grand Vista Cinema\\, 1 Main St\\, 1011AB Amsterdam\\, NL" in ical
    assert "GEO:52.37;4.89" in ical


def test_a_calendar_failure_warns_but_keeps_the_edit(
    config_path: Path, calendar: FakeCalendar, store: Store
) -> None:
    _cli(
        config_path,
        "log",
        "--title",
        "Dune",
        "--date",
        "2026-01-01",
        "--medium",
        "cinema",
        "--venue",
        "Grand Vista Cinema",
        "--no-metadata",
    )
    calendar.fail_next = True

    code, output = _edit(config_path, "--city", "Amsterdam")

    assert code == 0, output
    assert "Warning" in output
    assert next(v for v in store.list_venues() if v.name == "Grand Vista Cinema").city == (
        "Amsterdam"
    )


def test_store_update_venue_rejects_an_unknown_name(store: Store) -> None:
    with pytest.raises(StoreError, match="venue 'Nope' does not exist"):
        store.update_venue("Nope", city="Amsterdam")


def test_store_update_venue_sets_every_column_and_returns_the_venue(store: Store) -> None:
    store.add_venue("Grand Vista Cinema")

    venue = store.update_venue(
        "Grand Vista Cinema",
        chain="Vista",
        city="Amsterdam",
        country="NL",
        latitude=52.37,
        longitude=4.89,
        street_address="1 Main St",
        postal_code="1011AB",
    )

    assert venue.name == "Grand Vista Cinema"
    assert (venue.chain, venue.city, venue.country) == ("Vista", "Amsterdam", "NL")
    assert (venue.latitude, venue.longitude) == (52.37, 4.89)
    assert (venue.street_address, venue.postal_code) == ("1 Main St", "1011AB")
    assert store.list_venues() == [venue]


def test_store_update_venue_with_no_changes_returns_it_untouched(store: Store) -> None:
    added = store.add_venue("Grand Vista Cinema")

    assert store.update_venue("Grand Vista Cinema") == added


def test_store_update_venue_clears_a_column_with_none(store: Store) -> None:
    store.add_venue("Grand Vista Cinema")
    store.update_venue("Grand Vista Cinema", city="Amsterdam")

    assert store.update_venue("Grand Vista Cinema", city=None).city is None


def test_a_venue_is_listed_as_its_name_alone_when_nothing_else_is_known() -> None:
    assert _format_venue(Venue(id=1, name="Grand Vista")) == "Grand Vista"


def test_a_venue_is_listed_with_chain_address_and_coordinates() -> None:
    venue = Venue(
        id=1,
        name="Grand Vista",
        chain="Vista",
        city="Amsterdam",
        country="NL",
        latitude=52.37,
        longitude=4.89,
        street_address="1 Main St",
        postal_code="1011AB",
    )

    assert _format_venue(venue) == (
        "Grand Vista (Vista) - 1 Main St, 1011AB Amsterdam, NL [52.37, 4.89]"
    )


def test_a_venue_with_only_one_coordinate_lists_neither() -> None:
    assert _format_venue(Venue(id=1, name="A", latitude=52.37)) == "A"
    assert _format_venue(Venue(id=1, name="A", longitude=4.89)) == "A"


def test_a_venue_with_a_city_but_no_postal_code_lists_just_the_city() -> None:
    assert _format_venue(Venue(id=1, name="A", city="Amsterdam")) == "A - Amsterdam"
