## Context

Greenfield Python CLI — see proposal.md for motivation. The only
existing data is an org-mode file (one heading per viewing, an org
timestamp for date/time, CINEMA/IMDB properties) that the import
capability needs to read. The user already runs Baikal; this change
assumes the target calendar already exists and takes its CalDAV URL and
credentials from config rather than provisioning it. OMDb requires a
free API key and is rate-limited on the free tier (1,000 requests/day).

## Goals / Non-Goals

**Goals:**
- Local SQLite as the sole source of truth; the calendar is a
  push-only mirror the CLI is the only writer to.
- A fast interactive logging flow with sensible defaults for unknown
  or partial times.
- Update/delete that keeps the local store and the linked calendar
  event in sync via a tracked CalDAV UID.
- Fuzzy duplicate protection tuned to catch accidental re-logs without
  blocking legitimate same-day rewatches.

**Non-Goals:**
- Two-way calendar sync, or reconciling edits made directly on the
  calendar — out of scope, see proposal.
- Auto-provisioning the Baikal calendar itself.
- Any interface beyond the CLI.
- Automated Letterboxd ratings — no public API exists; stays manual.

## Decisions

**Storage: SQLite, single file under the user's data directory.**
Rejected Postgres (overkill for a single-user local tool) and a flat
JSON/CSV file (no query support for the dedup and listing requirements
without reimplementing one).

**CalDAV: the `caldav` + `icalendar` libraries.** Rejected hand-rolled
WebDAV requests — the PROPFIND/REPORT/UID-tracking plumbing these
libraries handle is exactly the highest-risk part of this build (see
proposal's stack rationale).

**CLI framework: `typer`, prompts via `questionary`.** Gives
type-hinted commands for the non-interactive flags (import, list
filters) and a clean cascading-prompt flow for interactive logging.

**Config: a TOML file** (e.g. `~/.config/movie-planner/config.toml`)
holding the CalDAV URL/credentials, OMDb API key, and SQLite DB path.
Rejected YAML (extra dependency for no real benefit here) and env-vars-
only (worse fit for a persistent, personal-use config).

**Medium/venue lists live as reference tables in the same SQLite DB**,
not a separate file — keeps a single source of truth and makes "reject
removing a medium still in use" a straightforward foreign-key query.

**Duplicate matching: `rapidfuzz` token-sort ratio against normalized
titles, gated to the same calendar day.** A same-day gate (rather than
a multi-day window) was chosen over a looser window to favor false
negatives over false positives — a missed duplicate is a quick manual
fix, a false block on a legitimate different-day rewatch is just
friction, and the realistic accidental-duplicate scenario (re-running
the CLI or an import) is same-day by construction.

**Interactive duplicate handling: confirm-to-add, not a hard block.**
Matches the tool's already-interactive character. A hard block would
require a separate `--force` re-run even for a legitimate same-day
double feature; a y/N prompt handles that in one step.

## Risks / Trade-offs

- [OMDb free-tier rate limit] → Fine at personal logging volume;
  successful lookups are cached locally so re-editing an entry doesn't
  re-hit the API for a title already matched.
- [Fuzzy threshold miscalibrated] → Threshold is configurable; default
  starts conservative (high similarity score + same-day gate) per the
  false-negative-over-false-positive preference above.
- [Calendar push fails partway, e.g. crash after event creation but
  before the UID is persisted locally] → The local entry is always
  written before the calendar push is attempted, so a failed or
  partial push never loses the local record; unsynced entries can be
  retried without re-prompting the user for the same data.
- [Org-mode import format is specific to this one file, including
  inconsistencies like duplicate PROPERTIES drawers already present in
  it] → Import validates and reports per-row rather than aborting the
  whole file, per the import capability's summary requirement.

## Migration Plan

N/A — greenfield project, nothing to migrate from in-system. First-run
prerequisites: the Baikal calendar already created, CalDAV credentials,
an OMDb API key, and (optionally) a CSV or JSON export of existing
viewing history for a one-time import.
