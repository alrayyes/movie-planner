from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import httpx
import pytest
from fakes import FakeCalendar

from movie_planner.calendar_sync import CalendarClient, CalendarSync
from movie_planner.omdb import OmdbClient, fetch_and_store_ratings, needs_omdb_fetch
from movie_planner.store import Entry, Store

MATCH_RESPONSE = {
    "Title": "Dune",
    "Year": "2021",
    "Rated": "PG-13",
    "Released": "22 Oct 2021",
    "Runtime": "155 min",
    "Director": "Denis Villeneuve",
    "Writer": "Jon Spaihts, Denis Villeneuve, Eric Roth",
    "Actors": "Timothée Chalamet, Rebecca Ferguson, Zendaya",
    "Plot": "Paul Atreides unites with the Fremen to seek revenge.",
    "Language": "English, Mandarin",
    "Country": "United States, Canada",
    "Awards": "Won 6 Oscars. 175 wins & 235 nominations total",
    "Genre": "Action, Adventure, Drama",
    "imdbRating": "8.0",
    "imdbVotes": "757,451",
    "Metascore": "74",
    "Ratings": [
        {"Source": "Internet Movie Database", "Value": "8.0/10"},
        {"Source": "Rotten Tomatoes", "Value": "83%"},
        {"Source": "Metacritic", "Value": "74/100"},
    ],
    "imdbID": "tt1160419",
    "Poster": "https://m.media-amazon.com/images/dune-poster.jpg",
    "DVD": "22 Nov 2021",
    "BoxOffice": "$108,327,830",
    "Production": "Legendary Pictures",
    "Website": "https://www.dunemovie.com",
    "Response": "True",
}

NO_MATCH_RESPONSE = {"Response": "False", "Error": "Movie not found!"}

SERIES_RESPONSE = {
    "Title": "Good Boy",
    "Year": "2018–2020",
    "Type": "series",
    "Director": "N/A",
    "Actors": "N/A",
    "Genre": "Comedy",
    "Ratings": [],
    "imdbID": "tt9999999",
    "Poster": "N/A",
    "Response": "True",
}


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


def test_lookup_returns_the_poster_url() -> None:
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.poster == "https://m.media-amazon.com/images/dune-poster.jpg"


def test_lookup_treats_na_poster_as_no_poster() -> None:
    response = {**MATCH_RESPONSE, "Poster": "N/A"}
    client = _client(lambda request: httpx.Response(200, json=response))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.poster is None


def test_lookup_returns_director_actors_genre_and_release_year() -> None:
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.director == "Denis Villeneuve"
    assert ratings.actors == "Timothée Chalamet, Rebecca Ferguson, Zendaya"
    assert ratings.genre == "Action, Adventure, Drama"
    assert ratings.release_year == 2021


def test_lookup_treats_na_as_none_for_director_actors_and_genre() -> None:
    response = {**MATCH_RESPONSE, "Director": "N/A", "Actors": "N/A", "Genre": "N/A"}
    client = _client(lambda request: httpx.Response(200, json=response))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.director is None
    assert ratings.actors is None
    assert ratings.genre is None


def test_lookup_returns_the_rest_of_omdbs_response_fields() -> None:
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.rated == "PG-13"
    assert ratings.released == "22 Oct 2021"
    assert ratings.runtime == "155 min"
    assert ratings.writer == "Jon Spaihts, Denis Villeneuve, Eric Roth"
    assert ratings.plot == "Paul Atreides unites with the Fremen to seek revenge."
    assert ratings.language == "English, Mandarin"
    assert ratings.country == "United States, Canada"
    assert ratings.awards == "Won 6 Oscars. 175 wins & 235 nominations total"
    assert ratings.metascore == "74"
    assert ratings.imdb_votes == "757,451"
    assert ratings.dvd == "22 Nov 2021"
    assert ratings.box_office == "$108,327,830"
    assert ratings.production == "Legendary Pictures"
    assert ratings.website == "https://www.dunemovie.com"


