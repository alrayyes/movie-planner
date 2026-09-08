import logging
from collections.abc import Callable

import httpx
import pytest

from movie_planner.tmdb import TmdbClient

FIND_RESPONSE = {
    "movie_results": [{"id": 438631}],
    "tv_results": [],
}

_BASE_DETAILS: dict[str, object] = {
    "homepage": "",
    "budget": 0,
    "popularity": 0.0,
    "belongs_to_collection": None,
    "credits": {"cast": []},
    "videos": {"results": []},
    "release_dates": {"results": []},
    "keywords": {"keywords": []},
}


def _details(**overrides: object) -> dict[str, object]:
    return {**_BASE_DETAILS, **overrides}


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> TmdbClient:
    http_client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.themoviedb.org/3/"
    )
    return TmdbClient(api_key="test-key", http_client=http_client)


def _handler_for(
    details: dict[str, object],
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/3/find/tt1160419":
            assert dict(request.url.params)["external_source"] == "imdb_id"
            assert dict(request.url.params)["api_key"] == "test-key"
            return httpx.Response(200, json=FIND_RESPONSE)
        assert request.url.path == "/3/movie/438631"
        params = dict(request.url.params)
        assert params["api_key"] == "test-key"
        assert params["append_to_response"] == "credits,videos,release_dates,keywords"
        return httpx.Response(200, json=details)

    return handler


def test_lookup_movie_details_no_movie_match_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"movie_results": [], "tv_results": []})

    client = _client(handler)

    assert client.lookup_movie_details(imdb_id="tt0000000") is None


def test_lookup_movie_details_returns_the_official_youtube_trailer() -> None:
    details = _details(
        videos={
            "results": [
                {"key": "n9xhJrPXop4", "type": "Teaser", "official": True, "site": "YouTube"},
                {"key": "8g18jFHCLXk", "type": "Trailer", "official": True, "site": "YouTube"},
                {"key": "unofficial123", "type": "Trailer", "official": False, "site": "YouTube"},
            ]
        }
    )
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.trailer_url == "https://www.youtube.com/watch?v=8g18jFHCLXk"


def test_lookup_movie_details_ignores_unofficial_and_non_trailer_videos() -> None:
    details = _details(
        videos={
            "results": [
                {"key": "teaser1", "type": "Teaser", "official": True, "site": "YouTube"},
                {"key": "unofficial1", "type": "Trailer", "official": False, "site": "YouTube"},
                {"key": "vimeo1", "type": "Trailer", "official": True, "site": "Vimeo"},
            ]
        }
    )
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.trailer_url is None


def test_lookup_movie_details_returns_the_full_cast_in_billing_order() -> None:
    details = _details(
        credits={
            "cast": [
                {"name": "Kirsten Dunst", "order": 0},
                {"name": "Wagner Moura", "order": 1},
                {"name": "Cailee Spaeny", "order": 2},
                {"name": "Stephen McKinley Henderson", "order": 3},
                {"name": "Nick Offerman", "order": 4},
            ]
        }
    )
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.actors == (
        "Kirsten Dunst, Wagner Moura, Cailee Spaeny, Stephen McKinley Henderson, Nick Offerman"
    )


def test_lookup_movie_details_sorts_cast_by_billing_order_even_if_the_response_does_not() -> None:
    details = _details(
        credits={
            "cast": [
                {"name": "Second Billed", "order": 1},
                {"name": "First Billed", "order": 0},
            ]
        }
    )
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.actors == "First Billed, Second Billed"


def test_lookup_movie_details_with_no_cast_is_none() -> None:
    client = _client(_handler_for(_details()))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.actors is None


def test_lookup_movie_details_reads_the_collection_name() -> None:
    details = _details(belongs_to_collection={"id": 1241, "name": "Civil War Collection"})
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.collection == "Civil War Collection"


def test_lookup_movie_details_with_no_collection_is_none() -> None:
    client = _client(_handler_for(_details(belongs_to_collection=None)))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.collection is None


