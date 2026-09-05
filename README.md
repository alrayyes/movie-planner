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

Log a Pathé cinema booking straight from its confirmation email instead —
pipe the raw email in, or point at a saved copy:

```sh
cat ticket.eml | uv run movie-planner from-pathe-email
uv run movie-planner from-pathe-email ticket.eml
```

Either way it parses the title, date, times, cinema, and booking number,
shows what it found, and asks for confirmation before writing — piping
the email doesn't skip that; the confirmation is read from the
controlling terminal, not from the piped input. A re-sent confirmation
for a booking already logged (same booking number) updates that entry
instead of creating a second one. Pass `--yes` to skip the prompt (for a
mail-pipe automation with no terminal attached) or `--no-metadata` to
skip the OMDb lookup.

Other commands:

```sh
uv run movie-planner list --from 2026-01-01 --to 2026-01-31 --medium cinema
uv run movie-planner list --chain Pathé
uv run movie-planner list --city Amsterdam
uv run movie-planner show 3
uv run movie-planner update 3 --title "Dune Part Two"
uv run movie-planner delete 3
uv run movie-planner locations media add cinema --physical
uv run movie-planner locations venues add "Grand Vista Cinema"
uv run movie-planner import movies.csv --force
uv run movie-planner sync retry
uv run movie-planner sync refresh
uv run movie-planner sync refresh --from 2026-01-01 --to 2026-01-31
uv run movie-planner sync refresh --date 2026-01-15
uv run movie-planner sync refresh --force --date 2026-01-15
```

`show` prints one entry's full metadata — ratings, links, venue, times —
in a structured, labelled layout instead of `list`'s single line. On a
terminal identifiable as iTerm2/WezTerm or Kitty/Ghostty, it also renders
the poster inline — `poster_url` is fetched and stored the same time
ratings are (`log`, `import`, `sync refresh`), or, for an entry logged
before this existed, fetched live at display time instead; anywhere
else, or with no poster available, `show` just skips the image. Kitty
only renders a poster that's already PNG — OMDb's usual JPEG posters
render on iTerm2/WezTerm only. No Sixel support.

A venue created with a name matching a hardcoded table (Pathé's own
Amsterdam cinemas, GSC's Malaysia locations, and a handful of
independent Amsterdam venues) gets its chain, city, and country filled
in automatically — a name that doesn't match gets none of that, never
a guess. `list --chain`/`--city` filter on it; `show` displays it.

`import` accepts a `.csv` or `.json` file with the same fields as
`examples/`, and fetches OMDb ratings the same as `log` does. `sync retry`
re-pushes any entry that failed to sync when it was logged or imported —
cheap, and safe to run any time, since it never calls OMDb and only
touches entries that were never synced. `sync refresh` is the heavier
counterpart: it walks every entry, fetches OMDb ratings for any that are
still missing them, and re-pushes every calendar event so its description
reflects current data — worth running after upgrading, or to backfill
ratings for entries imported before this existed, not something to run
reflexively the way `retry` is. Pass `--from`/`--to` or a single `--date`
to scope it to a range instead of the whole log; `--date` can't be
combined with either. Pass `--force` to re-fetch ratings for entries
that already have them too — useful after a wrong OMDb match, or when a
rating's changed since — instead of the default of only fetching for
entries still missing one.

A large historical import (years of entries at once) can exceed OMDb's
daily request limit before it finishes. Pass `--no-metadata` to `import`
to create every entry with no OMDb calls at all, then backfill ratings
afterward with `sync refresh --from`/`--to`, one date range per day, as
many days as the limit takes to clear:

```sh
uv run movie-planner import movies-2020-2026.csv --no-metadata
uv run movie-planner sync refresh --from 2020-01-01 --to 2021-12-31
# next day:
uv run movie-planner sync refresh --from 2022-01-01 --to 2023-12-31
# ...and so on until every year is covered
```

Sync is push-only — the local SQLite store is the only source of
truth, and nothing here ever reads the calendar back. See
[`docs/calendar-schema.md`](docs/calendar-schema.md) for exactly what
gets written to the calendar, if something else needs to read it.

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

Instead of `caldav.password` in plain text, `caldav.password_command` runs
a command and uses its stdout as the password — a password manager CLI, for
example. Set only one of the two.

Every setting except the CalDAV password can also be set as a flag
(`--caldav-url`, `--caldav-username`, `--omdb-api-key`, `--db-path`) or an
environment variable (`MOVIE_PLANNER_CALDAV_URL` and so on), overriding the
config file for one invocation — flags win over environment variables, which
win over the config file. The password stays config-file-only (via
`password` or `password_command`) rather than risk landing in shell history
or a process list.

## Import examples

[`examples/`](examples/) has three fictional viewings in CSV and JSON
form. It shows the field names and structure that each import format
expects.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the toolchain, the hooks, and
how a change gets reviewed and released.

## Licence

[GPL-3.0](LICENSE).
