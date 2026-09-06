"""Fetches IMDb/Rotten Tomatoes/Metacritic ratings from OMDb, one call per
title or IMDb ID. See design.md's "OMDb free-tier rate limit" risk -
successful lookups are cached so re-editing an entry doesn't re-fetch a
title already matched.
"""

import re
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
    director: str | None = None
    actors: str | None = None
    genre: str | None = None
    release_year: int | None = None
    # The rest of OMDb's response (issue #237) - free, since it's the
    # same call already being made for the fields above, not a second
    # request. Deliberately NOT added to needs_omdb_fetch below: unlike
    # the fields above, several of these (dvd/box_office/production/
    # website in particular) are routinely "N/A" even for a real
    # match - treating their absence as "still needs fetching" would
    # re-fetch forever for a title OMDb simply has no data for. A
    # fetch already happening for another reason still captures these
    # for free; --force is the explicit way to backfill an
    # already-complete older entry.
    rated: str | None = None
    released: str | None = None
    runtime: str | None = None
    writer: str | None = None
    plot: str | None = None
    language: str | None = None
    country: str | None = None
    awards: str | None = None
    metascore: str | None = None
    imdb_votes: str | None = None
    dvd: str | None = None
    box_office: str | None = None
    production: str | None = None
    website: str | None = None


def needs_omdb_fetch(entry: Entry) -> bool:
    """Whether an entry is missing any OMDb-derived field it could have -
    not just the rating, so an entry logged before a field like
    `poster_url` existed still gets backfilled by a plain `sync refresh`,
    not just `--force`. Update this alongside adding any future
    OMDb-derived field - it's the one place "does this entry need
    fetching" is decided.
    """
    return (
        entry.imdb_rating is None
        or entry.poster_url is None
        or entry.director is None
        or entry.actors is None
        or entry.genre is None
        or entry.release_year is None
    )


def _rating(ratings: list[dict[str, object]], source: str) -> str | None:
    for entry in ratings:
        if entry.get("Source") == source:
            value = entry.get("Value")
            return value if isinstance(value, str) else None
    return None


def _na_or(value: object) -> str | None:
    return value if isinstance(value, str) and value != "N/A" else None


# A Pathé confirmation title sometimes carries a trailing format/
# edition marker OMDb's own title search doesn't recognize and never
# matches (movie-planner#216, quantified against a real historical
# import: 76 of 146 lookups failed on exactly this). Stripped only for
# the search string - the stored entry.title is never touched, since
# the format is real information, just not part of the movie's name.
_FORMAT_SUFFIX_RE = re.compile(
    r"\s*\(?\b(?:OV|NL|DOV|O3D|3D|4DX|IMAX|Dolby|Cinema|Atmos"
    # Dutch "Original Version" (movie-planner#224) - stripped word by
    # word, same as "Dolby Cinema" already is, so "(Originele versie)"
    # resolves in two passes rather than needing its own phrase match.
    r"|Originele|versie)\b\)?\s*$",
    re.IGNORECASE,
)


def _strip_format_suffix(title: str) -> str:
    cleaned = title
    while True:
        match = _FORMAT_SUFFIX_RE.search(cleaned)
        if not match or not cleaned[: match.start()].strip():
            # No more trailing suffix, or stripping it would empty the
            # title out entirely (it was the whole string, not a real
            # suffix on a real title) - stop either way.
            return cleaned
        cleaned = cleaned[: match.start()]


_YEAR_RE = re.compile(r"\d{4}")


