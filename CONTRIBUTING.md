# Contributing

## Getting set up

- **Python 3.14 or newer.**
- **[uv](https://docs.astral.sh/uv/)**. Not installed by default — one-time
  setup:

  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  Confirm it worked with `uv --version`. `uv sync` then creates `.venv`
  and installs everything pinned in `uv.lock`.

- **[bun](https://bun.sh)** for the tooling that isn't Python —
  commitlint, Prettier, markdownlint, and the
  [lefthook](https://lefthook.dev) that runs the git hooks. There's a
  `package.json`, but nothing here is JavaScript; it exists only so those
  tools resolve and stay pinned.
- **[Vale](https://vale.sh) v3.17.1** on your `PATH`, for the style tier
  of the prose lint — a released binary from
  [its releases page](https://github.com/errata-ai/vale/releases/tag/v3.17.1),
  or your package manager's pinned build. The version has to match what
  CI runs, or the hook passes and the pipeline fails for a reason that
  isn't obvious from the failure.

  `ltex-cli-plus` needs nothing installed: the hook fetches and caches it
  on first use.

- **[Docker](https://docs.docker.com/engine/install/)**, running locally,
  for the hooks that lint and build `Dockerfile` (hadolint, then a plain
  `docker build`).

Two commands install the linters and the git hooks:

```sh
uv sync
bun install
```

An uninstalled hook silently does nothing, which is worse than not having
one, so `bun install`'s `prepare` script runs `lefthook install` for you.
You find out at the pipeline otherwise, not at the commit.

## Everyday commands

Every one of these is what a hook or CI runs — see `lefthook.yml` and
`.github/workflows/*.yml` for exactly which.

```sh
uv run pytest
uv run pytest --cov=movie_planner --cov-report=term-missing
uv run ruff check          # the linter
uv run ruff check --fix    # its fixer
uv run ruff format         # the formatter; add --check for the check-only form
uv run mypy                # strict type checking, src/ and tests/
uv run bandit -r src/movie_planner   # static security scan
uv run mutmut run          # mutation testing, then `uv run mutmut results`

bun run format:check       # prettier --check, add --write to fix
bun run lint:md
bun run lint:prose         # vale
bun run lint:mechanics     # ltex-cli-plus
```

`mypy` runs in `strict` mode across both `src/` and `tests/`.
`mutmut run` itself is still non-blocking on its own exit code — it skips
`test_e2e.py` (rerunning a real Baikal container per mutant would make a
25-second check take hours) and always exits 0 regardless of survivor
count. The dotfiles-wide rule says a surviving mutant should always block
a merge, but this repo has 817 pre-existing survivors (checked
2026-09-09, after excluding the known-false-positive class below) and
flipping that switch directly would fail every PR over debt nobody
touched — that backlog is tracked module by module in milestone #5.

**The actual gate is `scripts/check_mutmut_survivors.py`** (#303), run
right after `mutmut run` in both `pre-push` and CI. It compares each file
your branch touches against `.mutmut-baseline.json` — a survivor count
per file — and fails only when a touched file has _more_ survivors now
than the baseline allows. A file you never touched can carry any amount
of pre-existing debt without blocking your PR; a file you did touch can't
gain a new one.

```sh
uv run mutmut run
uv run python scripts/check_mutmut_survivors.py check src/movie_planner/cli.py
```

If your change genuinely lowers a file's survivor count (you added a test
that kills a mutant nobody had covered before), ratchet the baseline down
in the same PR:

```sh
uv run python scripts/check_mutmut_survivors.py generate
```

The baseline only ever needs lowering, never raising — the script itself
refuses to pass a file whose count went up, so there's no legitimate
reason to hand-edit `.mutmut-baseline.json` upward. If you hit one, that's
a sign the new code needs a test, not a bigger number.

**Known false positive**: `movie_planner.venue_locations.x__add`'s
mutants are permanently excluded from every file's count
(`EXCLUDED_MUTANT_PREFIXES` in the script) — movie-planner#339 found that
`mutmut`'s coverage-based test selection attributes any mutant on
code that runs once at import (before any test starts) to whichever
test happens to finish first in the whole suite, not one that actually
exercises it. Its "survived" status doesn't reflect a real gap. Add a
future exclusion there only with the same kind of investigated,
documented justification — never to silence a real one.

## How it fits together

`src/movie_planner/` holds everything importable — `cli.py` is the
[Typer](https://typer.tiangolo.com) app. No `src/movie_planner/commands/`
tree: that shape earns its keep the day a second command needs its own
file. Tests live in `tests/`, driven through `typer.testing.CliRunner` —
Typer's wrapper over Click's own test runner, invoking the command
in-process rather than shelling out.

## Adding a new import format

`movie-planner import` reads whatever `IMPORT_FORMATS` (in
[`src/movie_planner/importers.py`](src/movie_planner/importers.py))
has registered, keyed by file suffix - `cli.py` never branches on a
specific format, only on whether the suffix is in that dict. The same
shape `pathe-mail-import`'s own ["Adding a second cinema
chain"](docs/pathe-mail-import.md#adding-a-second-cinema-chain) uses:
a registry a new adapter plugs into, not a branch to edit.

Adding a format (a Letterboxd export, XLSX, any other bulk source)
means:

1. Write a `parse(path: Path) -> list[ParsedRow]` function. `parse_csv`
   and `parse_json` are the reference implementations - both end up
   calling the shared `_row_from_dict` helper, worth reusing if your
   format is also naturally row-shaped. A `ParsedRow` is either a
   populated `ImportRow` (see its fields for what a row can carry) or a
   populated `error` string - never both; `run_import` reports every failed
   row back to the caller rather than aborting the whole file on one
   bad line.
2. Register it: `IMPORT_FORMATS[".xlsx"] = ImportFormat(name="xlsx",
parse=parse_xlsx)`. The `name` is what shows up as the entry's
   provenance later (issue #257) - keep it short and lowercase, same
   style as `"csv"`/`"json"`.
3. Nothing else changes. `movie-planner import <file>` picks up the
   new suffix automatically; the "unsupported file type" error already
   lists every registered format, not a hardcoded string.

Test the parser the same way `tests/test_import.py` already tests
`parse_csv`/`parse_json`: valid rows, a row missing a required field,
a row with a bad value (a date that doesn't parse, for example) - each
producing the right `ParsedRow`, not an unhandled exception.

## OMDb usage in issues

OMDb enforces a request cap (1000/day on the free tier this project
uses), and this codebase already avoids unnecessary calls in more than
one place - `run_import` skips the OMDb lookup entirely for a row
that's a detected duplicate, and `OmdbClient` caches a match per
`(title, year)` for the life of one run so the same title looked up
twice in a batch only makes one HTTP call. Any issue or PR touching
`import`, `sync`, or anything else that fetches ratings should state
that minimization explicitly as a testable acceptance criterion or
definition-of-done item - "duplicate/already-logged entries never
trigger a lookup," "a title looked up once in a run is never
re-fetched" - not leave it as an implicit expectation nobody wrote
down. Concrete and testable, the same bar `skills/write-issue/`
already holds every acceptance criterion to.

## TMDb usage (trailer lookup)

TMDb's free tier has no comparable daily cap to OMDb's, so this isn't the
same minimization pressure - but `TmdbClient` still caches by `imdb_id`
for the life of one run, same reasoning as `OmdbClient`. Trailer lookup
only ever runs immediately after a successful OMDb match, reusing the
`imdb_id` that match already returned rather than doing its own title
search - see `_fetch_trailer_or_warn` in `cli.py`. It's opportunistic
throughout: no `tmdb.api_key` configured, no match, or no official
YouTube trailer are all the same "no trailer" outcome, never an error
that blocks the rest of the command.

## Verifying a change against the real setup

Before running a full `sync refresh` (or any other command that touches
every entry) against the real database to confirm a change works, scope
it to the 5 most recently logged entries first - `movie-planner list
--limit 5` to find them, then `--from`/`--to`/`--date` to scope the
verification run to just those. Cheap, fast, and it catches a broken
change before it burns OMDb quota or pushes hundreds of malformed
calendar updates. Only run the full, unscoped command once the small
sample confirms the change does what it's supposed to.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/):
`type(scope): description`, types `feat`/`fix`/`docs`/`style`/`refactor`/
`perf`/`test`/`build`/`ci`/`chore`/`revert`. Subject under 50 characters,
lowercase, no trailing full stop. commitlint enforces the shape at
commit-msg and again in CI; the length and case rules are tighter than
what it checks, so hold to them anyway.

## Branching, review, and release

Every change goes through a pull request — nothing is pushed straight to
`main`. Branch protection on `main` enforces that.

The pull request **title** has to be a valid Conventional Commit too —
`pr-title.yml` checks it. commitlint only ever reads commit objects, and a
squash merge defaults its commit message to the pull request title, so this
is the only check standing between a badly titled pull request and a bad
message on `main`.

Once a pull request's checks are green, squash-merge it and delete the
branch. [release-please](https://github.com/googleapis/release-please)
reads the Conventional Commits on `main` and keeps a release pull request
open with the next version and changelog entry, read from `pyproject.toml`;
merging that one tags the release. Nobody picks a version by hand.
