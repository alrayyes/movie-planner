"""Looks up a movie's official YouTube trailer on TMDb, given the imdb_id
OMDb's own response already carries - no separate search, since TMDb's
"find by external ID" endpoint takes one directly. Two calls per lookup
(find, then videos); successful and empty lookups are both cached so
re-editing an entry doesn't repeat either call for a title already
resolved. Trailer lookup is best-effort throughout: a config with no
tmdb.api_key set, a miss, or an API error all just mean no trailer, never
a hard failure - see movie-planner#236.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class TmdbClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._http = http_client or httpx.Client(base_url="https://api.themoviedb.org/3/")
        self._cache: dict[str, str | None] = {}

    def lookup_trailer_url(self, *, imdb_id: str) -> str | None:
        if imdb_id in self._cache:
            return self._cache[imdb_id]

        tmdb_id = self._find_movie_id(imdb_id)
        if tmdb_id is None:
            self._cache[imdb_id] = None
            return None

        url = self._find_trailer_url(tmdb_id)
        self._cache[imdb_id] = url
        return url

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

    def _find_trailer_url(self, tmdb_id: int) -> str | None:
        logger.debug("TMDb videos request: tmdb_id=%s", tmdb_id)
        response = self._http.get(f"movie/{tmdb_id}/videos", params={"api_key": self._api_key})
        response.raise_for_status()
        for video in response.json().get("results", []):
            if (
                video.get("type") == "Trailer"
                and video.get("official") is True
                and video.get("site") == "YouTube"
                and video.get("key")
            ):
                url = f"https://www.youtube.com/watch?v={video['key']}"
                logger.debug("TMDb videos response: tmdb_id=%s -> %s", tmdb_id, url)
                return url
        logger.debug("TMDb videos response: tmdb_id=%s -> no official YouTube trailer", tmdb_id)
        return None
