#!/usr/bin/env bash
# Grammar, spelling and the phonetic article, over the prose this repository
# owns. The tier with a right answer, so it fails rather than advises.
#
# Runs the same ltex-ls-plus in the pre-push hook as in CI. It ships its own
# JDK and is a ~300 MB download the first time, which is why this caches it
# outside the repository; after that a run over a handful of documents takes
# about ten seconds.
set -uo pipefail

cd "$(dirname "$0")/.."

# Pinned, and the same version the workflow installs. When these two disagree
# the hook passes and the pipeline fails, which is the failure this whole
# arrangement exists to avoid.
VERSION=18.7.0

# Outside the repository, so a second clone does not download it again and no
# .gitignore has to know about it.
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/ltex-ls-plus/$VERSION"
HOME_DIR="$CACHE/ltex-ls-plus-$VERSION"

if [ ! -x "$HOME_DIR/bin/ltex-cli-plus" ]; then
  echo "Fetching ltex-ls-plus $VERSION (~300 MB, once per machine)"
  mkdir -p "$CACHE"
  url="https://github.com/ltex-plus/ltex-ls-plus/releases/download/${VERSION}/ltex-ls-plus-${VERSION}-linux-x64.tar.gz"
  # No --strip-components: the archive has a leading "./" entry, so stripping
  # one component removes that rather than the version directory, and the
  # binary ends up somewhere nobody looks.
  curl -fsSL "$url" | tar -xz -C "$CACHE"
fi

# The archive ships its own JDK and the launcher prefers JAVA_HOME, which on a
# machine with an older Java set dies on a class-file-version mismatch — a
# Java error reported as a prose failure. Found by glob so a JDK bump upstream
# does not silently break it.
jdk=$(find "$HOME_DIR" -maxdepth 1 -type d -name 'jdk-*' | head -1)
if [ -z "$jdk" ]; then
  echo "no bundled JDK found in the ltex archive" >&2
  exit 1
fi
export JAVA_HOME="$jdk"

# CHANGELOG.md is written by the release job; correcting it is not this
# script's business.
files=$(git ls-files '*.md' | grep -v '^CHANGELOG.md$')

echo "Checking:"
echo "$files"

# shellcheck disable=SC2086
"$HOME_DIR/bin/ltex-cli-plus" --client-configuration=.ltex.json $files
status=$?

# ltex-cli-plus exits 3 when it finds something, not 1. Testing for a specific
# code would pass a failing document, so this tests for non-zero.
if [ $status -ne 0 ]; then
  echo "ltex found grammar or spelling problems (exit $status)" >&2
  exit 1
fi
