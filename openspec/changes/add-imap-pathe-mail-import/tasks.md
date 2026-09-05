## 1. Scaffolding

- [x] 1.1 Create the new mail-fetch module/package and its
  `[project.scripts]` entry point in `pyproject.toml`, separate from
  `movie_planner.cli`; verify `uv run <entry-point> --help` runs
- [ ] 1.2 Create the Pathé translation-script module and its own
  `[project.scripts]` entry point, importing `movie_planner.pathe`
  directly; verify it runs standalone
- [x] 1.3 Define the mail tool's own config file shape (IMAP
  host/port/username/password or password_command, `[[chains]]`
  sender_domain/translate entries) and a `<tool> init` (or equivalent)
  that writes a starter copy, matching movie-planner's own
  `password_command` convention; verify a missing/invalid config fails
  with a message naming the problem, not a stack trace
- [x] 1.4 Add masked interactive IMAP password entry (stdlib `getpass`)
  to the config setup, used whenever no `password_command` is already
  configured; verify the password is never accepted as a CLI flag and
  never echoed - a fake stdin/tty in tests, not a real terminal

## 2. Mail fetch (IMAP and mbox adapters)

- [x] 2.1 Define the `MailClient` port (`Protocol`): search by sender
  domain, return raw messages
- [x] 2.2 Implement the `imaplib`-based IMAP adapter; verify against a
  fake/mock transport in tests, no real mailbox needed
- [x] 2.3 Implement the stdlib-`mailbox`-based mbox adapter; verify
  against a small fixture `.mbox` file committed to `tests/fixtures/`
- [x] 2.4 Add config for selecting and configuring whichever source is
  in use (IMAP host/port/credentials, or an mbox file path); verify a
  missing/invalid config for the selected source fails with a message
  naming the problem
- [x] 2.5 Implement sender-domain search across configured chains,
  shared by both adapters; verify with a fake client returning a mixed
  set of senders that only matching-domain messages are returned
- [x] 2.6 Implement generic envelope extraction (from, subject, date,
  plain-text body) from a raw fetched message, reusing the same
  MIME-vs-plain-text detection approach `pathe.py`'s `_extract_body`
  already uses; verify against both a raw `.eml` fixture and an
  already-extracted-text fixture, through both adapters
- [x] 2.7 Report an IMAP connection/auth failure, or a missing/unreadable
  mbox file, clearly, and produce no output file either way; verify
  with a fake client raising on connect and a nonexistent mbox path
- [x] 2.8 Verify against a real Thunderbird-produced local-folder file
  (not just a hand-written fixture) that its default mbox format is
  actually readable by the mbox adapter as claimed in the spec - if it
  isn't, correct the spec rather than leaving an unverified claim in it
  **(caveat: no Thunderbird binary available in this sandbox - verified
  via Thunderbird's own official source docs instead, confirming mbox
  is genuinely the default local-folder format; not empirically tested
  against a real Thunderbird-produced file. Worth a real test if that
  ever becomes possible.)**
- [x] 2.9 Add `--since`/`--until` scoping to both adapters (`since`/
  `until` params on `MailClient.fetch`), verified with a fake
  client/mbox fixture; omitting both searches everything (unchanged).
  The CLI-level `--since`/`--until`/"N ago" flags themselves land with
  the `fetch` command in the next PR (task group 3/4), since that
  command doesn't exist yet

## 3. Chain dispatch and translation scripts

- [x] 3.1 Implement sender-domain → configured script lookup and
  subprocess invocation (envelope as JSON on stdin, one parsed row as
  JSON on stdout, exit 0; non-zero/empty stdout means "not recognized");
  verify with a fake script (a small test fixture executable)
- [x] 3.2 Implement the Pathé translation script's envelope-in/row-out
  contract: call `parse_pathe_email` on the envelope body, map
  `PatheBooking` to a `movies.schema.json` row (title, date, medium=
  "cinema", venue=cinema, start_time, end_time - no `notes`, no
  `booking_ref`); verify against `tests/fixtures.py`'s existing Pathé
  email fixtures, both success and `PatheEmailParseError` cases
- [x] 3.3 Stamp every emitted row's `source` with the matched sender
  domain after the translation script returns, overwriting whatever the
  script itself set; verify a script that omits or sets a different
  `source` value still ends up tagged correctly in the output
