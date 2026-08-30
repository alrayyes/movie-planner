## Purpose

Keeps a Baikal CalDAV calendar as a push-only, synced view of the local
movie log, so the calendar always reflects the log without ever being a
place edits originate from.

## Requirements

### Requirement: Push a new entry to the calendar
When a movie-log entry is created, the system SHALL create a
corresponding VEVENT on the configured Baikal calendar and SHALL record
the resulting CalDAV UID against the local entry.

#### Scenario: New entry creates a calendar event
- **WHEN** a movie-log entry is logged successfully
- **THEN** a VEVENT is created on the configured calendar with the
  entry's title, date/time, and venue, and its UID is stored locally

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
