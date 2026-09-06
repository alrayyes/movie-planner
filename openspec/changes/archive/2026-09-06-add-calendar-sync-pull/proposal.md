## Why

Sync is push-only: `movie-planner` writes to the calendar but never
reads it back, and `movie-planner-web` (a separate repo) writes to the
same calendar independently. Any create/edit/delete made through web
is therefore invisible to the local store forever - `list`/`show` keep
showing a deleted-via-web entry, show stale data for one edited via
web, and never show one created purely via web at all (issue #168,
confirmed with Ryan directly; the broader "should the calendar become
the sole source of truth" framing in #169 was explicitly rejected in
favor of this narrower fix).

## What Changes

- **New**: `movie-planner sync pull` - fetches every event on the
  configured calendar, compares it against the local store by
  `caldav_uid`, and presents three kinds of candidate change for
  approval, one at a time (same confirm-before-write shape
  `from-pathe-email` already uses):
  - a calendar event with no matching local entry (candidate new
    entry)
  - a local entry whose linked event's content differs from the store
    (candidate change)
  - a local entry whose linked event no longer exists (candidate
    removal)
- Nothing is written to the local store without explicit approval.
  Declining a candidate leaves the store untouched; running `sync
  pull` again still offers it (or reflects it as resolved, if the
  calendar changed again since).
- `list`/`show` are unchanged - they keep reading the local store
  only. `sync pull` is the only thing that reads calendar data back
  into the store, and only when the user explicitly runs it.
- The existing push-only behavior (`log`, `import`, `update`,
  `sync refresh`, `sync retry`) is entirely unchanged - `movie-planner`
  itself still never reads the calendar back on its own account. This
  is additive, not a reversal of `calendar-sync`'s own push-only
  contract.

## Capabilities

### New Capabilities

- `calendar-sync-pull`: reads calendar events back, diffs them against
  the local store by `caldav_uid`, and applies only user-approved
  changes to it. Kept separate from the existing `calendar-sync`
  capability, whose own push-only contract is unchanged.

### Modified Capabilities

(none - `calendar-sync`'s existing push-only requirements are
unaffected)

## Impact

- New CLI command (`sync pull`) alongside the existing `sync
  refresh`/`sync retry`.
- New code to map a raw VEVENT back to `Entry` fields - the reverse of
  `build_vevent`/`build_description`/`_extra_properties`
  (`calendar_sync.py`): `LOCATION` back to a venue name, custom `X-*`
  properties back to title/director/genre/etc., `DTSTART`/`DTEND` back
  to date/start_time/end_time. Design decisions on ambiguous cases
  (an event with none of movie-planner's own `X-*` properties at all -
  created purely by web, never had OMDb data) belong in `design.md`,
  not here.
- `CalendarClient`/`_CalDAVCalendar` protocol needs a real "list all
  events" capability - `events()` already exists on the protocol but
  is currently only used for `check_connection`; this change is the
  first thing to actually read its return value.
- No changes to the local SQLite schema - reconciliation writes
  through the existing `Store.create_entry`/`update_entry`/
  `delete_entry` methods.
