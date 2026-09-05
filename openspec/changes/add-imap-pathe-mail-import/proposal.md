## Why

`from-pathe-email` couples the main CLI to one cinema chain's email
format and can only ever process one email at a time, piped or given as
a file. A standalone tool that reads an IMAP mailbox (Proton Bridge or
Gmail), finds Pathé booking confirmations, and emits them as an
`import.json` file lets `movie-planner` stay solely concerned with CRUD
and CalDAV sync plus one generic, vendor-agnostic import format - it
never has to know what a Pathé email looks like, or what `booking_ref`
means.

## What Changes

- **New**: a standalone mail-fetch tool. Reads mail from a configured
  source - IMAP (same client for Proton Bridge or Gmail - config-driven
  host/port/credentials, not two separate integrations) or a local mbox
  file (mutt, or Thunderbird's default local-folder format, which is
  also mbox) - searches for `pathe.nl` senders, parses each with the
  existing `parse_pathe_email` (unchanged), and writes every
  successfully parsed booking as a row in a `movies.schema.json`-shaped
  JSON file. An email that doesn't parse as a booking confirmation is
  never written to the JSON - it's printed as a review table (From,
  Subject, Date) instead.
- The tool has no knowledge of the store, CalDAV, or `booking_ref` - it
  never reads what's already logged. Running it again re-emits every
  booking confirmation still visible in the mailbox; `movie-planner
  import`'s existing duplicate handling is what keeps a re-run from
  double-logging.
- **BREAKING**: `booking_ref` is removed from the generic import
  contract - `ImportRow` drops the field, `run_import` stops accepting
  or persisting it via that path, and `examples/movies.schema.json`
  drops the property. `from-pathe-email` (the existing single-email CLI
  command) is unaffected - it stores and looks up `booking_ref` directly
  against the store, entirely outside the generic import pipeline, and
  keeps doing so unchanged.
- Duplicate detection gains a second, independent trigger: two entries
  whose screening times overlap (a 30-minute fuzz buffer either side of
  `start_time`/`end_time`) are flagged regardless of title similarity -
  a physically-impossible-to-attend-both check, not a title heuristic.
  This is a general `import`/`log` improvement, not specific to the mail
  tool, and it does not attempt to detect or reconcile a rescheduled
  booking (a changed time on a re-sent confirmation still isn't matched
  back to the original entry - accepted gap, fixed by hand with
  `movie-planner update`).

## Capabilities

### New Capabilities

- `pathe-mail-fetch`: connects to an IMAP mailbox, finds and parses
  Pathé booking confirmations, emits an import-ready JSON file, and
  reports anything it couldn't confidently parse for manual review.

### Modified Capabilities

- `import`: `booking_ref` is no longer an accepted field on an imported
  row (**BREAKING**).
- `duplicate-detection`: adds a time-overlap check, independent of
  title matching, alongside the existing fuzzy-title/same-day rule.

## Impact

- New module(s) for the IMAP client and the mail-to-import-row mapping,
  outside `movie_planner.cli`'s existing surface - exact placement
  decided in `design.md`.
- `src/movie_planner/importers.py`: `ImportRow` loses `booking_ref`;
  `run_import` stops writing it from a generic row.
- `examples/movies.schema.json`, `examples/README.md`, `README.md`:
  drop `booking_ref` from the documented row shape.
- `src/movie_planner/duplicates.py`: new overlap-detection logic
  alongside the existing fuzzy title/day check.
- New config surface for the mail tool (IMAP host/port/credentials,
  mailbox/search scope) - separate from `movie-planner`'s own
  `config.toml` sections, per the "doesn't concern itself with the main
  command" boundary.
- `src/movie_planner/cli.py`'s `from_pathe_email` command: unchanged.
- `src/movie_planner/pathe.py`: unchanged, reused as-is by the new tool.
