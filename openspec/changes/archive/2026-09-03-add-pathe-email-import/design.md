## Context

See proposal.md for motivation. Relevant current state:

- `build_vevent` (`calendar_sync.py`) sets only `summary`, `location`,
  `dtstart`/`dtend` — no `description` field exists anywhere yet.
- `import_command` (`cli.py`) never calls the OMDb fetch `log` does.
- `sync retry` only touches entries with no `caldav_uid`.
- The dedup-check -> create/update -> optional OMDb fetch -> calendar push
  -> report sequence is duplicated between `log` and `import_command`
  today, and would be duplicated a third time by `from-pathe-email`
  without extraction.
- `duplicates.py`'s `find_duplicate` and `build_vevent` are pure functions;
  `store.py`, `calendar_sync.py`'s `CalendarClient`, and `omdb.py` are the
  I/O shell around them (functional core / imperative shell, applied
  already, not being introduced here).
- `calendar_sync.py` already has a `Protocol` port (`_CalDAVCalendar`) in
  front of the `caldav` library — the one place ports-and-adapters is
  already in use, for the highest-risk integration. Nothing here extends
  that pattern to OMDb or SQLite; both stay concrete, single-implementation
  dependencies.

## Goals / Non-Goals

**Goals:**

- Parse a Pathé confirmation email (piped or from a file) into the same
  shape logging/importing already uses.
- Match a re-sent confirmation to the entry it updates, via booking
  number, falling back to the existing fuzzy title/date check.
- Give every pushed calendar event a description, without adding a
  general-purpose "notes" column to `entries`.
- Stop `import` and `refresh` from being silent about metadata, without
  hammering OMDb's rate-limited free tier.

**Non-Goals:**

- No general architecture change. This stays functional-core/imperative-
  shell as-is; no `domain/`/`adapters/`/`application/` restructuring, no
  repository interface in front of `Store` (SQLite is the only
  implementation there will ever be), no port added for OMDb.
- No persisted auditorium/seat/screening-format field. That data is parsed
  only to build the calendar description text.
- No handling of a Pathé cancellation email in this change — only booking
  confirmations (new or re-sent).
- No support for a booking confirmation covering more than one film.

## Decisions

**One shared orchestration helper, not a new layer.** Extract the
dedup-check -> create-or-update -> optional-OMDb -> calendar-push sequence
into one function in `cli.py` (or a small new module next to it),
parameterized by how confirmation is obtained (interactive prompt vs. the
parsed-email confirmation) and whether metadata fetch runs. `log`,
`import_command`, and `from-pathe-email` all call it. This is the one
piece of real orchestration duplication in the codebase (the rule in
`rules/architecture.md` about a "use case" layer being worth it for
multi-step workflow applies here specifically) — everything else stays as
thin as it is today.

**Booking number: indexed, not unique.** Pathé's own uniqueness guarantee
for booking numbers is unconfirmed. A `UNIQUE` constraint would let a
write fail outright if that assumption is wrong; a plain index plus the
mandatory confirmation step is the safety net instead — a false-positive
match is something the user sees and can reject, not something that can
corrupt a write.

**Email parsing: handle both raw MIME and plain text.** `cat blah.eml |
movie-planner from-pathe-email` pipes a raw RFC 822 message (headers,
multipart MIME) when it comes from a real mailbox. Parse with the `email`
stdlib module when the content looks like a MIME message (has headers and
a boundary), extracting the `text/plain` part; otherwise treat the input
as already-extracted plain text. This covers both a real piped `.eml` and
a pasted plain-text body without asking the user to pre-process either
one.

**Confirmation reads from `/dev/tty`, not stdin.** When the email is piped
in, stdin is already consumed by it. Read all of stdin first, then open
`/dev/tty` directly for the yes/no confirmation — the same approach
`git commit`/`sudo` use for a piped-stdin-plus-interactive-prompt
situation. When the email instead comes from a file argument, stdin is
free and the confirmation can use the normal prompt path.

**Description content, and why it isn't a stored field.** The VEVENT
description is built at push time from: OMDb ratings, Letterboxd
link/rating (already columns on `Entry`), and, for a Pathé-sourced entry
only, the auditorium/screening-format/seat text parsed from that email.
The latter is provenance for the calendar event, not a fact anything
queries by — parsing it straight into description text avoids a schema
change for data that has nowhere else to be used. This was chosen over
adding a `notes` column, which would let it round-trip through `update`
but isn't needed for anything this change does.

**`refresh` stays separate from `sync retry`.** See proposal.md's What
Changes — different cost profile (all entries + OMDb calls vs. unsynced
entries only, no OMDb calls) is reason enough to keep the names distinct,
even though `refresh`'s push step is a strict superset of `retry`'s. Both
call the same create-or-update push step, so there's no duplicated push
logic, only a different entry selection and an extra metadata-backfill
step ahead of it for `refresh`.

## Risks / Trade-offs

- **[Risk] Booking number turns out not to be unique in practice, and two
  different bookings collide.** -> Mitigation: no `UNIQUE` constraint to
  violate, and the confirmation step surfaces the mismatch (wrong title
  and date against a real one) before anything is written.
- **[Risk] Pathé changes its email template (wording, field order,
  HTML/plain-text ratio) and parsing silently breaks or misparses.** ->
  Mitigation: the "Unrecognized content" scenario in
  `pathe-email-import`'s spec requires a clear parse-failure report rather
  than a wrong or partial entry; the confirmation step is a second
  backstop.
- **[Risk] `refresh` run against a large history triggers many OMDb
  calls at once against a rate-limited free-tier key, since every
  CSV/JSON-imported entry has been missing ratings until now.** ->
  Mitigation: refresh only fetches for entries missing ratings (never
  re-fetches), and `omdb.py` already caches successful lookups within a
  run; a large first run is still a real one-time cost worth calling out
  in the command's own output (e.g. reporting how many lookups it's about
  to make) rather than silently blocking.

## Migration Plan

- New `booking_ref` column added the same way earlier columns were
  (`store.py`'s `_MIGRATED_COLUMNS`, `ALTER TABLE ... ADD COLUMN` against
  an existing database) — no destructive change, existing rows get
  `NULL`.
- `build_vevent` gaining a description changes what gets pushed on the
  next `update`/`refresh` for existing entries, not on its own — nothing
  is rewritten until a push happens.