def test_lookup_treats_na_as_none_for_the_rest_of_omdbs_fields() -> None:
    na_fields = [
        "Rated",
        "Released",
        "Runtime",
        "Writer",
        "Plot",
        "Language",
        "Country",
        "Awards",
        "Metascore",
        "imdbVotes",
        "DVD",
        "BoxOffice",
        "Production",
        "Website",
    ]
    response = {**MATCH_RESPONSE, **dict.fromkeys(na_fields, "N/A")}
    client = _client(lambda request: httpx.Response(200, json=response))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.rated is None
    assert ratings.released is None
    assert ratings.runtime is None
    assert ratings.writer is None
    assert ratings.plot is None
    assert ratings.language is None
    assert ratings.country is None
    assert ratings.awards is None
    assert ratings.metascore is None
    assert ratings.imdb_votes is None
    assert ratings.dvd is None
    assert ratings.box_office is None
    assert ratings.production is None
    assert ratings.website is None


def test_lookup_with_missing_fields_leaves_the_rest_of_omdbs_fields_none() -> None:
    response = {
        k: v
        for k, v in MATCH_RESPONSE.items()
        if k
        not in (
            "Rated",
            "Released",
            "Runtime",
            "Writer",
            "Plot",
            "Language",
            "Country",
            "Awards",
            "Metascore",
            "imdbVotes",
            "DVD",
            "BoxOffice",
            "Production",
            "Website",
        )
    }
    client = _client(lambda request: httpx.Response(200, json=response))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.rated is None
    assert ratings.website is None


def test_lookup_with_no_year_field_has_no_release_year() -> None:
    response = {k: v for k, v in MATCH_RESPONSE.items() if k != "Year"}
    client = _client(lambda request: httpx.Response(200, json=response))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.release_year is None


def test_lookup_parses_a_year_range_as_the_release_year() -> None:
    response = {**MATCH_RESPONSE, "Year": "2019–2023"}
    client = _client(lambda request: httpx.Response(200, json=response))

    ratings = client.lookup(title="Dune")

    assert ratings is not None
    assert ratings.release_year == 2019


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


# --- format/edition suffix stripped from the OMDb search: issue #216 ---
#
# Every case here is a real title from Ryan's historical Pathé import
# that failed OMDb lookup because of a trailing format/edition marker
# OMDb's own search doesn't recognize.


@pytest.mark.parametrize(
    ("stored_title", "expected_search_title"),
    [
        ("Spy (OV)", "Spy"),
        ("The Martian 3D", "The Martian"),
        ("Ant-Man and The Wasp 4DX 3D", "Ant-Man and The Wasp"),
        ("Insidious: Chapter 3 (OV)", "Insidious: Chapter 3"),
        ("Wreck-It Ralph 3D OV O3D", "Wreck-It Ralph"),
        # Dutch "Original Version" - movie-planner#224.
        ("Sausage Party (Originele versie)", "Sausage Party"),
        ("Incredibles 2 (Originele versie)", "Incredibles 2"),
        ("The Lego Movie 2 (Originele versie)", "The Lego Movie 2"),
    ],
)
def test_lookup_strips_a_format_suffix_before_searching(
    stored_title: str, expected_search_title: str
) -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    ratings = client.lookup(title=stored_title)

    assert ratings is not None
    assert seen_params["t"] == expected_search_title


def test_lookup_with_and_without_a_format_suffix_share_one_cache_entry_and_call() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    with_suffix = client.lookup(title="Insidious: Chapter 3 (OV)")
    without_suffix = client.lookup(title="Insidious: Chapter 3")

    assert with_suffix is not None
    assert without_suffix is not None
    assert with_suffix == without_suffix
    assert call_count == 1


def test_lookup_with_a_format_suffix_still_honours_the_year_hint() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(title="The Martian 3D", year=2015)

    assert seen_params["t"] == "The Martian"
    assert seen_params["y"] == "2015"


def test_lookup_with_no_recognizable_suffix_is_unaffected() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(title="Dune")

    assert seen_params["t"] == "Dune"


