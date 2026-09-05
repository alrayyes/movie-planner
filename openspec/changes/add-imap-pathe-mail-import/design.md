## Context

See `proposal.md` for motivation. Relevant current state:

- `pathe.py`'s `parse_pathe_email(raw) -> PatheBooking` is already pure -
  no I/O, raises `PatheEmailParseError` on anything it can't confidently
  parse. Nothing about it needs to change.
- `from-pathe-email` (`cli.py`) does its own booking-number reconciliation
  directly against the store (`Store.get_entry_by_booking_ref`), entirely
  outside `importers.py`/`run_import`. It stays exactly as-is.
- `ImportRow`/`run_import` (`importers.py`) currently accept `booking_ref`
  as a generic field, persisted the same way as any other supplied
  field - documented in `openspec/specs/import/spec.md`'s "A row can
  supply OMDb-derived fields directly" requirement, which lists
  `booking_ref` alongside `letterboxd_url`/`letterboxd_rating`.
- `duplicates.py`'s `find_duplicate` flags a likely duplicate on fuzzy
  title match (>= threshold) AND same calendar day - no time comparison
  at all today.
- `calendar_sync.py`'s `build_description` already renders `entry.notes`
  as its own labelled line, separate from `screening_details`
  (`from-pathe-email`-only, deliberately not persisted -
  `docs/calendar-schema.md`'s "Venue chain/location" section: "Screening
  details aren't stored anywhere on the entry itself").
- No `--json` output exists on any read command (`list`, `show`) today.

## Goals / Non-Goals

**Goals:**

- A standalone tool that turns an IMAP mailbox's Pathé booking
  confirmations into an `import.json` file, reusing `parse_pathe_email`
  unchanged.
- Zero new Pathé- or IMAP-specific knowledge added to `movie_planner`'s
  own package (`cli.py`, `store.py`, `calendar_sync.py`) - the generic
  import contract stays vendor-agnostic.
- A general, title-independent duplicate signal (time overlap) that
  benefits every import source, not just the mail tool.

**Non-Goals:**

- No reschedule reconciliation for mail-tool-sourced bookings. A changed
  time on a re-sent confirmation is not matched back to the original
  entry by any mechanism this change adds - `booking_ref` deliberately
  stays out of the generic pipeline (see proposal.md), and time-overlap
  detection doesn't substitute for it (a genuine reschedule usually moves
  to a non-overlapping time, so it isn't caught either). Fixed by hand
  with `movie-planner update` when noticed.
- No change to `from-pathe-email` - it keeps working exactly as it does
  today.
- No cross-midnight overlap detection. Overlap comparison is gated to
  entries on the same calendar date, same as today's fuzzy-title check -
  a screening that runs past midnight and overlaps the next day's first
  screening isn't caught. Matches the existing date-only (not
  full-timestamp) model everywhere else in the store.
- No OAuth/Gmail-API integration. The mail tool speaks plain IMAP with a
  password (an app password for Gmail, a Bridge-issued one for Proton) -
  if that stops being viable for either provider, that's a separate,
  later change.
- No persisted screening-details field. The mail tool doesn't carry
  auditorium/format/seat text into `import.json` at all (see Decisions) -
  losing it from bulk-imported bookings is accepted, smaller than
  reopening the "notes vs. provenance-only" question `notes` currently
  answers a different way.

## Decisions

**Same repo, new module, second console-script entry point - not a
`movie-planner` subcommand, not a separate repo.** A subcommand
(`movie-planner mail fetch-pathe`) would put "Pathé" and "IMAP" back in
`movie-planner --help`, the exact coupling this change removes. A
separate repo would mean vendoring or duplicating `pathe.py` and
`examples/movies.schema.json`, and a second CI/lint/release setup for
one small tool. A second `[project.scripts]` entry in this same
`pyproject.toml` (working name: `pathe-mail-import`), in its own module
(`src/pathe_mail_import/` or similar - exact path picked in `tasks.md`),
gets the reuse without the coupling: it can `import` from
`movie_planner.pathe` directly, and validate its own output against
`examples/movies.schema.json` in its tests, with zero new lines in
`cli.py`. This same repo also ships a second, separate entry point for
the Pathé translation script itself (see below) - two small binaries,
not one that knows about Pathé internally.

**Stateless, full-mailbox scan every run - no cursor.** Matches "generate
a json with all the data it finds" literally. Every run re-searches and
re-parses every `pathe.nl` message the IMAP search returns; idempotency
against what's already logged is `movie-planner import`'s existing
fuzzy-duplicate handling, not this tool's job. Simpler (nothing to get
wrong about a stored watermark), at the cost of re-fetching the same
history every run - acceptable at personal-mailbox scale.

