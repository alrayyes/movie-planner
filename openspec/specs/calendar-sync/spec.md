## Purpose

Keeps a Baikal CalDAV calendar as a push-only, synced view of the local
movie log, so the calendar always reflects the log without ever being a
place edits originate from.

## Requirements

### Requirement: Push a new entry to the calendar
When a movie-log entry is created, the system SHALL create a
corresponding VEVENT on the configured Baikal calendar and SHALL record
the resulting CalDAV UID against the local entry. The UID SHALL be a
UUIDv7, not v4, so newly-created entries insert in time order rather
than at a random point.

#### Scenario: New entry creates a calendar event
- **WHEN** a movie-log entry is logged successfully
- **THEN** a VEVENT is created on the configured calendar with the
  entry's title, date/time, and venue, and its UID (a UUIDv7) is
  stored locally

### Requirement: Map partial time information to VEVENT fields
The system SHALL create an all-day VEVENT when only a date is known, a
VEVENT with only DTSTART when a start time but no end time is known, and
a VEVENT with both DTSTART and DTEND when both are known.

#### Scenario: Date only
- **WHEN** a logged entry has a date and no start or end time
- **THEN** the pushed VEVENT is an all-day event on that date

#### Scenario: Start time only
- **WHEN** a logged entry has a date and start time but no end time
- **THEN** the pushed VEVENT has DTSTART set and no DTEND

### Requirement: Propagate updates to the linked event
When a movie-log entry is updated, the system SHALL update the linked
VEVENT, identified by its stored UID, to match.

#### Scenario: Updating a synced entry
- **WHEN** the user updates a logged entry that has a linked calendar
  event
- **THEN** the linked VEVENT's fields are updated to match, using the
  same UID

### Requirement: Propagate deletes to the linked event
When a movie-log entry is deleted, the system SHALL delete the linked
VEVENT from the calendar.

#### Scenario: Deleting a synced entry
- **WHEN** the user deletes a logged entry that has a linked calendar
  event
- **THEN** the linked VEVENT is removed from the calendar

### Requirement: Calendar is not a write source
The system SHALL NOT read changes made directly on the calendar back
into the local store; the local store remains authoritative.

#### Scenario: Direct calendar edit is ignored
- **WHEN** a VEVENT is edited directly in the calendar app rather than
  through the CLI
- **THEN** the local entry is unaffected by that edit

### Requirement: Sync failure does not lose the local entry
If pushing to the calendar fails, the system SHALL still persist the
local entry and SHALL report the sync failure to the user for retry.

#### Scenario: Calendar unreachable
- **WHEN** the Baikal server is unreachable while logging a new entry
- **THEN** the entry is saved locally, and the user is told the
  calendar push failed

### Requirement: Include metadata in the event description
When pushing a VEVENT, whether creating or updating it, the system SHALL
set its description from the entry's available ratings, Letterboxd
link/rating, notes, and the venue's chain (when known), and, when the
entry came from a Pathé booking confirmation, the screening format and
seat. An entry with no such data SHALL still be pushed, with no
description set. Unlike screening details, notes are stored on the
entry, so they persist across every subsequent push.

#### Scenario: Entry with ratings and a Letterboxd link
- **WHEN** an entry with IMDb, Rotten Tomatoes, and Metacritic ratings and
  a Letterboxd link is pushed
- **THEN** the pushed VEVENT's description includes all of them

#### Scenario: Entry with no metadata
- **WHEN** an entry with no ratings, Letterboxd data, or screening details
  is pushed
- **THEN** the pushed VEVENT has no description

### Requirement: Venue location on the pushed event
When a venue has a known city and country (from the hardcoded
chain/location table), the system SHALL set the pushed VEVENT's
LOCATION to "venue name, city, country" instead of just the venue
name, and SHALL include the venue's chain, when known, as a line in the
description.

