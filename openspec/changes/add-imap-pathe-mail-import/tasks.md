## 1. Scaffolding

- [ ] 1.1 Create the new mail-fetch module/package and its
  `[project.scripts]` entry point in `pyproject.toml`, separate from
  `movie_planner.cli`; verify `uv run <entry-point> --help` runs
- [ ] 1.2 Create the Pathé translation-script module and its own
  `[project.scripts]` entry point, importing `movie_planner.pathe`
  directly; verify it runs standalone
- [ ] 1.3 Define the mail tool's own config file shape (IMAP
  host/port/username/password or password_command, `[[chains]]`
  sender_domain/translate entries) and a `<tool> init` (or equivalent)
  that writes a starter copy, matching movie-planner's own
  `password_command` convention; verify a missing/invalid config fails
  with a message naming the problem, not a stack trace

## 2. Mail fetch (IMAP and mbox adapters)

- [ ] 2.1 Define the `MailClient` port (`Protocol`): search by sender
  domain, return raw messages
- [ ] 2.2 Implement the `imaplib`-based IMAP adapter; verify against a
  fake/mock transport in tests, no real mailbox needed
- [ ] 2.3 Implement the stdlib-`mailbox`-based mbox adapter; verify
  against a small fixture `.mbox` file committed to `tests/fixtures/`
- [ ] 2.4 Add config for selecting and configuring whichever source is
  in use (IMAP host/port/credentials, or an mbox file path); verify a
  missing/invalid config for the selected source fails with a message
  naming the problem
- [ ] 2.5 Implement sender-domain search across configured chains,
  shared by both adapters; verify with a fake client returning a mixed
  set of senders that only matching-domain messages are returned
- [ ] 2.6 Implement generic envelope extraction (from, subject, date,
  plain-text body) from a raw fetched message, reusing the same
  MIME-vs-plain-text detection approach `pathe.py`'s `_extract_body`
  already uses; verify against both a raw `.eml` fixture and an
  already-extracted-text fixture, through both adapters
- [ ] 2.7 Report an IMAP connection/auth failure, or a missing/unreadable
  mbox file, clearly, and produce no output file either way; verify
  with a fake client raising on connect and a nonexistent mbox path
- [ ] 2.8 Verify against a real Thunderbird-produced local-folder file
  (not just a hand-written fixture) that its default mbox format is
  actually readable by the mbox adapter as claimed in the spec - if it
  isn't, correct the spec rather than leaving an unverified claim in it

## 3. Chain dispatch and translation scripts

- [ ] 3.1 Implement sender-domain → configured script lookup and
  subprocess invocation (envelope as JSON on stdin, one parsed row as
  JSON on stdout, exit 0; non-zero/empty stdout means "not recognized");
  verify with a fake script (a small test fixture executable)
- [ ] 3.2 Implement the Pathé translation script's envelope-in/row-out
  contract: call `parse_pathe_email` on the envelope body, map
  `PatheBooking` to a `movies.schema.json` row (title, date, medium=
  "cinema", venue=cinema, start_time, end_time - no `notes`, no
  `booking_ref`); verify against `tests/fixtures.py`'s existing Pathé
  email fixtures, both success and `PatheEmailParseError` cases
- [ ] 3.3 Stamp every emitted row's `source` with the matched sender
  domain after the translation script returns, overwriting whatever the
  script itself set; verify a script that omits or sets a different
  `source` value still ends up tagged correctly in the output
- [ ] 3.4 Route "no configured chain for this sender" and "script exited
  non-zero" both into the same unrecognized-email path; verify both
  cases land in the review table, not the output file

## 4. Output

- [ ] 4.1 Write every recognized row into one output JSON file, valid
  against `examples/movies.schema.json`; verify with a schema-validation
  test (`jsonschema`, same pattern as `tests/test_examples_schema.py`)
- [ ] 4.2 Print the unrecognized-email review table (from, subject,
  date); verify its content against a fixture set of unrecognized
  messages
- [ ] 4.3 Verify the whole tool is stateless: running it twice against
  an unchanged fake mailbox produces identical output both times

## 5. Remove `booking_ref` and add `source` to the generic import contract

- [x] 5.1 Drop `booking_ref` from `ImportRow` and from
  `run_import`/`_row_from_dict`'s field handling; verify
  `tests/test_import.py`'s booking_ref-specific tests are removed and
  the rest still pass
- [x] 5.2 Add `source` to `ImportRow`/`run_import`/`_row_from_dict`,
  stored as-is with no interpretation, same pattern as `notes`; verify
  a new `test_import.py` case
- [x] 5.3 Drop `booking_ref` from and add `source` to
  `examples/movies.schema.json`; verify `tests/test_examples_schema.py`
  still passes with both changes
- [x] 5.4 Update `examples/README.md` and `README.md`'s Import examples
  section: drop the `booking_ref` mention, document `source`
- [x] 5.5 Verify `from-pathe-email` and its own tests
  (`tests/test_cli.py`) are untouched and still pass unchanged

## 6. Overlapping-screening duplicate detection

- [ ] 6.1 Implement the buffered time-range overlap check in
  `duplicates.py`, folded into `find_duplicate` alongside the existing
  fuzzy-title/same-day check; verify each scenario in
  `specs/duplicate-detection/spec.md`'s delta has a passing test
- [ ] 6.2 Verify existing `find_duplicate`/`duplicate-detection` tests
  (title-based) still pass unchanged
- [ ] 6.3 Verify the bulk-import and interactive-logging call sites
  (`run_import`, `log`) surface an overlap-flagged candidate the same
  way they already surface a title-flagged one - no new UI path

## 7. Docs

- [ ] 7.1 Write the new tool's own `README.md` (requirements,
  installation, config, usage, the translation-script contract for
  anyone adding a second chain)
- [ ] 7.2 Cross-link it from movie-planner's own `README.md` (a short
  pointer, same shape as the existing `movie-planner-web` mention) -
  discoverable, without `movie-planner --help` ever mentioning Pathé or
  IMAP
- [ ] 7.3 Update `CHANGELOG.md`/release notes to call out the
  **BREAKING** `booking_ref` removal from the import contract
