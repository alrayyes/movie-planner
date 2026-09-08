"""Looks up a movie's TMDb details, given the imdb_id OMDb's own response
already carries - no separate search, since TMDb's "find by external ID"
endpoint takes one directly. Two calls per lookup (find, then one enriched
movie-details call via append_to_response): full cast, trailer, collection,
content certification, homepage, keywords, budget, and popularity all come
back together (issue #311) - not one call per field. Successful and empty
lookups are both cached so re-editing an entry doesn't repeat either call
for a title already resolved. Lookup is best-effort throughout: a config
with no tmdb.api_key set, a miss, or an API error all just mean no TMDb
data, never a hard failure - see movie-planner#236.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# The default for content certification (issue #311) - the most widely
# recognized rating system (MPAA), and TMDb's release_dates carries a
# certification per country with no single "the" certification to prefer
# instead. Deliberately no fallback to another country: a certification
# from an incompatible rating system would be actively misleading, not
# just less complete.
_CERTIFICATION_COUNTRY = "US"


@dataclass(frozen=True)
class TmdbMovieDetails:
    trailer_url: str | None = None
    actors: str | None = None
    collection: str | None = None
    certification: str | None = None
    homepage: str | None = None
    keywords: str | None = None
    budget: int | None = None
    popularity: float | None = None


def _trailer_url(videos: list[dict[str, object]]) -> str | None:
    for video in videos:
        if (
            video.get("type") == "Trailer"
            and video.get("official") is True
            and video.get("site") == "YouTube"
            and video.get("key")
        ):
            return f"https://www.youtube.com/watch?v={video['key']}"
    return None


def _order(member: dict[str, object]) -> int:
    order = member.get("order")
    return order if isinstance(order, int) else 0


def _actors(cast: list[dict[str, object]]) -> str | None:
    named = [member for member in cast if isinstance(member.get("name"), str)]
    names = [str(member["name"]) for member in sorted(named, key=_order)]
    return ", ".join(names) if names else None


def _collection(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    return name if isinstance(name, str) and name else None


def _certification(release_dates: list[dict[str, object]]) -> str | None:
    for country in release_dates:
        if country.get("iso_3166_1") != _CERTIFICATION_COUNTRY:
            continue
        entries = country.get("release_dates")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            certification = entry.get("certification") if isinstance(entry, dict) else None
            if isinstance(certification, str) and certification:
                return certification
    return None


def _keywords(keywords: list[dict[str, object]]) -> str | None:
    names = [name for k in keywords if isinstance(name := k.get("name"), str)]
    return ", ".join(names) if names else None


def _na_or(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _budget(value: object) -> int | None:
    # 0 is TMDb's "nothing entered", not a real free-to-make movie - same
    # "absent means N/A" convention OMDb's own fields already use.
    return value if isinstance(value, int) and value > 0 else None


def _popularity(value: object) -> float | None:
    # Unlike budget, a genuine 0.0 is real data here (an obscure title
    # nobody's looked at), not TMDb's placeholder for "unknown" - only a
    # missing/non-numeric value maps to None.
    return float(value) if isinstance(value, int | float) else None


class TmdbClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._http = http_client or httpx.Client(base_url="https://api.themoviedb.org/3/")
        self._cache: dict[str, TmdbMovieDetails | None] = {}

    def lookup_movie_details(self, *, imdb_id: str) -> TmdbMovieDetails | None:
        if imdb_id in self._cache:
            return self._cache[imdb_id]

        tmdb_id = self._find_movie_id(imdb_id)
        if tmdb_id is None:
            self._cache[imdb_id] = None
            return None

        details = self._fetch_movie_details(tmdb_id)
        self._cache[imdb_id] = details
        return details

    def _find_movie_id(self, imdb_id: str) -> int | None:
        logger.debug("TMDb find request: imdb_id=%s", imdb_id)
        response = self._http.get(
            f"find/{imdb_id}",
            params={"api_key": self._api_key, "external_source": "imdb_id"},
        )
        response.raise_for_status()
        movie_results = response.json().get("movie_results") or []
        if not movie_results:
            logger.debug("TMDb find response: no movie match for imdb_id=%s", imdb_id)
            return None
        tmdb_id = movie_results[0].get("id")
        tmdb_id = tmdb_id if isinstance(tmdb_id, int) else None
        logger.debug("TMDb find response: imdb_id=%s -> tmdb_id=%s", imdb_id, tmdb_id)
        return tmdb_id

    def _fetch_movie_details(self, tmdb_id: int) -> TmdbMovieDetails:
        logger.debug("TMDb movie details request: tmdb_id=%s", tmdb_id)
        response = self._http.get(
            f"movie/{tmdb_id}",
            params={
                "api_key": self._api_key,
                "append_to_response": "credits,videos,release_dates,keywords",
            },
        )
        response.raise_for_status()
        data = response.json()
        details = TmdbMovieDetails(
            trailer_url=_trailer_url(data.get("videos", {}).get("results", [])),
            actors=_actors(data.get("credits", {}).get("cast", [])),
            collection=_collection(data.get("belongs_to_collection")),
            certification=_certification(data.get("release_dates", {}).get("results", [])),
            homepage=_na_or(data.get("homepage")),
            keywords=_keywords(data.get("keywords", {}).get("keywords", [])),
            budget=_budget(data.get("budget")),
            popularity=_popularity(data.get("popularity")),
        )
        logger.debug("TMDb movie details response: tmdb_id=%s -> %s", tmdb_id, details)
        return details