- [x] 3.4 Route "no configured chain for this sender" and "script exited
  non-zero" both into the same unrecognized-email path; verify both
  cases land in the review table, not the output file

## 4. Output

- [x] 4.1 Write every recognized row into one output JSON file, valid
  against `examples/movies.schema.json`; verify with a schema-validation
  test (`jsonschema`, same pattern as `tests/test_examples_schema.py`)
- [x] 4.2 Print the unrecognized-email review table (from, subject,
  date); verify its content against a fixture set of unrecognized
  messages
- [x] 4.3 Verify the whole tool is stateless: running it twice against
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

- [x] 6.1 Implement the buffered time-range overlap check in
  `duplicates.py`, folded into `find_duplicate` alongside the existing
  fuzzy-title/same-day check; verify each scenario in
  `specs/duplicate-detection/spec.md`'s delta has a passing test
- [x] 6.2 Verify existing `find_duplicate`/`duplicate-detection` tests
  (title-based) still pass unchanged
- [x] 6.3 Verify the bulk-import and interactive-logging call sites
  (`run_import`, `log`) surface an overlap-flagged candidate the same
  way they already surface a title-flagged one - no new UI path

## 7. Docs

- [ ] 7.1 Write the new tool's own `README.md` (requirements,
  installation, config, usage, the translation-script contract for
  anyone adding a second chain), with a `--help` screenshot generated
  by `rich-codex` the same way `movie-planner`'s own README got one in
  #135
- [ ] 7.2 Cross-link it from movie-planner's own `README.md` (a short
  pointer, same shape as the existing `movie-planner-web` mention) -
  discoverable, without `movie-planner --help` ever mentioning Pathé or
  IMAP
- [ ] 7.3 Update `CHANGELOG.md`/release notes to call out the
  **BREAKING** `booking_ref` removal from the import contract
- [ ] 7.4 Write `docs/architecture.md`: a Mermaid diagram and short
  prose showing how movie-planner (CLI + SQLite store), the CalDAV
  calendar, movie-planner-web, OMDb, and this mail tool all relate -
  data flow, not implementation detail; linked from the main
  `README.md`
- [ ] 7.5 (scope check, not yet decided - see below) If the main
  `README.md` has grown too large by this point, split the heavier
  `## Usage` subsections out into `docs/` pages (per `rules/docs.md`'s
  "anything that outgrows the README moves into docs/"), leaving the
  README as a concise entry point; this is a general documentation-
  quality task, not specific to Pathé mail import, so may land as its
  own separate PR/issue rather than folded into #140 - confirm with the
  user before doing the split

## 8. Piped composition (fetch | translate | import)

- [x] 8.1 Add an envelope-only output mode to the fetch tool (one JSON
  envelope per line on stdout, no dispatch to any translation script);
  verify its output is valid input to the Pathé translation script run
  standalone
- [x] 8.2 Update the Pathé translation script (and the dispatch
  contract generally) so "doesn't recognize this envelope" writes a
  diagnostic to stderr and emits nothing to stdout when run standalone,
  distinct from the exit-code signal used when invoked internally by
  the fetch tool's single-command mode; verify both call shapes.
  **Turned out to need one more change while implementing**: the
  translation script now reads/writes NDJSON (one envelope/row per
  line) rather than one object per invocation, since
  `--envelopes-only` emits many envelopes on one stream and the script
  has to consume all of them, not just the first - dispatch.py's
  internal single-envelope invocation still works unchanged, since a
  single `json.dumps(...)` call is always exactly one line.
- [x] 8.3 `movie-planner import`: accept no file path, reading JSON
  from stdin instead - a bare object (one row) or an array; verify
  both shapes, and that a file path argument still works unchanged
  with stdin untouched
- [x] 8.4 End-to-end: verify `fetch --envelopes-only | pathe-translate
  | movie-planner import` on a fixture mailbox produces the same
  entries as running the fetch tool as one command against the same
  fixture and then importing its output file. Verified as three real
  OS processes piped together (not simulated) producing the expected
  entry; equivalence with the single-command path is established via
  that path's own separately-passing tests rather than a literal
  side-by-side diff in one test
