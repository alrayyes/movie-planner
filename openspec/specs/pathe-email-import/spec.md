## Purpose

Turns a Pathé booking confirmation email into a movie-log entry, matching
it against anything already logged so a re-sent confirmation updates the
same entry instead of creating a duplicate.

## Requirements

### Requirement: Parse a Pathé booking confirmation email
The system SHALL accept a Pathé booking confirmation email, either piped
via stdin or given as a file path, and SHALL extract the movie title,
screening date, start time, expected end time, cinema name, and booking
number from it.

#### Scenario: Parsing a piped email
- **WHEN** the user pipes a Pathé booking confirmation email into the
  command
- **THEN** the title, date, start time, expected end time, cinema, and
  booking number are extracted from it

#### Scenario: Unrecognized content
- **WHEN** the piped or given content does not match the expected Pathé
  confirmation format
- **THEN** the command reports that it could not parse the email and does
  not create or update an entry

### Requirement: Confirm parsed data before writing
The system SHALL display the parsed fields to the user and SHALL require
explicit confirmation before creating or updating an entry, reading that
confirmation from the controlling terminal even when the email content
was supplied via stdin.

#### Scenario: User confirms
- **WHEN** the user reviews the parsed fields and confirms
- **THEN** the entry is created or updated as parsed

#### Scenario: User rejects
- **WHEN** the user reviews the parsed fields and declines
- **THEN** no entry is created or updated

### Requirement: Match an existing entry by booking number
The system SHALL look up an existing entry by the parsed booking number
before creating a new one; when a match is found, the parsed email SHALL
be treated as an update to that entry.

#### Scenario: Re-sent confirmation after a time change
- **WHEN** a parsed email's booking number matches an already-logged
  entry, with a different start time than that entry has
- **THEN** the user is shown the existing entry and the new time as a
  proposed update, not a new entry

### Requirement: Fall back to fuzzy duplicate detection
When no existing entry matches the parsed booking number, the system
SHALL apply the same duplicate-detection rules interactive logging uses,
comparing the parsed title and date against existing entries, before
creating a new entry.

#### Scenario: No booking number match, likely duplicate found
- **WHEN** a parsed email's booking number matches no existing entry, and
  its title and date fuzzy-match an existing entry logged the same day
- **THEN** the user is shown that existing entry before a new one is
  created

### Requirement: Store the booking number for future matching
The system SHALL persist the parsed booking number against the created or
updated entry, without requiring booking numbers to be unique across
entries.

#### Scenario: Booking number stored
- **WHEN** an entry is created or updated from a parsed email
- **THEN** the entry's stored booking number matches the one parsed from
  the email

### Requirement: Enrich with OMDb metadata
The system SHALL fetch OMDb ratings for an entry created or updated this
way, the same as interactive logging does, unless explicitly skipped.

#### Scenario: Metadata fetched on a new entry
- **WHEN** a new entry is created from a parsed email
- **THEN** OMDb ratings are fetched and stored against it, if a match is
  found

### Requirement: Sync to the calendar
The system SHALL push a created or updated entry to the calendar the same
way interactive logging and updating do.

#### Scenario: Calendar reflects the parsed booking
- **WHEN** an entry is created or updated from a parsed email
- **THEN** the corresponding calendar event is created or updated to
  match
