## Why

Movie viewings are currently logged by hand in an org-mode file — title,
date/time, venue, and an IMDb link typed in per entry. There's no calendar
view of what was watched and when, no rating data, and nothing stops the
same viewing from being logged twice. A CLI tool that captures the same
information through a guided prompt, enriches it, and pushes it to a
calendar removes the manual upkeep and gives a real answer to "what did I
watch, when, and where."

## What Changes

- New Python CLI (`movie-planner`) that interactively prompts for a
  watched movie: title, date, optional start/end time, medium
  (cinema/netflix/youtube/etc., user-editable), and venue (specific
  cinema, user-editable, only asked when medium is a physical place).
- Local SQLite store as the source of truth for logged viewings; the CLI
  is the only writer to the calendar.
- Push-only sync of each logged viewing to a Baikal (CalDAV) calendar as
  a VEVENT, tracking the CalDAV UID per entry so it can be updated or
  deleted later through the CLI.
- Update and delete commands that modify the local entry and propagate
  the change to the linked calendar event.
- Metadata enrichment: fetch IMDb, Rotten Tomatoes, and Metacritic
  ratings from OMDb given a title or IMDb ID; store a manually-entered
  Letterboxd link/rating alongside it (no public Letterboxd API exists).
- Fuzzy duplicate detection: normalized, fuzzy-matched title plus
  same-day proximity flags a likely-duplicate viewing. Interactive
  logging asks for confirmation before adding; bulk import skips flagged
  rows by default and reports them, with a `--force` flag to bypass.
- Bulk import from CSV or JSON, routed through the same
  duplicate-detection check.

## Capabilities

### New Capabilities
- `movie-log`: interactive logging of a watched movie (title, date,
  optional start/end time, medium, venue) against the local store, plus
  listing entries and updating/deleting an existing one.
- `calendar-sync`: push-only sync of movie-log entries to a Baikal
  CalDAV calendar, including VEVENT mapping for unknown/partial times
  and propagating updates and deletes via the tracked CalDAV UID.
- `metadata`: fetching IMDb/Rotten Tomatoes/Metacritic ratings via OMDb
  and storing a manually-entered Letterboxd link/rating, attached to a
  movie-log entry.
- `duplicate-detection`: fuzzy title and date-proximity matching against
  existing entries, with confirm-to-add behavior in interactive logging
  and skip-and-report behavior during bulk import.
- `import`: bulk-loading viewing events from CSV or JSON files into the
  local store, through duplicate detection.

### Modified Capabilities
None — this is a new project with no existing specs.

## Impact

- New Python codebase and packaging (no existing code in this repo).
- New local SQLite database file as the persistent store.
- New external dependency on a Baikal instance the user already runs
  (CalDAV credentials and calendar location supplied via config).
- New external dependency on the OMDb API (API key supplied via config).
- New config for user-editable medium/venue lists.
- Repo hosted on `github.com/alrayyes`, GPL-3.0 licensed.
