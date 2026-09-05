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
    imdb_id: str | None = None
    poster: str | None = None


def needs_omdb_fetch(entry: Entry) -> bool:
    """Whether an entry is missing any OMDb-derived field it could have -
    not just the rating, so an entry logged before a field like
    `poster_url` existed still gets backfilled by a plain `sync refresh`,
    not just `--force`. Update this alongside adding any future
    OMDb-derived field (director/genre/etc., issue #88) - it's the one
    place "does this entry need fetching" is decided.
    """
    return entry.imdb_rating is None or entry.poster_url is None


def _rating(ratings: list[dict[str, object]], source: str) -> str | None:
    for entry in ratings:
        if entry.get("Source") == source:
            value = entry.get("Value")
            return value if isinstance(value, str) else None
    return None


class OmdbClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._http = http_client or httpx.Client(base_url="https://www.omdbapi.com/")
        self._cache: dict[str, MovieRatings | None] = {}

    def lookup(
        self,
        *,
        title: str | None = None,
        imdb_id: str | None = None,
        year: int | None = None,
    ) -> MovieRatings | None:
        if not title and not imdb_id:
            raise ValueError("lookup needs a title or imdb_id")

        # A watched-year hint only makes sense for a title search - an
        # imdb_id is already exact - and is disambiguation, not a strict
        # filter: a re-watch of an older film has a watched-year that's
        # never the release year, so a year-scoped miss falls back to a
        # plain title search rather than reporting no match.
        if title and not imdb_id and year is not None:
            year_scoped = self._lookup_one(title=title, imdb_id=None, year=year)
            if year_scoped is not None:
                return year_scoped
        return self._lookup_one(title=title, imdb_id=imdb_id, year=None)

    def _lookup_one(
        self, *, title: str | None, imdb_id: str | None, year: int | None
    ) -> MovieRatings | None:
        cache_key_base = imdb_id or title
        # Validated by the caller: at least one of imdb_id/title is set.
        assert cache_key_base is not None  # nosec B101
        cache_key = f"{cache_key_base}|{year}" if year is not None else cache_key_base
        if cache_key in self._cache:
            return self._cache[cache_key]

        params: dict[str, str] = {"apikey": self._api_key}
        params["i" if imdb_id else "t"] = cache_key_base
        if year is not None:
            params["y"] = str(year)

        response = self._http.get("/", params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("Response") == "False":
            self._cache[cache_key] = None
            return None

        response_imdb_id = data.get("imdbID")
        poster = data.get("Poster")
        ratings = MovieRatings(
            imdb=_rating(data.get("Ratings", []), "Internet Movie Database"),
            rotten_tomatoes=_rating(data.get("Ratings", []), "Rotten Tomatoes"),
            metacritic=_rating(data.get("Ratings", []), "Metacritic"),
            imdb_id=response_imdb_id if isinstance(response_imdb_id, str) else None,
            poster=poster if isinstance(poster, str) and poster != "N/A" else None,
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
    ratings = client.lookup(title=entry.title, imdb_id=imdb_id, year=entry.date.year)
    if ratings is None:
        return entry, False
    imdb_url = entry.imdb_url or (
        f"https://www.imdb.com/title/{ratings.imdb_id}/" if ratings.imdb_id else None
    )
    updated = store.update_entry(
        entry.id,
        imdb_rating=ratings.imdb,
        rotten_tomatoes_rating=ratings.rotten_tomatoes,
        metacritic_rating=ratings.metacritic,
        imdb_url=imdb_url,
        poster_url=ratings.poster,
    )
    return updated, True
