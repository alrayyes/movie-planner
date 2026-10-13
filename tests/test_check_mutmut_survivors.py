"""The diff-scoped mutmut run (movie-planner#385): which mutants a PR's files own."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_mutmut_survivors.py"
spec = importlib.util.spec_from_file_location("check_mutmut_survivors", SCRIPT)
assert spec is not None and spec.loader is not None
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_a_module_owns_every_mutant_under_its_dotted_name() -> None:
    assert gate.mutant_globs(["src/movie_planner/cli.py"]) == ["movie_planner.cli.*"]


def test_a_nested_module_keeps_its_package_in_the_name() -> None:
    assert gate.mutant_globs(["src/movie_planner/mail_import/cli.py"]) == [
        "movie_planner.mail_import.cli.*"
    ]


def test_several_files_give_one_glob_each() -> None:
    assert gate.mutant_globs(["src/movie_planner/cli.py", "src/movie_planner/omdb.py"]) == [
        "movie_planner.cli.*",
        "movie_planner.omdb.*",
    ]


def test_files_outside_src_or_not_python_own_no_mutants() -> None:
    assert gate.mutant_globs(["tests/test_cli.py", "README.md", "src/movie_planner/py.typed"]) == []


def test_no_files_means_nothing_to_mutate() -> None:
    assert gate.mutant_globs([]) == []


def test_a_package_init_falls_back_to_every_mutant() -> None:
    # `movie_planner.mail_import.*` would also match the package's submodules,
    # and `movie_planner.*` every module, so an __init__.py can't be scoped.
    assert gate.mutant_globs(["src/movie_planner/mail_import/__init__.py"]) == ["*"]
    assert gate.mutant_globs(["src/movie_planner/cli.py", "src/movie_planner/__init__.py"]) == ["*"]


def test_unrun_mutants_mean_the_results_are_partial() -> None:
    # generate rewrites the baseline from these results, so after a scoped run
    # it would drop every file that wasn't run.
    partial = (
        "movie_planner.cli.x_a__mutmut_1: killed\nmovie_planner.omdb.x_b__mutmut_1: not checked\n"
    )
    assert gate.has_unrun_mutants(partial)


def test_a_full_run_has_no_unrun_mutants() -> None:
    full = "movie_planner.cli.x_a__mutmut_1: killed\nmovie_planner.omdb.x_b__mutmut_1: survived\n"
    assert not gate.has_unrun_mutants(full)
