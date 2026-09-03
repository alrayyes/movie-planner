## 1. Store: booking reference

- [x] 1.1 Add `booking_ref` to `entries` (migrated column, plain index, no
  `UNIQUE` constraint) and verify a fresh DB and an existing pre-migration
  DB both end up with the column via a store test
- [x] 1.2 Add `Store.get_entry_by_booking_ref` (or equivalent lookup) and
  verify with a test that creates two entries and looks one up by its
  booking ref
- [x] 1.3 Wire `booking_ref` through `create_entry`/`update_entry`/`Entry`
  and verify round-trip via a store test

## 2. Calendar: description

- [x] 2.1 Add a pure function that builds description text from ratings,
  Letterboxd link/rating, and optional screening-details text, returning
  `None` when there's nothing to include, and verify with unit tests
  covering: all fields present, no fields present, partial fields
- [x] 2.2 Wire that into `build_vevent` (new `description` parameter) and
  verify with a test that a built VEVENT's `DESCRIPTION` matches
- [x] 2.3 Pass the built description through `CalendarSync.push_new` and
  `push_update` and verify with a test against the existing CalDAV test
  double that the pushed ical includes it

## 3. Shared create-or-update push/log helper

- [x] 3.1 Extract the optional-OMDb-fetch -> create-or-update calendar-push
  tail into one function (`_finalize_entry`), used by `log`, `import`, and
  `sync retry`; verified existing `log`/`import`/`sync retry` tests still
  pass unchanged against the refactor. **Narrowed from the task as
  originally written**: the dedup-check step stays in each command rather
  than folding into the same function - `log`'s interactive
  confirm-or-reject, `import`'s silent skip-or-force, and
  `from-pathe-email`'s booking-ref-then-fuzzy-match-then-tty-confirm (group
  5) are different enough in shape that cramming them behind one
  parameterized signature looked like the kind of abstraction
  `rules/architecture.md` says to skip when a port straight onto the
  domain already reads clearly. The metadata+push tail was the actual
  duplicated logic (and the actual bug - task 3.2); that's what's shared.
- [x] 3.2 Make `import_command` use the metadata-fetch step of the shared
  helper and verify with a test that an imported row ends up with OMDb
  ratings when a match exists

## 4. Pathé email parsing

- [x] 4.1 Add a parser that accepts either a raw MIME message (extracting
  the `text/plain` part) or already-plain text, and verify with a test
  using a raw `.eml` fixture and a plain-text fixture of the same email
- [x] 4.2 Extract title, date, start time, expected end time, cinema name,
  auditorium/screening-format/seat text, and booking number from the
  parsed body, and verify with a test against a real-shaped fixture email
- [x] 4.3 Report a clear parse failure (not a partial/wrong entry) when
  the content doesn't match the expected format, and verify with a test
  using a non-Pathé/garbage input

## 5. `from-pathe-email` command

- [x] 5.1 Accept the email as a file path argument or via stdin, and
  verify both paths with CLI tests
- [x] 5.2 Look up an existing entry by parsed booking number first,
  falling back to `find_duplicate` on title/date when no booking-number
  match exists, and verify both paths with tests (booking-ref match found;
  no booking-ref match but fuzzy title/date match; neither)
- [x] 5.3 Show the parsed fields (and, on a match, old vs. new) and
  confirm via `/dev/tty` rather than stdin when the email came from stdin,
  falling back to a normal prompt when it came from a file, and verify
  with a test that a piped email plus a simulated tty response produces
  the expected create/update/no-op. Added `--yes` to skip confirmation
  entirely (no controlling terminal at all - e.g. a mail-pipe automation)
  and a clear error rather than a hang when neither is available.
- [x] 5.4 On confirmation, create or update the entry via the shared
  helper from group 3 (metadata fetch on, calendar push on) with
  `booking_ref` set, and passing the parsed screening-details text through
  to the description builder from group 2
- [x] 5.5 Update `README.md`'s Usage section with the new command and how
  piping works

## 6. `refresh` command

- [x] 6.1 Add `sync refresh`: for every entry, fetch OMDb only when
  ratings are missing (never re-fetch an entry that already has them),
  then push create-or-update via the same helper `sync retry` uses, and
  verify with a test covering a mix of never-synced, already-synced, and
  already-rated entries
- [x] 6.2 Report before running how many OMDb lookups it's about to make,
  and a summary afterward (refreshed count, metadata fetched count), and
  verify with a CLI test on output
- [x] 6.3 Update `README.md`'s Usage section (`refresh` alongside
  `sync retry`, and the distinction between them)

## 7. Verification

- [x] 7.1 Run the full test suite and confirm it passes
- [x] 7.2 Manually ran `from-pathe-email` piped from stdin against a
  fixture matching the real email's shape (`--config` pointed at a real,
  unreachable CalDAV/OMDb to confirm the "sync failure doesn't lose the
  local entry" behavior holds): confirmed the fields parsed correctly,
  the entry was created with `booking_ref` set, and a second, rescheduled
  email with the same booking number updated that same entry (id
  unchanged) rather than creating a second one.
