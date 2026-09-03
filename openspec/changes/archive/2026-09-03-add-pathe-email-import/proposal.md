## Why

Every viewing logged from a Pathé cinema starts as a booking
confirmation email already in hand — title, date, start/expected-end
time, cinema, and a booking number. Typing that back into `log` by hand is
pure transcription. Separately, no calendar event pushed by this tool has
ever carried a description: `build_vevent` only sets a summary and location,
so the ratings and links an entry does have never reach the calendar, and
entries imported via `import` never fetch them in the first place.

## What Changes

- New `from-pathe-email` command: reads a Pathé booking confirmation email
  (piped via stdin or given as a file path), parses title, date, start/end
  time, cinema, and booking number, shows the parsed fields, and asks for
  confirmation — read from the controlling terminal, since stdin may be
  occupied by the piped email — before writing.
- Matching: looks up an existing entry by booking number first (an update,
  e.g. a re-sent confirmation after a time or room change); falls back to
  the existing fuzzy title/date duplicate check when no booking number
  matches, the same way interactive `log` does.
- New `booking_ref` column on `entries`, populated by this command, not
  treated as unique (Pathé's own uniqueness guarantee is unconfirmed) —
  a match is a lookup hint the user still confirms, not an automatic write.
- Reuses the existing OMDb metadata fetch (currently only wired into `log`)
  for entries created or updated this way.
- `build_vevent` gains a `description`: ratings, Letterboxd link/rating when
  present, and, for a Pathé-sourced entry, the auditorium/screening format
  and seat as free text — parsed and rendered into the description only,
  never persisted as its own column.
- New `refresh` command: for every entry, fetches OMDb ratings when missing
  (never re-fetching an entry that already has them) and then pushes an
  updated calendar event (or creates one, if never synced) reflecting
  current data. Kept separate from `sync retry` — `retry` stays the cheap,
  no-OMDb-calls, unsynced-entries-only recovery path; `refresh` is the
  heavier, deliberate, all-entries sweep. Both share the same
  create-or-update push step.
- `import` (CSV/JSON) gains the same OMDb fetch step `log` already has,
  closing the gap that left imported entries without ratings.

## Capabilities

### New Capabilities

- `pathe-email-import`: parsing a Pathé booking confirmation email into a
  movie-log entry, matching it against existing entries by booking number
  or fuzzy title/date, confirming with the user, and creating or updating
  accordingly.

### Modified Capabilities

- `calendar-sync`: pushed VEVENTs gain a description built from ratings and
  Letterboxd data; adds the `refresh` operation that backfills metadata and
  re-pushes every entry.
- `metadata`: the OMDb fetch now also runs during bulk `import` and during
  `refresh`, not only interactive `log`; `refresh` skips entries that
  already have ratings rather than re-fetching them.

## Impact

- `src/movie_planner/store.py`: new `booking_ref` column (migrated,
  indexed, not unique), a lookup by booking ref.
- `src/movie_planner/calendar_sync.py`: `build_vevent` gains `description`;
  a shared create-or-update push step used by `log`, `import`,
  `from-pathe-email`, `sync retry`, and `refresh`.
- `src/movie_planner/importers.py` or a new `pathe.py`: email parsing.
- `src/movie_planner/cli.py`: `from-pathe-email` and `refresh` commands;
  `import` gains the metadata step.
- Tests and `README.md` usage/configuration sections.
