# calendar-sync-pull Specification

## Purpose
Reconciles changes made directly on the calendar (by movie-planner-web
or by hand) back into the local movie-log store, with every change
reviewed and explicitly approved before it's written - closing the gap
left by the calendar's push-only sync, without making it a two-way
sync.

## Requirements

### Requirement: Detect a calendar event with no matching local entry
When `sync pull` runs, the system SHALL identify every calendar event
whose UID does not match any local entry's `caldav_uid` and SHALL
present it as a candidate new entry.

#### Scenario: A web-created entry has no local counterpart
- **WHEN** `sync pull` runs and a calendar event's UID matches no
  local entry's `caldav_uid`
- **THEN** that event is presented as a candidate new entry, with its
  title, date/time, and venue shown for review

### Requirement: Detect a local entry whose linked event changed
When `sync pull` runs, for each local entry with a `caldav_uid`, the
system SHALL compare its linked calendar event's structured fields
(title, date, start time, end time, venue, director, actors, genre,
release year, poster URL, row, seat) against the stored entry and
SHALL present a candidate change for each entry where at least one of
these fields differs. Fields derived from the calendar event's free-text
description (ratings, Letterboxd, chain, notes) SHALL NOT be compared.

#### Scenario: A structured field differs
- **WHEN** a local entry's linked calendar event has a different venue
  than the one stored locally
- **THEN** that entry is presented as a candidate change, showing the
  stored value and the calendar's value for the differing field(s)

#### Scenario: Only description-derived content differs
- **WHEN** a local entry's linked calendar event's description text
  differs from what the store would generate, but every structured
  field matches
- **THEN** that entry is not presented as a candidate change

#### Scenario: A structured X-* property is missing from the event
- **WHEN** a local entry has a stored value for a field normally
  carried by a custom `X-*` property (for example row/seat), and the
  linked calendar event no longer has that property at all
- **THEN** that entry is presented as a candidate change showing the
  field going from its stored value to "unknown" - not phrased as a
  confirmed deletion, since a missing property does not by itself mean
  a deliberate removal

### Requirement: Detect a local entry whose linked event was removed
When `sync pull` runs, for each local entry with a `caldav_uid`, the
system SHALL detect when no calendar event exists with that UID and
SHALL present a candidate removal.

#### Scenario: An entry's linked event no longer exists
- **WHEN** a local entry's `caldav_uid` matches no event currently on
  the calendar
- **THEN** that entry is presented as a candidate removal

### Requirement: Every candidate change requires explicit approval
The system SHALL NOT write a candidate new entry, change, or removal
to the local store without the user explicitly approving that specific
candidate. Candidates SHALL be presented one at a time.

#### Scenario: User approves a candidate
- **WHEN** the user is shown a candidate and confirms it
- **THEN** the corresponding change (create, update, or delete) is
  written to the local store

#### Scenario: User declines a candidate
- **WHEN** the user is shown a candidate and declines it
- **THEN** the local store is left unchanged for that candidate, and
  nothing is recorded that would suppress it from being offered again

#### Scenario: A later sync pull re-evaluates a declined candidate
- **WHEN** `sync pull` runs again after an earlier candidate was
  declined and the calendar has not changed further for that entry
- **THEN** the same candidate is presented again

### Requirement: Venue name resolution from a calendar event
When resolving a candidate's venue, the system SHALL strip a trailing
`", <city>, <country>"` from the event's LOCATION only when both parts
exactly match the event's own `X-CITY`/`X-COUNTRY` properties. The
system SHALL use the LOCATION value as-is when there is no such exact
match, or when `X-CITY`/`X-COUNTRY` are absent. The resolved name SHALL
be looked up the same way `log`/`import` already resolve a venue name,
including alias resolution to a canonical venue.

#### Scenario: LOCATION matches its own X-CITY/X-COUNTRY
- **WHEN** an event's LOCATION is `"Pathé De Munt, Amsterdam,
  Netherlands"` and its X-CITY is `"Amsterdam"` and X-COUNTRY is
  `"Netherlands"`
- **THEN** the resolved venue name is `"Pathé De Munt"`

#### Scenario: LOCATION does not match X-CITY/X-COUNTRY
- **WHEN** an event's LOCATION does not end in a string exactly
  matching its own X-CITY/X-COUNTRY values (or has neither property)
- **THEN** the resolved venue name is the LOCATION value unchanged
