# slim (Debian, glibc), not alpine: a transitive dependency (lxml, via
# icalendar's recurring-events extra) ships manylinux wheels built against
# glibc, so alpine's musl would force a from-source compile instead of
# using the prebuilt wheel.
FROM ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945 AS uv
FROM python:3.14-slim-bookworm@sha256:416f0db2a2b561945630cef9877a7ea0581b27449eb9fd9df42f03e1b74b5b63 AS builder

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# Built at its final runtime path (not the default /build/.venv) so the
# console-script shebangs uv bakes in still resolve after the venv is
# copied into the runtime stage below.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --frozen --no-dev --no-editable

# Not part of the shipped image — `docker build .` never reaches this
# stage since it isn't an ancestor of the final one below. Built with
# `docker build --target pyinstaller` by scripts/build-binary.sh, to
# freeze the CLI into one binary for .deb/.rpm packaging on the same
# glibc floor this runtime image already targets (see the header
# comment above).
FROM builder AS pyinstaller
# PyInstaller shells out to objdump to inspect the shared libraries it
# bundles; not part of the slim base image.
RUN apt-get update && apt-get install -y --no-install-recommends binutils=2.40-2 \
  && rm -rf /var/lib/apt/lists/*
RUN uv sync --frozen --no-editable && \
  uv run pyinstaller --onefile --name movie-planner --distpath /dist /opt/venv/bin/movie-planner

FROM python:3.14-slim-bookworm@sha256:416f0db2a2b561945630cef9877a7ea0581b27449eb9fd9df42f03e1b74b5b63

RUN useradd --create-home --uid 1000 movieplanner
COPY --from=builder --chown=movieplanner:movieplanner /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

USER movieplanner
WORKDIR /home/movieplanner
ENTRYPOINT ["movie-planner"]