def test_fetch_and_store_ratings_never_changes_the_stored_title(store: Store) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)
    entry = store.create_entry(
        title="Spy (OV)",
        date=date(2026, 1, 1),
        medium_id=store.add_medium("cinema", is_physical_place=True).id,
    )

    updated, matched = fetch_and_store_ratings(store, client, entry)

    assert matched is True
    assert updated.title == "Spy (OV)"


def _entry(**overrides: object) -> Entry:
    defaults: dict[str, object] = {
        "id": 1,
        "title": "Dune",
        "date": date(2026, 1, 1),
        "medium_id": 1,
    }
    defaults.update(overrides)
    return Entry(**defaults)  # type: ignore[arg-type]


def test_needs_omdb_fetch_with_no_rating() -> None:
    assert needs_omdb_fetch(_entry()) is True


def test_needs_omdb_fetch_with_rating_but_no_poster() -> None:
    entry = _entry(imdb_rating="8.5/10", poster_url=None)

    assert needs_omdb_fetch(entry) is True


_ALL_OMDB_FIELDS: dict[str, object] = {
    "imdb_rating": "8.5/10",
    "poster_url": "https://m.media-amazon.com/images/dune-poster.jpg",
    "director": "Denis Villeneuve",
    "actors": "Timothée Chalamet, Rebecca Ferguson, Zendaya",
    "genre": "Action, Adventure, Drama",
    "release_year": 2021,
}


@pytest.mark.parametrize("missing_field", list(_ALL_OMDB_FIELDS))
def test_needs_omdb_fetch_with_one_field_missing_is_true(missing_field: str) -> None:
    fields = {**_ALL_OMDB_FIELDS, missing_field: None}
    entry = _entry(**fields)

    assert needs_omdb_fetch(entry) is True


def test_needs_omdb_fetch_with_every_field_present_is_false() -> None:
    entry = _entry(**_ALL_OMDB_FIELDS)

    assert needs_omdb_fetch(entry) is False


def test_lookup_requires_title_or_imdb_id() -> None:
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    with pytest.raises(ValueError, match="title or imdb_id"):
        client.lookup()


def test_lookup_by_title_and_year_sends_the_year_param() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(title="Dune", year=2021)

    assert seen_params["t"] == "Dune"
    assert seen_params["y"] == "2021"


def test_lookup_falls_back_to_title_only_when_year_scoped_search_finds_nothing() -> None:
    requests_seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        requests_seen.append(params)
        if "y" in params:
            return httpx.Response(200, json=NO_MATCH_RESPONSE)
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    ratings = client.lookup(title="Dune", year=1900)

    assert ratings is not None
    assert ratings.imdb == "8.0/10"
    assert len(requests_seen) == 2
    assert "y" in requests_seen[0]
    assert "y" not in requests_seen[1]


def test_lookup_with_imdb_id_ignores_the_year_hint() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(imdb_id="tt1160419", year=2021)

    assert seen_params["i"] == "tt1160419"
    assert "y" not in seen_params


def test_lookup_by_title_sends_the_type_movie_param() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(title="Dune")

    assert seen_params["type"] == "movie"


def test_lookup_by_imdb_id_sends_no_type_param() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(imdb_id="tt1160419")

    assert "type" not in seen_params


def test_lookup_by_title_rejects_a_series_result() -> None:
    client = _client(lambda request: httpx.Response(200, json=SERIES_RESPONSE))

    ratings = client.lookup(title="Good Boy")

    assert ratings is None


def test_lookup_by_title_rejecting_a_series_result_is_cached() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=SERIES_RESPONSE)

    client = _client(handler)

    client.lookup(title="Good Boy")
    client.lookup(title="Good Boy")

    assert call_count == 1


def test_lookup_by_imdb_id_does_not_reject_a_series_result() -> None:
    """An explicit imdb_id is already an exact, deliberate match - Type
    filtering only guards against an ambiguous title search picking the
    wrong kind of result.
    """
    client = _client(lambda request: httpx.Response(200, json=SERIES_RESPONSE))

    ratings = client.lookup(imdb_id="tt9999999")

    assert ratings is not None
    assert ratings.imdb_id == "tt9999999"