#### Scenario: Pushing an entry at a venue with a known location
- **WHEN** an entry at a venue with a known chain, city, and country is
  pushed
- **THEN** the pushed VEVENT's LOCATION includes the city and country,
  and its description includes the chain

#### Scenario: Pushing an entry at a venue with no known location
- **WHEN** an entry at a venue not in the hardcoded table is pushed
- **THEN** the pushed VEVENT's LOCATION is just the venue name, and the
  description has no chain line

### Requirement: IMDb link is fetched and included automatically
When an OMDb lookup matches, the system SHALL derive `imdb_url` from the
match's IMDb ID and store it, unless the entry already has a manually-set
`imdb_url`, which SHALL never be overwritten. The pushed description's
`IMDb:` line SHALL include this link alongside the rating when both are
present.

#### Scenario: A fresh OMDb match with no existing link
- **WHEN** an entry with no `imdb_url` gets an OMDb match
- **THEN** `imdb_url` is set to `https://www.imdb.com/title/<id>/` and the
  pushed description's `IMDb:` line includes it

#### Scenario: An entry with a manually-set link
- **WHEN** an entry that already has an `imdb_url` gets an OMDb match
- **THEN** the existing `imdb_url` is left unchanged

### Requirement: Poster URL is pushed as a custom property
When an entry has a `poster_url`, the system SHALL include it on the
pushed VEVENT as a custom `X-POSTER-URL` property. An entry with no
poster URL SHALL have no such property on the pushed event.

#### Scenario: Pushing an entry with a poster URL
- **WHEN** an entry with a `poster_url` is pushed
- **THEN** the pushed VEVENT has an `X-POSTER-URL` property set to it

#### Scenario: Pushing an entry with no poster URL
- **WHEN** an entry with no `poster_url` is pushed
- **THEN** the pushed VEVENT has no `X-POSTER-URL` property

### Requirement: Refresh recomputes and re-pushes every entry
The system SHALL provide a refresh operation that, for every logged
entry, fetches OMDb ratings when the entry does not already have them,
then pushes the entry's calendar event — creating it if the entry has
never been synced, updating it otherwise — so its description reflects
current data.

#### Scenario: Refreshing an already-synced entry
- **WHEN** refresh runs against an entry that already has a linked
  calendar event
- **THEN** that event is updated to reflect the entry's current data

#### Scenario: Refreshing a never-synced entry
- **WHEN** refresh runs against an entry with no linked calendar event
- **THEN** a calendar event is created for it, the same as a first sync

### Requirement: Refresh can be scoped to a date range or a single date
The system SHALL accept `--from`/`--to` options to limit a refresh to
entries dated on or after/before the given date, and a `--date` option
to limit it to entries on that exact date. `--date` SHALL be rejected
when combined with either `--from` or `--to`. With no date option, every
entry is refreshed.

#### Scenario: Refreshing a date range
- **WHEN** refresh runs with `--from` and `--to`
- **THEN** only entries dated within that inclusive range are refreshed

#### Scenario: Refreshing a single date
- **WHEN** refresh runs with `--date`
- **THEN** only entries dated on that exact day are refreshed

#### Scenario: Combining --date with --from or --to
- **WHEN** refresh runs with `--date` and either `--from` or `--to`
- **THEN** the command exits with an error instead of refreshing anything

### Requirement: Refresh can force-refetch existing ratings
The system SHALL accept a `--force` option that re-fetches OMDb ratings
for every refreshed entry, including ones that already have a rating -
instead of the default of only fetching for entries still missing one.
`--force` SHALL still respect any date scoping in the same invocation.

#### Scenario: Forcing a re-fetch
- **WHEN** refresh runs with `--force` against entries that already
  have ratings
- **THEN** OMDb is queried again for every one of them

#### Scenario: Forcing a re-fetch within a date range
- **WHEN** refresh runs with `--force` and `--from`/`--to`/`--date`
- **THEN** only entries within that range are re-fetched
