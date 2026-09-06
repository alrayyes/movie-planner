## Context

See `proposal.md` for motivation. Relevant current state:

- `CalendarClient`/`_CalDAVCalendar` (`calendar_sync.py`) already expose
  `events() -> Sequence[object]`, but nothing reads its return value
  today - `check_connection` just calls it and discards the result.
- `build_vevent`/`build_description`/`_extra_properties` are the
  forward direction this change has to mirror in reverse: `SUMMARY`
  (title), `DTSTART`/`DTEND` (date/start_time/end_time), `LOCATION`
  (venue, optionally `", <city>, <country>"` appended), custom `X-*`
  properties (poster/director/actors/genre/year/city/country/row/seat),
  and a free-text `DESCRIPTION` combining ratings, Letterboxd, chain,
  notes, and screening details with no per-field markers beyond a
  human-readable label prefix per line.
- movie-planner-web writes to the same calendar independently
  (confirmed directly with that project): blind PUTs, no
  conflict check, and - a real bug on its side, just filed as
  movie-planner-web#294 - its own VEVENT parser only reads a fixed
  allow-list of `X-*` properties, so editing *any* field there on an
  entry that has `X-CITY`/`X-COUNTRY` (or, once it lands there,
  `X-ROW`/`X-SEAT`) silently drops them from the regenerated event.

## Goals / Non-Goals

**Goals:**

- Detect calendar-side new/changed/removed entries relative to the
  local store, using only calendar fields movie-planner itself already
  writes in a structured, unambiguous form.
- Never write to the store without explicit, per-candidate approval.

**Non-Goals:**

- Reconstructing ratings, Letterboxd data, chain, or notes from
  `DESCRIPTION`. That text has no reliable per-field boundary beyond a
  label prefix `build_description` itself controls, and reverse-parsing
  it would mean maintaining a second parser that has to track
  `build_description`'s own format forever. These fields are left
  alone entirely by `sync pull` - unset (`None`) on a new candidate,
  unchanged on a changed candidate. OMDb-derived ones are still
  reachable the normal way (`sync refresh`); notes/Letterboxd stay a
  manual `update`.
- Real two-way, continuous sync. This is a manually-triggered,
  one-shot reconciliation pass - not a background job, not something
  `list`/`show` trigger implicitly.
- Fixing movie-planner-web's own allow-list bug (#294) - out of scope
  for this repo, tracked on that side.

## Decisions

**Venue resolution: exact-match strip, not a guess.** `LOCATION` is
either a bare venue name or `"<venue>, <city>, <country>"`
(`_venue_location` in `cli.py`). Since a manually-typed-via-web
`LOCATION` might not follow this shape at all, `sync pull` only strips
a trailing `", <city>, <country>"` when it *exactly* matches the
event's own `X-CITY`/`X-COUNTRY` properties (when present) - otherwise
the whole `LOCATION` string is used as the venue name verbatim, same
"never guess" rule the rest of this codebase already follows for venue
data. Either way, resolution goes through the existing
`Store.get_or_create_venue`, so a recognized name still gets its
chain/city/country/coordinates filled in and a known alias still
resolves to its canonical venue (#196/#227) - no new venue-matching
logic.

**"Changed" is scoped to what's actually parsed.** A matched entry
(same `caldav_uid`) is flagged changed only if a *structured* field
differs: title, date, start_time, end_time, venue (by resolved name),
`director`/`actors`/`genre`/`release_year`/`poster_url`/`row`/`seat`
(each straight from its `X-*` property, present-or-absent). Ratings/
notes/Letterboxd are never compared, so `DESCRIPTION` formatting
differences can never produce a false "changed" flag.

**A missing `X-*` property is "unknown," not "user deleted this."**
Per movie-planner-web#294, an event's own `X-*` properties can go
missing as a side effect of an unrelated edit on that side, not a
deliberate removal. `sync pull` still surfaces this as a diff line
(e.g. `row: '5' -> (none)`) for the user to judge, but the copy shown
alongside it says so plainly, rather than implying certainty about
intent. This is presentation, not detection logic - the diff is
computed the same way regardless of *why* a property is gone.

**Per-item approval, not a bulk table.** Confirmed directly: each
candidate (new/changed/removed) is shown with its diff and a
`y/N` prompt, one at a time - the same shape `from-pathe-email`
already uses, not a `git status`-style summary-then-bulk-approve.
Slower for a large first pull, but nothing is approved by accident,
and it matches the one existing precedent in this codebase for
"show the user what would change, then confirm" rather than
introducing a second UX pattern.

**`CalendarClient` gains a real read method.** `list_events() -> list[str]`
(raw iCalendar text per event), backed by the existing
`_CalDAVCalendar.events()` the protocol already declares - the first
thing in this codebase to actually use its return value rather than
just calling it for a connectivity check.

**Declining leaves the store untouched, not marked "seen."** A
declined candidate is not recorded anywhere - running `sync pull`
again re-offers it exactly as before, unless the calendar itself
changed again in the meantime (in which case it's evaluated fresh, not
compared against the earlier declined version). Simpler than tracking
per-user dismissals, and consistent with "the store is only ever
changed by explicit approval."

## Risks / Trade-offs

- **[Risk]** movie-planner-web's allow-list bug (#294) means a
  `sync pull` run today could show real, false "row/seat removed"
  diffs for any entry edited there after #218 shipped, purely as a
  side effect of unrelated edits, not intentional. → **Mitigation**:
  the "missing property = unknown, not deletion" framing above; no
  code-level guard is possible from this side until #294 ships, so
  this is a documented, accepted gap, not something this change tries
  to work around.
- **[Risk]** A calendar with hundreds of entries (369 real ones today)
  means `sync pull` fetches and diffs every single event on every run
  - no incremental/since-last-pull tracking. → **Mitigation**: accepted
  for a first version; a `--since`/watermark optimization is a
  reasonable follow-up once real usage shows this is actually slow,
  not designed speculatively now.
- **[Trade-off]** Per-item approval is slow for a first pull against a
  calendar with a lot of independent web history. → Accepted per the
  confirmed decision above; a `--yes`/bulk-approve flag is a
  reasonable future addition once the per-item flow exists, not part
  of this change.

## Open Questions

(none - the ambiguous cases above were resolved during the explore
conversation rather than deferred)