def test_lookup_by_title_with_no_year_sends_no_year_param() -> None:
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(title="Dune")

    assert "y" not in seen_params


def test_lookup_caches_a_year_scoped_match_separately_from_a_plain_one() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    client.lookup(title="Dune", year=2021)
    client.lookup(title="Dune")

    assert call_count == 2


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


def test_fetch_and_store_ratings_uses_the_entrys_year_as_a_hint(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=MATCH_RESPONSE)

    client = _client(handler)

    fetch_and_store_ratings(store, client, entry)

    assert seen_params["y"] == "2026"


def test_fetch_and_store_ratings_sets_imdb_url_from_the_imdb_id(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    updated, _ = fetch_and_store_ratings(store, client, entry)

    assert updated.imdb_url == "https://www.imdb.com/title/tt1160419/"
    assert store.get_entry(entry.id).imdb_url == "https://www.imdb.com/title/tt1160419/"


def test_fetch_and_store_ratings_persists_the_poster_url(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    updated, _ = fetch_and_store_ratings(store, client, entry)

    assert updated.poster_url == "https://m.media-amazon.com/images/dune-poster.jpg"
    assert (
        store.get_entry(entry.id).poster_url == "https://m.media-amazon.com/images/dune-poster.jpg"
    )


def test_fetch_and_store_ratings_persists_director_actors_genre_and_release_year(
    store: Store,
) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    updated, _ = fetch_and_store_ratings(store, client, entry)

    assert updated.director == "Denis Villeneuve"
    assert updated.actors == "Timothée Chalamet, Rebecca Ferguson, Zendaya"
    assert updated.genre == "Action, Adventure, Drama"
    assert updated.release_year == 2021
    stored = store.get_entry(entry.id)
    assert stored.director == "Denis Villeneuve"
    assert stored.actors == "Timothée Chalamet, Rebecca Ferguson, Zendaya"
    assert stored.genre == "Action, Adventure, Drama"
    assert stored.release_year == 2021


def test_fetch_and_store_ratings_persists_the_rest_of_omdbs_fields(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))

    fetch_and_store_ratings(store, client, entry)

    stored = store.get_entry(entry.id)
    assert stored.rated == "PG-13"
    assert stored.released == "22 Oct 2021"
    assert stored.runtime == "155 min"
    assert stored.writer == "Jon Spaihts, Denis Villeneuve, Eric Roth"
    assert stored.plot == "Paul Atreides unites with the Fremen to seek revenge."
    assert stored.language == "English, Mandarin"
    assert stored.country == "United States, Canada"
    assert stored.awards == "Won 6 Oscars. 175 wins & 235 nominations total"
    assert stored.metascore == "74"
    assert stored.imdb_votes == "757,451"
    assert stored.dvd == "22 Nov 2021"
    assert stored.box_office == "$108,327,830"
    assert stored.production == "Legendary Pictures"
    assert stored.website == "https://www.dunemovie.com"


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


def test_fetch_and_store_ratings_on_no_match_records_todays_date(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Not A Real Movie", date=date(2026, 1, 1), medium_id=medium.id)
    client = _client(lambda request: httpx.Response(200, json=NO_MATCH_RESPONSE))

    updated, found = fetch_and_store_ratings(store, client, entry)

    assert found is False
    assert updated.omdb_last_no_match == date.today()
    reloaded = store.get_entry(entry.id)
    assert reloaded.omdb_last_no_match == date.today()


def test_fetch_and_store_ratings_on_a_match_clears_a_prior_no_match(store: Store) -> None:
    medium = store.add_medium("cinema", is_physical_place=True)
    entry = store.create_entry(title="Dune", date=date(2026, 1, 1), medium_id=medium.id)
    entry = store.update_entry(entry.id, omdb_last_no_match=date(2026, 1, 1))

    client = _client(lambda request: httpx.Response(200, json=MATCH_RESPONSE))
    updated, found = fetch_and_store_ratings(store, client, entry)

    assert found is True
    assert updated.omdb_last_no_match is None


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
