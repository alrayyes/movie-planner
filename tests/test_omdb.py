from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import httpx
import pytest
from fakes import FakeCalendar

from movie_planner.calendar_sync import CalendarClient, CalendarSync
from movie_planner.omdb import OmdbClient, fetch_and_store_ratings
from movie_planner.store import Store

MATCH_RESPONSE = {
    "Title": "Dune",
    "imdbRating": "8.0",
    "Ratings": [
        {"Source": "Internet Movie Database", "Value": "8.0/10"},
        {"Source": "Rotten Tomatoes", "Value": "83%"},
        {"Source": "Metacritic", "Value": "74/100"},
    ],
    "imdbID": "tt1160419",
    "Response": "True",
}

NO_MATCH_RESPONSE = {"Response": "False", "Error": "Movie not found!"}


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> OmdbClient:
    http_client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://www.omdbapi.com/"
    )
    return OmdbClient(api_key="test-key", http_client=http_client)


def test_lookup_by_title_returns_ratings() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.imdb == "8.0/10"
    assert ratings.rotten_tomatoes == "83%"
    assert ratings.metacritic == "74/100"
    assert seen_params["t"] == "Dune"
    assert seen_params["apikey"] == "test-key"


def test_lookup_by_imdb_id_sends_the_id_param() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(imdb_id="tt1160419")

    assert seen_params["i"] == "tt1160419"
    assert "t" not in seen_params


def test_lookup_no_match_returns_none() -> None:
    client = _client(lambda request: httpx.Response(200, json=NO_MATCH_RESPONSE))

    ratings = client.lookup(title="Not A Real Movie Title Xyz")

    assert ratings is None


def test_lookup_missing_rating_source_is_none() -> None:
    response = {
        "imdbRating": "8.0",
        "Ratings": [{"Source": "Internet Movie Database", "Value": "8.0/10"}],
        "Response": "True",
    }
    client = _client(lambda request: httpx.Response(200, json=response))

    ratings = client.lookup(title="Some Movie")

    assert ratings is not None
    assert ratings.imdb == "8.0/10"
    assert ratings.rotten_tomatoes is None
    assert ratings.metacritic is None
    assert ratings.imdb_id is None


def test_lookup_returns_the_imdb_id() -> None:
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.imdb_id == "tt1160419"


def test_lookup_caches_successful_matches() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(title="Dune")
    client.lookup(title="Dune")

    assert call_count == 1


def test_lookup_caches_no_match_too() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=NO_MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(title="Missing")
    client.lookup(title="Missing")

    assert call_count == 1


def test_lookup_requires_title_or_imdb_id() -> None:
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    with pytest.raises(ValueError, match="title or imdb_id"):
        client.lookup()


# --- fetch_and_store_ratings: task 5.2 ---


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "movies.db")
    yield s
    s.close()


def test_fetch_and_store_ratings_on_a_match(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    updated, found = fetch_and_store_ratings(store, client, entry)

    assert found is True
    assert updated.imdb_rating == "8.0/10"
    assert updated.rotten_tomatoes_rating == "83%"
    assert updated.metacritic_rating == "74/100"
    assert store.get_entry(entry.id).imdb_rating == "8.0/10"


def test_fetch_and_store_ratings_sets_imdb_url_from_the_imdb_id(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    updated, _ = fetch_and_store_ratings(store, client, entry)

    assert updated.imdb_url == "https://www.imdb.com/title/tt1160419/"
    assert store.get_entry(entry.id).imdb_url == "https://www.imdb.com/title/tt1160419/"


def test_fetch_and_store_ratings_does_not_overwrite_a_manual_imdb_url(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, imdb_url="https://www.imdb.com/title/tt-manual/")
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    updated, _ = fetch_and_store_ratings(store, client, entry)

    assert updated.imdb_url == "https://www.imdb.com/title/tt-manual/"


def test_fetch_and_store_ratings_on_no_match(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Not A Real Movie", date=date(2026, 1, 1), medium_id=medium.id)
    client = _client(lambda request: httpx.Response(200, json=NO_MATCH_RESPONSE))

    updated, found = fetch_and_store_ratings(store, client, entry)

    assert found is False
    assert updated.imdb_rating is None


def test_entry_logs_updates_and_syncs_with_no_metadata_at_all(store: Store) -> None:
    """Task 5.4: metadata is entirely optional, at every stage."""
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    assert entry.imdb_rating is None
    assert entry.letterboxd_url is None

    entry = store.update_entry(entry.id, title="Dune Part Two")
    assert entry.imdb_rating is None

    sync = CalendarSync(store, CalendarClient(FakeCalendar()))
    synced = sync.push_new(entry, venue=None)

    assert synced.caldav_uid is not None
    assert synced.imdb_rating is None
