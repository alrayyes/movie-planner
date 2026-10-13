"""The `User-Agent` header every outgoing request carries, so OMDb, TMDB,
and the Baikal CalDAV server can all tell which movie-planner version is
talking to them from their own access logs.
"""

from importlib.metadata import PackageNotFoundError, version


def _movie_planner_version() -> str:
    # PKGBUILD and flake.nix both generate man pages by importing
    # movie_planner.cli straight off the source tree (PYTHONPATH="src"),
    # with no installed dist-info metadata for importlib.metadata to find -
    # this has to degrade quietly there rather than break packaging.
    try:
        return version("movie-planner")
    except PackageNotFoundError:
        return "0.0.0"


USER_AGENT_HEADER = {"User-Agent": f"movie-planner/{_movie_planner_version()}"}
