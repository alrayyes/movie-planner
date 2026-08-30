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

**Status: chassis only.** The commands described below (`log`, `list`,
`update`, `delete`, `locations`, `import`) don't exist yet. The full plan
— proposal, design decisions, and the task breakdown — lives in
[`openspec/changes/add-movie-log-cli/`](openspec/changes/add-movie-log-cli/).

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
- **A Baikal (CalDAV) calendar already set up**, once calendar sync
  lands — this tool doesn't provision one.
- **An [OMDb API key](https://www.omdbapi.com/apikey.aspx)**, once
  metadata fetching lands.

## Installation

```sh
git clone https://github.com/alrayyes/movie-planner.git
cd movie-planner
uv sync
```

## Usage

```sh
uv run movie-planner --help
```

Real commands land as the tasks in
[`openspec/changes/add-movie-log-cli/tasks.md`](openspec/changes/add-movie-log-cli/tasks.md)
get implemented.

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

All three sections are required. A missing file or a missing key fails
with a message naming the problem, not a stack trace.

## Import examples

[`examples/`](examples/) has three fictional viewings in CSV and JSON
form. It shows the field names and structure that each import format
expects.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the toolchain, the hooks, and
how a change gets reviewed and released.

## Licence

[GPL-3.0](LICENSE).
