#!/usr/bin/env bash
# Freezes the CLI into one self-contained executable with PyInstaller,
# for nfpm to wrap into .deb/.rpm — see nfpm.yaml's header comment for
# why this exists instead of depending on distro python3-* packages.
# Shared by the CI dry run and the release job so the two can't build
# it differently.
#
# Built via the Dockerfile's own `pyinstaller` stage rather than on
# the runner directly — a binary linked against the runner's newer
# glibc fails to load at all on Debian bookworm (confirmed:
# "GLIBC_2.38 not found"). Building against the same pinned
# python:3.14-slim-bookworm image the runtime image already uses
# keeps the binary compatible with both Debian and the newer glibc
# Fedora/Ubuntu already ship.
set -euo pipefail

cd "$(dirname "$0")/.."

rm -rf dist-pyinstaller
mkdir -p dist-pyinstaller

docker build --target pyinstaller -t movie-planner:pyinstaller-build .

container=$(docker create movie-planner:pyinstaller-build)
docker cp "$container:/dist/movie-planner" dist-pyinstaller/movie-planner
docker rm "$container" >/dev/null
