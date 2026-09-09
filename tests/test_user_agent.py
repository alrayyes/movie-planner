from importlib.metadata import PackageNotFoundError

import pytest

from movie_planner.user_agent import _movie_planner_version


def test_movie_planner_version_looks_up_the_movie_planner_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_names: list[str] = []

    def fake_version(name: str) -> str:
        seen_names.append(name)
        return "9.9.9"

    monkeypatch.setattr("movie_planner.user_agent.version", fake_version)

    assert _movie_planner_version() == "9.9.9"
    assert seen_names == ["movie-planner"]


def test_movie_planner_version_falls_back_when_package_metadata_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Reproduces PKGBUILD/flake.nix's man-page generation, which imports
    # movie_planner.cli straight off the source tree (PYTHONPATH="src")
    # with no installed dist-info metadata for importlib.metadata to find -
    # movie-planner#357's regression, which broke the aur/nix CI jobs.
    def raise_not_found(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr("movie_planner.user_agent.version", raise_not_found)

    assert _movie_planner_version() == "0.0.0"
