"""scripts/sync_uv_lock.sh (movie-planner#77): the release job's lockfile sync.

Run against a throwaway git remote with a stub `uv`, because the failure that
matters is a race: main moves between the checkout and the push, which cost
v1.28.2 its Docker image and packages when the push was rejected and the step
took the publish jobs down with it.
"""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_uv_lock.sh"

# `uv lock` rewrites the lock's recorded version to pyproject's. When RACE_FILE
# is set, the first call also lands a commit on the remote, the way a merge
# does while the real `uv lock` is running.
STUB_UV = """#!/usr/bin/env bash
set -euo pipefail
version="$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)"
sed -i "s/^version = .*/version = \\"$version\\"/" uv.lock
if [ -n "${RACE_FILE:-}" ] && [ ! -e "$RACE_FILE.done" ]; then
  touch "$RACE_FILE.done"
  git clone -q "$REMOTE" "$RACE_FILE.clone"
  (cd "$RACE_FILE.clone" && echo moved > other.txt && git add other.txt \\
    && git -c user.name=x -c user.email=x@x commit -q -m "chore: main moved" \\
    && git push -q origin HEAD:main)
fi
"""


@pytest.fixture(autouse=True)
def hook_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Git exports an absolute GIT_DIR to a hook run from a worktree, and a
    test that builds its own repositories must not inherit it: the commits and
    the push below would land in the checkout the hook is running from. This
    stands in for that checkout with a decoy that has a remote of its own, and
    fails the test if anything reaches it.
    """
    decoy_remote = tmp_path / "decoy-remote.git"
    decoy = tmp_path / "decoy"
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    for cwd, args in (
        (tmp_path, ["init", "-q", "--bare", "-b", "main", str(decoy_remote)]),
        (tmp_path, ["clone", "-q", str(decoy_remote), str(decoy)]),
        (
            decoy,
            [
                "-c",
                "user.name=x",
                "-c",
                "user.email=x@x",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "decoy",
            ],
        ),
        (decoy, ["push", "-q", "origin", "HEAD:main"]),
    ):
        subprocess.run(["git", *args], cwd=cwd, check=True, env=clean, capture_output=True)
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    yield
    count = subprocess.run(
        ["git", "rev-list", "--all", "--count"],
        cwd=decoy,
        env=clean,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert count == "1", "a test wrote to the repository the hook is running from"


def own_environment() -> dict[str, str]:
    """The environment without the GIT_* variables a hook passes down, so a
    repository made here is the only one git can see.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=own_environment()
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> dict[str, Path]:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(remote), str(work))
    (work / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.0.1"\n')
    (work / "uv.lock").write_text('version = "1.0.0"\n')
    git(work, "add", ".")
    git(work, "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "-m", "init")
    git(work, "push", "-q", "origin", "HEAD:main")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(STUB_UV)
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
    return {"remote": remote, "work": work, "bin": bin_dir, "tmp": tmp_path}


def run_sync(repo: dict[str, Path], **env: str) -> subprocess.CompletedProcess[str]:
    full_env = {
        **own_environment(),
        "PATH": f"{repo['bin']}:{os.environ['PATH']}",
        "REMOTE": str(repo["remote"]),
        **env,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "main"],
        cwd=repo["work"],
        env=full_env,
        capture_output=True,
        text=True,
    )


def remote_lock(repo: dict[str, Path]) -> str:
    return git(repo["remote"], "show", "main:uv.lock")


def test_a_stale_lock_is_committed_and_pushed(repo: dict[str, Path]) -> None:
    result = run_sync(repo)
    assert result.returncode == 0, result.stderr
    assert remote_lock(repo) == 'version = "1.0.1"'
    assert "sync uv.lock" in git(repo["remote"], "log", "-1", "--format=%s", "main")


def test_a_lock_already_in_sync_makes_no_commit(repo: dict[str, Path]) -> None:
    (repo["work"] / "uv.lock").write_text('version = "1.0.1"\n')
    git(repo["work"], "add", ".")
    git(repo["work"], "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "-m", "sync")
    git(repo["work"], "push", "-q", "origin", "HEAD:main")
    before = git(repo["remote"], "rev-parse", "main")
    result = run_sync(repo)
    assert result.returncode == 0, result.stderr
    assert git(repo["remote"], "rev-parse", "main") == before


def test_main_moving_during_the_step_does_not_lose_the_sync(repo: dict[str, Path]) -> None:
    result = run_sync(repo, RACE_FILE=str(repo["tmp"] / "race"))
    assert result.returncode == 0, result.stderr
    assert remote_lock(repo) == 'version = "1.0.1"'
    assert "other.txt" in git(repo["remote"], "ls-tree", "--name-only", "main")


def test_a_push_that_keeps_failing_warns_but_does_not_fail_the_job(
    repo: dict[str, Path],
) -> None:
    hook = repo["remote"] / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    result = run_sync(repo)
    # The publish jobs `need` this one, and a stale lockfile must not cost a release.
    assert result.returncode == 0, result.stderr
    assert "::warning" in result.stdout + result.stderr
    assert remote_lock(repo) == 'version = "1.0.0"'