**One `MailClient` port, two adapters (IMAP, mbox) - not a network-only
abstraction.** Proton Bridge and Gmail both speak IMAP4rev1, so they're
one adapter, config-only difference (`host`, `port`, `username`,
`password`). A local mbox file (mutt's own storage, or Thunderbird's
default local-folder format - also plain mbox) is a second, same-shaped
adapter: same "search by sender domain, return envelopes" contract, no
network at all, read via the stdlib `mailbox` module - no new
dependency. A small `Protocol` (mirroring `calendar_sync.py`'s existing
`_CalDAVCalendar` pattern - the one place a port already exists here)
in front of both keeps chain dispatch, envelope extraction, and output
writing completely unaware of which one is in use. Config picks the
source (`[imap]` section vs. `[mbox]` section, or a `source = "imap" |
"mbox"` key - exact shape decided in `tasks.md`); a third source later
(Maildir, say) is a third adapter behind the same port, not a rewrite.

**IMAP password: masked interactive prompt or `password_command`, never
a flag or hand-typed into the config file.** Same reasoning
`movie-planner` itself already applies to its own CalDAV password - a
flag lands in shell history and a process list; a config file is fine
to hold *a* secret but awkward to type one into by hand. The tool's own
config setup uses `getpass` (stdlib, no dependency) for masked entry,
writing the result to the config file the same way `movie-planner init`
writes a starter config today; `password_command` remains the
alternative for anyone already using a password manager CLI.

**Separate Docker image, not bundled into `movie-planner`'s own.** One
image holding both tools' credentials and volumes undoes the
separation this whole change is about, the moment it reaches
deployment - the mail tool's IMAP password has no reason to be
reachable from a container that also mounts CalDAV/OMDb config, or vice
versa, and their operational shapes differ anyway (`movie-planner` is
run interactively; this tool is a periodic batch job). Built from the
same `Dockerfile` as a second stage/target (`--target
pathe-mail-import`) to avoid duplicating base-image and
dependency-install steps, but published as its own tagged image with
its own minimal `docker run` flags (matching `docs/INSTALL.md`'s
existing least-privilege pattern for `movie-planner`'s own image),
never combined into one runtime container.

**Chain-specific parsing lives entirely outside the tool, as an external
script invoked per email - not a Python parser registered in-process.**
The core tool only ever does two generic things: (1) IMAP fetch + MIME
extraction, turning a raw message into `{from, subject, date, body}` -
nothing chain-specific in this step, since that extraction isn't Pathé
logic either, it's plain email plumbing; and (2) for each email, look up
its sender's domain in config to find which external "translation
script" owns it, run that script as a subprocess, feed it the envelope
as JSON on stdin, and read its result back on stdout. A script that
recognizes the email prints one JSON row (the `movies.schema.json` shape,
minus `booking_ref`) and exits 0; a script that doesn't recognize it
prints nothing and exits non-zero, which routes that email to the
"unsure" table same as a parse failure. Config maps `sender_domain ->
script path`, e.g.:

```toml
[[chains]]
sender_domain = "pathe.nl"
translate = "/path/to/pathe-translate"
```

This is a stronger cut than an in-process registry: adding a second
chain later needs zero changes to the core tool's own code or a new
release of it - just a new script and a new config block, in any
language, tested and versioned independently. Pathé's own script is the
first implementation, shipped from this repo as a thin CLI wrapper
around `movie_planner.pathe.parse_pathe_email` (reads the envelope JSON,
calls it, prints the mapped row or exits non-zero on
`PatheEmailParseError`) - `pathe.py` itself still never has to know any
of this exists.

The stdin-JSON-in/stdout-JSON-out contract is deliberately
language-agnostic - a future chain's translation script has no reason to
be Python just because this one is. Python is simply the right tool for
*this* one, since it reuses `movie_planner.pathe` directly; a chain with
an existing parser in another language, or one that's easier to express
as a small shell/awk/whatever script against a simpler email format,
should just be that.

**Date-range scoping is a caller-computed flag, not tool-side state.**
`--since`/`--until` (plus a relative "N seconds/minutes/hours ago" form
for `--since`) narrow the IMAP/mbox search, but the tool itself still
tracks nothing between runs - it's the caller's job (a cron script) to
work out what window to pass, typically "since I last ran." This keeps
the "stateless, no cursor" decision above intact while making a cron
schedule practical: without it, every run re-scans the entire mail
source regardless of how often it's invoked.

**Envelope-only mode makes the pipeline `fetch | translate | import`
buildable by hand, not just runnable as one command.** The single-
command mode (fetch, dispatch to each chain's script itself, collect
successes/failures, write one output) stays the default - simplest for
a cron job, one exit code to check. But since the translation script is
already a standalone binary with a stdin/stdout contract, the only
missing piece for `movie-planner-mail-fetch --envelopes-only |
pathe-translate | movie-planner import` to work is a mode where the
fetch tool emits envelopes instead of dispatching them itself. Both
modes share the same fetch/envelope-extraction code - this is a second
output mode, not a second implementation. In this mode, a translation
script's "I don't recognize this" signal moves from "return
non-zero, tool routes it to a review table" to "write a diagnostic to
stderr, emit nothing to stdout" - there's no coordinating process left
to build a table, and stderr passing through a pipe is the standard way
a Unix filter reports something without disturbing the data stream.

**`movie-planner import` accepts stdin - a single object or an array,
JSON only.** The immediate motivation is exactly the pipeline above:
without this, `movie-planner import` is always a file, and the
"pipe fetch straight into translate straight into import" story needs
a temp file at the last step regardless. Accepting a bare single object
(not just an array) matters because the common case piping through this
tool is one row at a time, not a batch - forcing `echo '{"...": "..."}'
| jq -s .` (wrap-in-array) on every caller isn't worth avoiding when
the parser can just accept both shapes directly. CSV via stdin is
explicitly out of scope - there's no use case motivating it here, and
piped CSV would need its own header-detection story a file path already
solves for free.

**The core tool stamps `source`, not the translation script.** Every
emitted row gets `source` set to the sender domain that matched it
(`"pathe.nl"`, taken straight from the `[[chains]]` config entry that
dispatched it) - the core tool already knows this to route the email,
so it overwrites whatever the script itself put there rather than
trusting each script to remember to set it consistently. `source` is
opaque to `movie-planner` itself (see the `import` spec delta) - purely
a provenance label a person (or a future tool) can read back later,
the same way `notes` is free text `movie-planner` never interprets.

**Screening details are dropped, not folded into `notes`.** I considered
mapping `PatheBooking.screening_details` into the emitted row's `notes`
field, since `ImportRow` already has one and `build_description` already
renders it. Rejected: `docs/calendar-schema.md` documents screening
details as deliberately *not* persisted - provenance for one calendar
push, gone on the next `sync refresh`/`update` - specifically so it's
never confused with genuine personal notes, which do persist. Routing it
through `notes` reverses that on purpose, for every mail-tool-sourced
booking, as a side effect of a refactor rather than a deliberate call.
Dropping it is a smaller, more honest loss - still available by hand via
`movie-planner update --notes` if wanted.

**Duplicate detection: extend `find_duplicate` itself, not a second
check.** Overlap detection reuses the exact same "flag → confirm
interactively / skip+report during bulk import" plumbing
`duplicate-detection`'s spec already requires, rather than adding a
parallel reporting path. `find_duplicate` flags a candidate when *either*
the existing fuzzy-title-same-day condition holds, *or* its time range
overlaps an existing same-day entry's time range (each inflated by a
30-minute buffer on both ends before comparing) - regardless of title
similarity for the latter. A bare `start_time` with no `end_time` is
treated as a zero-width point (no assumed runtime) rather than invented
duration.

