# movie-planner

[![CI](https://github.com/alrayyes/movie-planner/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/alrayyes/movie-planner/actions/workflows/ci.yml)
[![Codecov](https://codecov.io/gh/alrayyes/movie-planner/graph/badge.svg)](https://codecov.io/gh/alrayyes/movie-planner)
[![release](https://img.shields.io/github/v/release/alrayyes/movie-planner?sort=semver)](https://github.com/alrayyes/movie-planner/releases/latest)
[![licence](https://img.shields.io/badge/licence-GPL--3.0-blue)](LICENSE)

A command-line tool that logs the movies you've watched — title, date,
start/end time, where you watched it — and syncs each viewing to a Baikal
(CalDAV) calendar. It replaces a hand-maintained org-mode log with a guided
prompt, enriches entries with IMDb/Rotten Tomatoes/Metacritic ratings via
OMDb and a manually entered Letterboxd link, and catches accidental
duplicate log entries with fuzzy title matching.

## Requirements

- **Python 3.14 or newer.**
- **[uv](https://docs.astral.sh/uv/)**, for the virtual environment, the
  dependencies and running everything below. Not installed by default —
  one-time setup:

  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  Confirm it worked with `uv --version`.

- **[bun](https://bun.sh)**, for the tooling that isn't Python —
  commitlint, Prettier, markdownlint, and the
  [lefthook](https://lefthook.dev) that runs the git hooks. There's a
  `package.json`, but nothing here is JavaScript; it exists only so those
  tools resolve and stay pinned.
- **[Vale](https://vale.sh)**, pinned in
  [CONTRIBUTING.md](CONTRIBUTING.md#getting-set-up).
- **A Baikal (CalDAV) calendar already set up** — this tool doesn't
  provision one, only syncs to it.
- **An [OMDb API key](https://www.omdbapi.com/apikey.aspx)**, for the
  IMDb/Rotten Tomatoes/Metacritic ratings fetched on each logged entry.

## Installation

See [`docs/INSTALL.md`](docs/INSTALL.md) for every install method — the
AUR, `.deb`/`.rpm` release assets, Docker, and installing from a
checkout. For development, or to run from a checkout:

```sh
git clone https://github.com/alrayyes/movie-planner.git
cd movie-planner
uv sync
```

## Usage

```sh
uv run movie-planner --help
```

(Drop `uv run` and call `movie-planner` directly if you installed it with
`pipx`/`pip` instead of running from a checkout.)

Log a viewing interactively (each field prompts if you leave it off, when
running in a terminal):

```sh
uv run movie-planner log --title "Dune" --date 2026-01-01 --medium cinema \
  --venue "Grand Vista Cinema"
```

A likely duplicate (same normalized title, same day) asks for confirmation
before adding — pass `--force` to skip that, or to add it non-interactively.

Other commands:

```sh
uv run movie-planner list --from 2026-01-01 --to 2026-01-31 --medium cinema
uv run movie-planner update 3 --title "Dune Part Two"
uv run movie-planner delete 3
uv run movie-planner locations media add cinema --physical
uv run movie-planner locations venues add "Grand Vista Cinema"
uv run movie-planner import movies.csv --force
uv run movie-planner sync retry
```

`import` accepts a `.csv` or `.json` file with the same fields as
`examples/`; `sync retry` re-pushes any entry that failed to sync when it
was logged or imported.

## Configuration

A TOML file at `$XDG_CONFIG_HOME/movie-planner/config.toml`
(`~/.config/movie-planner/config.toml` if `XDG_CONFIG_HOME` isn't set):

```toml
[caldav]
url = "https://baikal.example.com/dav.php/calendars/moviewatcher/movies/"
username = "moviewatcher"
password = "..."

[omdb]
api_key = "..."

[storage]
db_path = "~/.local/share/movie-planner/movies.db"
```

Run `movie-planner init` to write a starter copy of this file, ready to
edit — any other command run against a missing config file offers to do
the same, interactively. All three sections are required; a missing file
or a missing key fails with a message naming the problem, not a stack
trace.

## Import examples

[`examples/`](examples/) has three fictional viewings in CSV and JSON
form. It shows the field names and structure that each import format
expects.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the toolchain, the hooks, and
how a change gets reviewed and released.

## Licence

[GPL-3.0](LICENSE).
