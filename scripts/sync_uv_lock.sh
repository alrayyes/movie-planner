#!/usr/bin/env bash
# Sync uv.lock's recorded movie-planner version after a release (#77).
#
# release-please bumps pyproject.toml and nothing bumps uv.lock's own entry for
# the package, so every `uv run` after a release would rewrite the lockfile.
# This regenerates it and pushes one commit to the branch.
#
# main moves while a release runs (Dependabot PRs merge right after one), so a
# push can be rejected. v1.28.2 lost its Docker image and packages that way:
# the push failed this step, the job failed, and every publish job that needs it
# was skipped. So each attempt starts from the latest branch tip instead of
# rebasing (a lockfile can't be merged), and when every attempt fails the step
# warns and exits 0. A stale lockfile must never cost a release.
#
# usage: sync_uv_lock.sh [branch]   (default: main)
set -euo pipefail

branch="${1:-main}"

for attempt in 1 2 3; do
  git fetch --quiet origin "$branch"
  git reset --quiet --hard "origin/$branch"
  uv lock
  if git diff --quiet -- uv.lock; then
    echo "uv.lock already records the current version."
    exit 0
  fi
  git config user.name 'movie-planner release job'
  git config user.email 'alrayyes@users.noreply.github.com'
  git add uv.lock
  git commit --quiet -m "chore(deps): sync uv.lock's recorded version [skip ci]"
  if git push --quiet origin "HEAD:$branch"; then
    exit 0
  fi
  echo "Push rejected (attempt $attempt of 3), retrying from the latest $branch."
done

echo "::warning::uv.lock's recorded version was not synced: every push was rejected. Run \`uv lock\` and commit it."
exit 0