## Risks / Trade-offs

- **[Risk] Full-mailbox re-scan every run gets slow or hits an IMAP rate
  limit as the mailbox grows.** → Mitigation: `pathe.nl`-sender search
  scopes the fetch to a small subset of most inboxes; revisit with a
  stored watermark only if this is measured to actually be slow.
- **[Risk] 30-minute overlap buffer is a guess, not measured against real
  data.** → Mitigation: it's a starting point, not a promise - easy to
  tune once real screenings run through it, and it only ever flags for
  review/confirmation, never silently blocks a write.
- **[Risk] Dropping `booking_ref` from the generic import contract
  breaks anyone who's hand-written a JSON/CSV file supplying it.** →
  Mitigation: no example ever demonstrated it (`examples/movies.json`/
  `movies.csv` never included the field), and it's called out as
  **BREAKING** in the proposal and changelog.
- **[Risk] Password-based IMAP auth (vs. OAuth) is the weaker link for
  Gmail specifically if Google tightens basic-auth/app-password support
  further.** → Mitigation: out of scope per Non-Goals; the config is
  provider-agnostic enough that swapping in an OAuth-based adapter later
  doesn't require touching the `MailClient` port's shape, just a new
  implementation of it.

## Migration Plan

- `ImportRow`/`run_import`: drop `booking_ref` handling. No data
  migration - the `entries.booking_ref` *column* stays (still written
  and read by `from-pathe-email`); only the generic-import code path
  stops touching it.
- `examples/movies.schema.json`/`examples/README.md`/`README.md`: drop
  `booking_ref` from the documented row shape.
- `openspec/specs/import/spec.md`: delta removing `booking_ref` from the
  "row can supply OMDb-derived fields directly" requirement's field
  list.
- `openspec/specs/duplicate-detection/spec.md`: delta adding the
  time-overlap requirement.
- New `pathe-mail-import` package/module, its own `config.toml`-style
  file (XDG path, `password`/`password_command` split matching the
  existing CalDAV/OMDb credential pattern), its own README section or
  top-level doc.
- No rollback complexity: the new tool is additive and separately
  installed; the `booking_ref` field removal only affects code paths
  nothing in this repo's own examples currently exercises.
