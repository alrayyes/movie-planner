## 1. Read the calendar back

- [x] 1.1 Add `list_events() -> list[str]` to `CalendarClient`, backed
  by the existing `_CalDAVCalendar.events()` the protocol already
  declares; verify against a fake calendar returning a fixed set of
  events
- [x] 1.2 Verify `check_connection` is unaffected (still just calls
  `events()` for connectivity, doesn't route through the new method)

## 2. Reverse-map a VEVENT to candidate fields

- [x] 2.1 Parse SUMMARY/DTSTART/DTEND back to title/date/start_time/
  end_time, covering all three time-completeness shapes
  `build_vevent` produces (date-only, start-only, start+end); verify
  each round-trips through `build_vevent` then back correctly
- [x] 2.2 Resolve LOCATION to a venue name per design.md's rule
  (strip a trailing `", <city>, <country>"` only when it exactly
  matches the event's own X-CITY/X-COUNTRY; otherwise use LOCATION
  verbatim), then through the existing `Store.get_or_create_venue`;
  verify both the matching and non-matching cases, and that a known
  alias still resolves to its canonical venue

  Alias-name resolution (the pure, no-store-write half of
  `get_or_create_venue`) happens during detection, via the same
  `KNOWN_VENUE_LOCATIONS` table; the actual `Store.get_or_create_venue`
  call (which can create a venue row) is deferred to applying an
  *approved* candidate in task group 4 - calling it during mere
  detection would create a venue row before any approval, which
  proposal.md's "nothing is written without approval" guarantee
  doesn't carve an exception for. Flagged, not silently decided -
  see the note at the end of this file.
- [x] 2.3 Read X-DIRECTOR/X-ACTORS/X-GENRE/X-YEAR/X-POSTER-URL/X-ROW/
  X-SEAT directly, each present-or-None with no interpretation;
  verify an event missing some or all of these maps to None for
  those fields, not an error
- [x] 2.4 Verify DESCRIPTION is never parsed for any of this - a
  candidate's ratings/notes/Letterboxd/chain fields are always
  None on a new candidate and always absent from a changed
  candidate's diff, regardless of what DESCRIPTION contains

## 3. Detect candidates

- [x] 3.1 Implement new-entry detection: a calendar event whose UID
  matches no local entry's `caldav_uid`; verify against a fixture
  calendar/store pair with a known extra event
- [x] 3.2 Implement changed-entry detection: for each local entry
  with a `caldav_uid`, compare its linked event's structured fields
  (per task group 2) against the stored entry, flagging a candidate
  when any differ; verify a single differing field is caught, and
  that a DESCRIPTION-only difference is not
- [x] 3.3 Implement removed-entry detection: a local entry with a
  `caldav_uid` matching no event currently on the calendar; verify
  against a fixture store entry whose event was deleted
- [x] 3.4 Verify a missing X-* property on a matched entry produces a
  changed-candidate diff phrased as "unknown", not as a confirmed
  deletion (design.md's movie-planner-web#294 mitigation)

  Implemented in `calendar_pull.py`'s `detect_candidates`/
  `parse_event`/`ParsedEvent`. Detection itself just reports the raw
  diff (stored value -> `None`); the "unknown, not deletion" framing
  is a presentation concern for task 4.1's CLI output, not detection
  logic - matches design.md's own "this is presentation, not
  detection logic" note.

## Note: two things task groups 1-3 could not resolve on their own

Surfaced rather than guessed, per this change's own "never write to
the store without approval" and "never guess" conventions - both need
a decision before task group 4 (the actual `sync pull` command) can
be implemented:

1. **New-candidate medium.** `Store.create_entry` requires a
   `medium_id` (NOT NULL column), but nothing in proposal.md/design.md/
   spec.md says how a purely calendar-sourced new candidate gets one.
   A `LOCATION` only ever appears for a physical-place medium, but its
   *absence* doesn't say which medium a candidate is (`netflix`,
   `youtube`, some other streaming service, or a physical place movie-
   planner-web simply didn't send a venue for) - genuinely ambiguous,
   not something to default silently.
2. **Fields added since this change was drafted.** #236/#237 shipped
   after this proposal/design/spec were written and added ten more
   structured `X-*` properties (`X-RATED`, `X-RUNTIME`,
   `X-MOVIE-LANGUAGE`, `X-MOVIE-COUNTRY`, `X-METASCORE`,
   `X-IMDB-VOTES`, `X-DVD`, `X-BOX-OFFICE`, `X-PRODUCTION`,
   `X-WEBSITE`) plus `X-TRAILER-URL` - all structured, not
   `DESCRIPTION`-derived, so by the same reasoning spec.md already
   applies to director/actors/genre/etc. they arguably belong in the
   "changed" comparison too. Left out of `_diff_entry` for now,
   matching spec.md's literal, closed field list rather than silently
   expanding it - a real drift between this change's own artifacts and
   the current codebase, worth a spec update rather than an
   implementation-time judgment call.

## 4. `sync pull` command and approval flow

- [x] 4.1 Add `movie-planner sync pull`, fetching every event via
  `list_events`, running detection (group 3), and presenting each
  candidate one at a time with its diff and a y/N prompt, same
  confirmation pattern `from-pathe-email` already uses; verify via a
  CLI test simulating approve and decline on different candidate
  types
- [x] 4.2 Verify an approved new candidate creates a local entry via
  `Store.create_entry`, an approved change updates via
  `Store.update_entry`, and an approved removal deletes via
  `Store.delete_entry`
- [x] 4.3 Verify a declined candidate leaves the store unchanged and
  is offered again on a subsequent `sync pull` run with no
  intervening calendar change
- [x] 4.4 Verify `list`/`show` are untouched by this change - they
  still read only the local store, never the calendar

## 5. Docs

- [x] 5.1 Update `docs/architecture.md`'s diagram and "What each
  piece actually knows about" section to show `sync pull` as the one
  path data flows calendar-to-store, keeping the rest of the
  push-only description accurate
- [x] 5.2 Update `README.md`'s sync section to mention `sync pull`
  alongside `sync refresh`/`sync retry`, noting it's a manually-run,
  approval-gated reconciliation step, not automatic
