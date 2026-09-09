#!/usr/bin/env python3
"""Diff-scoped mutmut survivor gate (movie-planner#303).

`mutmut run` itself is never blocking on its own exit code - flipping that on
directly would fail every PR over the pre-existing backlog that predates this
gate (tracked module by module in milestone #5). Instead, this script compares
the *current* mutmut status counts for each file a PR actually touches against
a committed baseline (`.mutmut-baseline.json`), and fails only when a touched
file's counts went up - a new gap in the diff, not old debt nobody asked to
fix.

Two statuses are tracked per file, separately:

- "survived": a mutant a test set ran against and none caught - a real test
  case missing for behavior something already tries to exercise.
- "no tests": mutmut found no test at all to run against the mutant - new
  code nothing touches yet, a stricter gap than "survived".

Two subcommands:

    uv run python scripts/check_mutmut_survivors.py generate
        Regenerate .mutmut-baseline.json from the current `mutmut` results
        (run `uv run mutmut run` first). Run this after a PR that lowers a
        file's counts, to ratchet the baseline down - the script itself never
        raises it, and the gate always allows a lower count than the baseline
        without asking for a baseline update.

    uv run python scripts/check_mutmut_survivors.py check <file> [<file> ...]
        Check the given source files (repo-relative paths, e.g.
        src/movie_planner/cli.py) against the baseline. Exits non-zero and
        lists the new gaps for any file whose current counts exceed its
        baseline.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / ".mutmut-baseline.json"

STATUSES = ("survived", "no tests")

# movie_planner.venue_locations.x__add - known false-positive class
# (movie-planner#339): mutmut's coverage-based test selection attributes a
# collection-time trampoline hit (this function runs once at import, before
# any test starts) to whichever test happens to finish first in the whole
# run, not a test that actually exercises it. Its "survived" status doesn't
# reflect a real test gap - excluded here rather than counted against
# venue_locations.py, so a PR touching that file for an unrelated reason
# isn't blocked by it. Add further exclusions here only with the same kind
# of investigated, documented justification - not to silence a real gap.
EXCLUDED_MUTANT_PREFIXES = [
    "movie_planner.venue_locations.x__add__mutmut_",
]


def is_excluded(mutant_key: str) -> bool:
    return any(mutant_key.startswith(prefix) for prefix in EXCLUDED_MUTANT_PREFIXES)


def module_to_path(module: str) -> str:
    """movie_planner.mail_import.cli -> src/movie_planner/mail_import/cli.py"""
    return "src/" + module.replace(".", "/") + ".py"


def current_mutants_by_file() -> dict[str, dict[str, list[str]]]:
    """Run `mutmut results`, return {source path: {status: [mutant keys]}}."""
    result = subprocess.run(
        ["uv", "run", "mutmut", "results"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    by_file: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for line in result.stdout.splitlines():
        line = line.strip()
        if ": " not in line:
            continue
        mutant_key, _, status = line.rpartition(": ")
        mutant_key = mutant_key.strip()
        if status not in STATUSES or is_excluded(mutant_key):
            continue
        module = mutant_key.rsplit(".", 1)[0]
        by_file[module_to_path(module)][status].append(mutant_key)
    return {path: dict(statuses) for path, statuses in by_file.items()}


def cmd_generate() -> int:
    by_file = current_mutants_by_file()
    baseline = {
        path: {status: len(keys) for status, keys in sorted(statuses.items())}
        for path, statuses in sorted(by_file.items())
    }
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    totals = {status: sum(f.get(status, 0) for f in baseline.values()) for status in STATUSES}
    totals_str = ", ".join(f"{count} {status}" for status, count in totals.items())
    print(f"Wrote {BASELINE_PATH.relative_to(REPO_ROOT)}: {len(baseline)} files, {totals_str}.")
    return 0


def cmd_check(changed_files: list[str]) -> int:
    if not BASELINE_PATH.exists():
        print(f"error: {BASELINE_PATH.relative_to(REPO_ROOT)} is missing - run `generate` first.")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text())
    by_file = current_mutants_by_file()

    failures = []
    for path in changed_files:
        if not path.startswith("src/") or not path.endswith(".py"):
            continue
        current_statuses = by_file.get(path, {})
        allowed_statuses = baseline.get(path, {})
        for status in STATUSES:
            current = current_statuses.get(status, [])
            allowed = allowed_statuses.get(status, 0)
            if len(current) > allowed:
                failures.append((path, status, allowed, current))

    if not failures:
        print("No new mutmut gaps in the diff's touched files.")
        return 0

    print("New mutmut gaps introduced in this diff:")
    print()
    for path, status, allowed, current in failures:
        print(f"  {path} [{status}]: {len(current)} now, {allowed} allowed by baseline")
        for key in sorted(current):
            print(f"    {key}")
    print()
    print(
        "Add a test that kills each new mutant (`uv run mutmut show <key>` shows the "
        "mutation), or, if it's a genuine false positive shaped like movie-planner#339, "
        "document and add it to EXCLUDED_MUTANT_PREFIXES in this script."
    )
    script_path = Path(__file__).resolve().relative_to(REPO_ROOT)
    print(
        f"If a change genuinely lowers a file's counts instead, re-run "
        f"`uv run python {script_path} generate` and commit the updated baseline."
    )
    return 1


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("generate", "check"):
        print(__doc__)
        return 2

    if sys.argv[1] == "generate":
        return cmd_generate()

    changed_files = sys.argv[2:]
    if not changed_files:
        print("No source files given to check - nothing to do.")
        return 0
    return cmd_check(changed_files)


if __name__ == "__main__":
    raise SystemExit(main())
