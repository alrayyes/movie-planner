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
`mutmut` is non-blocking everywhere it runs (`pre-push`, CI): a surviving
mutant is a missing test case worth picking up, not a merge blocker for a
suite that wasn't built mutation-clean from day one. It skips
`test_e2e.py` — rerunning a real Baikal container per mutant would make a
25-second check take hours.

## How it fits together

`src/movie_planner/` holds everything importable — `cli.py` is the
[Typer](https://typer.tiangolo.com) app. No `src/movie_planner/commands/`
tree: that shape earns its keep the day a second command needs its own
file. Tests live in `tests/`, driven through `typer.testing.CliRunner` —
Typer's wrapper over Click's own test runner, invoking the command
in-process rather than shelling out.

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
