from collections.abc import Callable

import httpx

from movie_planner.tmdb import TmdbClient

FIND_RESPONSE = {
    "movie_results": [{"id": 438631}],
    "tv_results": [],
}

VIDEOS_RESPONSE = {
    "results": [
        {
            "key": "n9xhJrPXop4",
            "type": "Teaser",
            "official": True,
            "site": "YouTube",
        },
        {
            "key": "8g18jFHCLXk",
            "type": "Trailer",
            "official": True,
            "site": "YouTube",
        },
        {
            "key": "unofficial123",
            "type": "Trailer",
            "official": False,
            "site": "YouTube",
        },
    ]
}


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> TmdbClient:
    http_client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.themoviedb.org/3/"
    )
    return TmdbClient(api_key="test-key", http_client=http_client)


def test_lookup_trailer_url_returns_the_official_youtube_trailer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/3/find/tt1160419":
            assert dict(request.url.params)["external_source"] == "imdb_id"
            assert dict(request.url.params)["api_key"] == "test-key"
            return httpx.Response(200, json=FIND_RESPONSE)
        assert request.url.path == "/3/movie/438631/videos"
        assert dict(request.url.params)["api_key"] == "test-key"
        return httpx.Response(200, json=VIDEOS_RESPONSE)

    client = _client(handler)

    url = client.lookup_trailer_url(imdb_id="tt1160419")

    assert url == "https://www.youtube.com/watch?v=8g18jFHCLXk"


def test_lookup_trailer_url_ignores_unofficial_and_non_trailer_videos() -> None:
    videos = {
        "results": [
            {"key": "teaser1", "type": "Teaser", "official": True, "site": "YouTube"},
            {"key": "unofficial1", "type": "Trailer", "official": False, "site": "YouTube"},
            {"key": "vimeo1", "type": "Trailer", "official": True, "site": "Vimeo"},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "find" in request.url.path:
            return httpx.Response(200, json=FIND_RESPONSE)
        return httpx.Response(200, json=videos)

    client = _client(handler)

    assert client.lookup_trailer_url(imdb_id="tt1160419") is None


def test_lookup_trailer_url_no_movie_match_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"movie_results": [], "tv_results": []})

    client = _client(handler)

    assert client.lookup_trailer_url(imdb_id="tt0000000") is None


def test_lookup_trailer_url_caches_by_imdb_id() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if "find" in request.url.path:
            return httpx.Response(200, json=FIND_RESPONSE)
        return httpx.Response(200, json=VIDEOS_RESPONSE)

    client = _client(handler)

    first = client.lookup_trailer_url(imdb_id="tt1160419")
    second = client.lookup_trailer_url(imdb_id="tt1160419")

    assert first == second == "https://www.youtube.com/watch?v=8g18jFHCLXk"
    assert calls == 2  # one find + one videos call, never repeated for the same imdb_id


def test_lookup_trailer_url_no_match_is_cached_too() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"movie_results": [], "tv_results": []})

    client = _client(handler)

    client.lookup_trailer_url(imdb_id="tt0000000")
    client.lookup_trailer_url(imdb_id="tt0000000")

    assert calls == 1
