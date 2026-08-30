## 1. Project setup

- [x] 1.1 Initialize the Python project structure (pyproject.toml, package layout, `typer` entrypoint) and verify `movie-planner --help` runs
- [x] 1.2 Add pinned dependencies (typer, questionary, caldav, icalendar, rapidfuzz, an HTTP client for OMDb) to pyproject.toml and verify a clean-venv install succeeds
- [x] 1.3 Add TOML config loading (CalDAV URL/credentials, OMDb API key, SQLite DB path) and verify a missing or invalid config produces a clear error rather than a stack trace
- [x] 1.4 Add LICENSE (GPL-3.0) and a README covering setup and configuration, and verify the documented commands work as written

## 2. Local data store

- [x] 2.1 Define the SQLite schema for entries, medium reference table, and venue reference table, and verify all tables are created on first run
- [x] 2.2 Implement medium/venue CRUD (add/list/remove) enforcing rejection of removal while referenced, and verify with a test that removes a medium in use and asserts it's rejected
- [x] 2.3 Implement entry CRUD (create/list/update/delete) against the schema, and verify with tests covering optional start/end time and venue-only-prompted-for-physical-medium

## 3. Duplicate detection

- [x] 3.1 Implement title normalization (case-fold, strip punctuation, strip known noise suffixes like trailing " - Movies") and verify with a unit test covering the "Ready or Not 2" suffix case
- [x] 3.2 Implement fuzzy match plus same-day gate against existing entries using rapidfuzz with a configurable threshold, and verify with tests for same-title/same-day flagged and same-title/different-day not flagged
- [ ] 3.3 Wire the duplicate check into interactive logging as a confirm-to-add prompt, and verify by running the log command against a seeded duplicate and confirming the prompt appears
- [ ] 3.4 Wire the duplicate check into bulk import as skip-and-report with a `--force` override, and verify with an import test asserting skipped rows appear in the summary and `--force` persists them

## 4. Calendar sync

- [x] 4.1 Implement a CalDAV client wrapper around `caldav`/`icalendar` for the configured Baikal calendar, and verify with a connectivity check against a test calendar
- [x] 4.2 Implement VEVENT creation with the date-only/start-only/full-range mapping rules, and verify with tests for all three time-completeness cases
- [x] 4.3 Implement push-on-create that stores the returned CalDAV UID on the local entry, and verify by creating an entry and confirming the UID round-trips
- [x] 4.4 Implement update/delete propagation keyed by the stored UID, and verify with tests that update and delete a local entry and check the corresponding VEVENT changed or is gone
- [x] 4.5 Implement sync-failure handling (local entry persists, failure is reported, push is retryable) and verify by simulating an unreachable calendar during logging

## 5. Metadata

- [x] 5.1 Implement an OMDb client (title/IMDb ID lookup, local caching of successful matches) and verify with tests covering a match and a no-match response
- [x] 5.2 Wire OMDb fetch into the logging flow, storing IMDb/Rotten Tomatoes/Metacritic ratings, and verify an entry gains ratings after logging
- [x] 5.3 Implement manual Letterboxd link/rating entry and verify it can be attached to and later shown on an entry
- [x] 5.4 Verify an entry can be logged, updated, and synced with no metadata attached at all

## 6. Import

- [x] 6.1 Implement CSV import mapping columns to entry fields, routed through validation and duplicate detection, and verify against a sample CSV fixture
- [x] 6.2 Implement JSON import with the same field set and rules, and verify against a sample JSON fixture
- Descoped: org-mode import. Built and smoke-tested against the real log, then cut - the parser and its test/example fixtures were built directly around real personal viewing history (real venues, dates, titles), which doesn't belong in a public repo. CSV/JSON cover the same import need without that.
- [x] 6.4 Implement the end-of-import summary (imported / skipped-duplicate / failed counts) and verify with a fixture that produces one of each outcome

## 7. Interactive CLI wiring & end-to-end

- [ ] 7.1 Wire all commands (log, list, update, delete, locations, import, sync retry) under the typer app and verify `movie-planner --help` lists them all
- [ ] 7.2 End-to-end test: log an entry, confirm it appears in list output and as a VEVENT on a test Baikal calendar, then update and delete it and confirm both sides reflect it
- [ ] 7.3 Manual walkthrough: import `examples/movies.csv` against a test calendar and review the import summary for unexpected skips or failures
