#!/usr/bin/env bash
# Grammar, spelling and the phonetic article, over the prose this repository
# owns. The tier with a right answer, so it fails rather than advises.
#
# Runs the same ltex-cli-plus in the pre-push hook as in CI. In CI the
# mechanics job's own container is ghcr.io/alrayyes/ltex-cli-plus, built
# once and reused rather than fetched fresh every run, so ltex-cli-plus is
# already on PATH there. Locally, prefers docker against the same image
# (about the same ~10s once pulled as the raw tarball, per
# rules/markdown.md); a machine with neither falls back to fetching and
# caching the release tarball under $XDG_CACHE_HOME.
set -uo pipefail

cd "$(dirname "$0")/.."

VERSION=18.7.0
IMAGE="ghcr.io/alrayyes/ltex-cli-plus:$VERSION@sha256:22452e86a130e528d526b60792926002983fcbf732bff09bd4e843d22816e4ea"

if command -v ltex-cli-plus >/dev/null 2>&1; then
  run_ltex() { ltex-cli-plus "$@"; }
elif command -v docker >/dev/null 2>&1; then
  run_ltex() {
    docker run --rm -v "$PWD:/work" -w /work --entrypoint /usr/local/bin/ltex-cli-plus "$IMAGE" "$@"
  }
else
  # Outside the repository, so a second clone does not download it again and
  # no .gitignore has to know about it.
  CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/ltex-ls-plus/$VERSION"
  HOME_DIR="$CACHE/ltex-ls-plus-$VERSION"

  if [ ! -x "$HOME_DIR/bin/ltex-cli-plus" ]; then
    echo "Fetching ltex-ls-plus $VERSION (~300 MB, once per machine)"
    mkdir -p "$CACHE"
    url="https://github.com/ltex-plus/ltex-ls-plus/releases/download/${VERSION}/ltex-ls-plus-${VERSION}-linux-x64.tar.gz"
    # No --strip-components: the archive has a leading "./" entry, so
    # stripping one component removes that rather than the version
    # directory, and the binary ends up somewhere nobody looks.
    curl -fsSL "$url" | tar -xz -C "$CACHE"
  fi

  # The archive ships its own JDK and the launcher prefers JAVA_HOME, which
  # on a machine with an older Java set dies on a class-file-version
  # mismatch — a Java error reported as a prose failure. Found by glob so a
  # JDK bump upstream does not silently break it.
  jdk=$(find "$HOME_DIR" -maxdepth 1 -type d -name 'jdk-*' | head -1)
  if [ -z "$jdk" ]; then
    echo "no bundled JDK found in the ltex archive" >&2
    exit 1
  fi
  export JAVA_HOME="$jdk"
  run_ltex() { "$HOME_DIR/bin/ltex-cli-plus" "$@"; }
fi

# CHANGELOG.md is written by the release job, and OpenSpec's generated
# artifacts and Claude Code's own scaffolding follow their own
# conventions; correcting any of them is not this script's business.
files=$(git ls-files '*.md' | grep -v '^CHANGELOG.md$' | grep -v '^openspec/' | grep -v '^\.claude/')

echo "Checking:"
echo "$files"

# shellcheck disable=SC2086
run_ltex --client-configuration=.ltex.json $files
status=$?

# ltex-cli-plus exits 3 when it finds something, not 1. Testing for a specific
# code would pass a failing document, so this tests for non-zero.
if [ $status -ne 0 ]; then
  echo "ltex found grammar or spelling problems (exit $status)" >&2
  exit 1
fi
