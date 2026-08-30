"""Fetches IMDb/Rotten Tomatoes/Metacritic ratings from OMDb, one call per
title or IMDb ID. See design.md's "OMDb free-tier rate limit" risk -
successful lookups are cached so re-editing an entry doesn't re-fetch a
title already matched.
"""

from dataclasses import dataclass

import httpx

from movie_planner.store import Entry, Store


@dataclass(frozen=True)
class MovieRatings:
    imdb: str | None
    rotten_tomatoes: str | None
    metacritic: str | None


def _rating(ratings: list[dict], source: str) -> str | None:
    for entry in ratings:
        if entry.get("Source") == source:
            return entry.get("Value")
    return None


class OmdbClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._http = http_client or httpx.Client(base_url="https://www.omdbapi.com/")
        self._cache: dict[str, MovieRatings | None] = {}

    def lookup(
        self, *, title: str | None = None, imdb_id: str | None = None
    ) -> MovieRatings | None:
        if not title and not imdb_id:
            raise ValueError("lookup needs a title or imdb_id")

        cache_key = imdb_id or title
        assert cache_key is not None
        if cache_key in self._cache:
            return self._cache[cache_key]

        params = {"apikey": self._api_key}
        params["i" if imdb_id else "t"] = imdb_id or title

        response = self._http.get("/", params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("Response") == "False":
            self._cache[cache_key] = None
            return None

        ratings = MovieRatings(
            imdb=_rating(data.get("Ratings", []), "Internet Movie Database"),
            rotten_tomatoes=_rating(data.get("Ratings", []), "Rotten Tomatoes"),
            metacritic=_rating(data.get("Ratings", []), "Metacritic"),
        )
        self._cache[cache_key] = ratings
        return ratings


def fetch_and_store_ratings(
    store: Store,
    client: OmdbClient,
    entry: Entry,
    *,
    imdb_id: str | None = None,
) -> tuple[Entry, bool]:
    """Looks up `entry`'s title (or `imdb_id`, when known) and stores
    whatever OMDb returns. Returns the entry (updated only on a match)
    and whether a match was found, so the caller can tell the user when
    it wasn't.
    """
    ratings = client.lookup(title=entry.title, imdb_id=imdb_id)
    if ratings is None:
        return entry, False
    updated = store.update_entry(
        entry.id,
        imdb_rating=ratings.imdb,
        rotten_tomatoes_rating=ratings.rotten_tomatoes,
        metacritic_rating=ratings.metacritic,
    )
    return updated, True
