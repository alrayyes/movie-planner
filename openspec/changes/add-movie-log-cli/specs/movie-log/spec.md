## Purpose

Lets the user record, list, update, and delete their own log of watched
movies, held locally as the source of truth for everything else in the
system.

## ADDED Requirements

### Requirement: Log a watched movie interactively
The system SHALL prompt for title, date, optional start time, optional
end time, medium, and — when medium is a physical place — venue, and
SHALL persist the entry to the local store.

#### Scenario: Logging with a full time range
- **WHEN** the user runs the log command and provides title, date, start
  time, end time, medium "cinema", and venue "Tuschinski"
- **THEN** a new entry is persisted with all provided fields

#### Scenario: Logging with unknown times
- **WHEN** the user runs the log command and leaves both start and end
  time blank
- **THEN** a new entry is persisted with a date and no start or end time

#### Scenario: Venue not asked for non-physical medium
- **WHEN** the user selects medium "netflix"
- **THEN** the system does not prompt for a venue

### Requirement: User-editable medium and venue lists
The system SHALL let the user add, list, and remove values from the
medium list and the venue list, and SHALL offer only currently-defined
values, plus an option to add a new one, when prompting.

#### Scenario: Adding a new venue
- **WHEN** the user adds venue "Pathe Noord" via the locations command
- **THEN** "Pathe Noord" appears as a selectable venue on subsequent log
  entries

#### Scenario: Removing a medium in use
- **WHEN** the user attempts to remove a medium that existing entries
  reference
- **THEN** the system rejects the removal and explains which entries
  reference it

### Requirement: List logged entries
The system SHALL let the user list logged entries showing title, date,
medium, and venue, optionally filtered by date range or medium.

#### Scenario: Listing all entries
- **WHEN** the user runs the list command with no filters
- **THEN** every logged entry is shown, ordered by date

### Requirement: Update a logged entry
The system SHALL let the user update the title, date, start/end time,
medium, or venue of an existing entry by identifying it, and SHALL apply
the same medium/venue rules used for initial logging.

#### Scenario: Correcting a wrong date
- **WHEN** the user updates an existing entry's date
- **THEN** the stored entry reflects the new date

### Requirement: Delete a logged entry
The system SHALL let the user delete an existing entry by identifying
it, removing it from the local store.

#### Scenario: Deleting an entry
- **WHEN** the user deletes an existing entry
- **THEN** the entry no longer appears in the list command output