def _parse_release_year(value: object) -> int | None:
    # OMDb's "Year" is a plain "2021" for a movie, but a range like
    # "2019-2023" or open-ended "2019-" for a series - take the first
    # four-digit run either way.
    if not isinstance(value, str):
        return None
    match = _YEAR_RE.search(value)
    return int(match.group()) if match else None


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

        # Cleaned once, up front, so both the cache key and the actual
        # search below use the same stripped title regardless of
        # whether the year-scoped branch runs - "X (OV)" and "X" then
        # share one cache entry and one API call (movie-planner#216).
        search_title = _strip_format_suffix(title) if title is not None else None

        # A watched-year hint only makes sense for a title search - an
        # imdb_id is already exact - and is disambiguation, not a strict
        # filter: a re-watch of an older film has a watched-year that's
        # never the release year, so a year-scoped miss falls back to a
        # plain title search rather than reporting no match.
        if search_title and not imdb_id and year is not None:
            year_scoped = self._lookup_one(title=search_title, imdb_id=None, year=year)
            if year_scoped is not None:
                return year_scoped
        return self._lookup_one(title=search_title, imdb_id=imdb_id, year=None)

    def _lookup_one(
        self, *, title: str | None, imdb_id: str | None, year: int | None
    ) -> MovieRatings | None:
        cache_key_base = imdb_id or title
        # Validated by the caller: at least one of imdb_id/title is set.
        assert cache_key_base is not None  # nosec B101
        cache_key = f"{cache_key_base}|{year}" if year is not None else cache_key_base
        if cache_key in self._cache:
            return self._cache[cache_key]

        # A bare title is ambiguous - OMDb may resolve it to a TV series of
        # the same name - so title searches are restricted to movies both
        # server-side (the `type` param) and again below on the response,
        # in case OMDb's own filter lets one through anyway. An imdb_id is
        # already an exact, deliberate match and isn't filtered.
        title_search = title is not None and imdb_id is None
        params: dict[str, str] = {"apikey": self._api_key}
        params["i" if imdb_id else "t"] = cache_key_base
        if title_search:
            params["type"] = "movie"
        if year is not None:
            params["y"] = str(year)

        response = self._http.get("/", params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("Response") == "False":
            self._cache[cache_key] = None
            return None

        if title_search and data.get("Type") not in (None, "movie"):
            self._cache[cache_key] = None
            return None

        response_imdb_id = data.get("imdbID")
        ratings = MovieRatings(
            imdb=_rating(data.get("Ratings", []), "Internet Movie Database"),
            rotten_tomatoes=_rating(data.get("Ratings", []), "Rotten Tomatoes"),
            metacritic=_rating(data.get("Ratings", []), "Metacritic"),
            imdb_id=response_imdb_id if isinstance(response_imdb_id, str) else None,
            poster=_na_or(data.get("Poster")),
            director=_na_or(data.get("Director")),
            actors=_na_or(data.get("Actors")),
            genre=_na_or(data.get("Genre")),
            release_year=_parse_release_year(data.get("Year")),
            rated=_na_or(data.get("Rated")),
            released=_na_or(data.get("Released")),
            runtime=_na_or(data.get("Runtime")),
            writer=_na_or(data.get("Writer")),
            plot=_na_or(data.get("Plot")),
            language=_na_or(data.get("Language")),
            country=_na_or(data.get("Country")),
            awards=_na_or(data.get("Awards")),
            metascore=_na_or(data.get("Metascore")),
            imdb_votes=_na_or(data.get("imdbVotes")),
            dvd=_na_or(data.get("DVD")),
            box_office=_na_or(data.get("BoxOffice")),
            production=_na_or(data.get("Production")),
            website=_na_or(data.get("Website")),
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
        director=ratings.director,
        actors=ratings.actors,
        genre=ratings.genre,
        release_year=ratings.release_year,
        rated=ratings.rated,
        released=ratings.released,
        runtime=ratings.runtime,
        writer=ratings.writer,
        plot=ratings.plot,
        language=ratings.language,
        country=ratings.country,
        awards=ratings.awards,
        metascore=ratings.metascore,
        imdb_votes=ratings.imdb_votes,
        dvd=ratings.dvd,
        box_office=ratings.box_office,
        production=ratings.production,
        website=ratings.website,
    )
    return updated, True