def test_lookup_movie_details_reads_the_us_certification() -> None:
    details = _details(
        release_dates={
            "results": [
                {
                    "iso_3166_1": "NL",
                    "release_dates": [{"certification": "12", "type": 3}],
                },
                {
                    "iso_3166_1": "US",
                    "release_dates": [{"certification": "R", "type": 3}],
                },
            ]
        }
    )
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.certification == "R"


def test_lookup_movie_details_skips_a_blank_us_certification() -> None:
    # A real TMDb response can list the US among release_dates.results
    # with every certification entry blank - that's "not certified",
    # not "certification unknown", but this module treats both the same
    # way: omit, never guess a rating that was never actually assigned.
    details = _details(
        release_dates={
            "results": [
                {"iso_3166_1": "US", "release_dates": [{"certification": "", "type": 3}]},
            ]
        }
    )
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.certification is None


def test_lookup_movie_details_with_no_us_certification_is_none() -> None:
    # Deliberately no fallback to another country's rating system - a
    # certification from an incompatible system would be actively
    # misleading, not just incomplete.
    details = _details(
        release_dates={
            "results": [
                {"iso_3166_1": "NL", "release_dates": [{"certification": "12", "type": 3}]},
            ]
        }
    )
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.certification is None


def test_lookup_movie_details_reads_the_homepage() -> None:
    details = _details(homepage="https://civilwar.movie")
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.homepage == "https://civilwar.movie"


def test_lookup_movie_details_with_a_blank_homepage_is_none() -> None:
    client = _client(_handler_for(_details(homepage="")))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.homepage is None


def test_lookup_movie_details_reads_keywords() -> None:
    details = _details(
        keywords={"keywords": [{"id": 1, "name": "dystopia"}, {"id": 2, "name": "journalism"}]}
    )
    client = _client(_handler_for(details))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.keywords == "dystopia, journalism"


def test_lookup_movie_details_with_no_keywords_is_none() -> None:
    client = _client(_handler_for(_details()))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.keywords is None


def test_lookup_movie_details_reads_a_positive_budget() -> None:
    client = _client(_handler_for(_details(budget=50_000_000)))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.budget == 50_000_000


def test_lookup_movie_details_treats_a_zero_budget_as_unknown() -> None:
    # TMDb uses 0 as "no budget entered", not a real free-to-make movie -
    # same "N/A means absent" convention OMDb's own fields already use.
    client = _client(_handler_for(_details(budget=0)))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.budget is None


def test_lookup_movie_details_reads_popularity() -> None:
    client = _client(_handler_for(_details(popularity=83.421)))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.popularity == 83.421


def test_lookup_movie_details_a_genuine_zero_popularity_is_kept() -> None:
    # Unlike budget, 0.0 is a real, meaningful score here (an obscure
    # title nobody's looked at) rather than TMDb's placeholder for
    # "nothing entered" - so it's kept, not treated as unknown.
    client = _client(_handler_for(_details(popularity=0.0)))

    result = client.lookup_movie_details(imdb_id="tt1160419")

    assert result is not None
    assert result.popularity == 0.0


def test_lookup_movie_details_caches_by_imdb_id() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if "find" in request.url.path:
            return httpx.Response(200, json=FIND_RESPONSE)
        return httpx.Response(200, json=_details())

    client = _client(handler)

    first = client.lookup_movie_details(imdb_id="tt1160419")
    second = client.lookup_movie_details(imdb_id="tt1160419")

    assert first == second
    assert calls == 2  # one find + one details call, never repeated for the same imdb_id


def test_lookup_movie_details_no_match_is_cached_too() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"movie_results": [], "tv_results": []})

    client = _client(handler)

    client.lookup_movie_details(imdb_id="tt0000000")
    client.lookup_movie_details(imdb_id="tt0000000")

    assert calls == 1


def test_lookup_movie_details_logs_both_requests_at_debug_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _client(_handler_for(_details()))

    with caplog.at_level(logging.DEBUG, logger="movie_planner.tmdb"):
        client.lookup_movie_details(imdb_id="tt1160419")

    messages = [r.message for r in caplog.records]
    assert any("tt1160419" in m for m in messages)
    assert any("438631" in m for m in messages)
