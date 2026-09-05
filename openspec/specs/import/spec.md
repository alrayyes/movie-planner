## Purpose

Brings existing viewing history into the local store in bulk from CSV
or JSON.

## Requirements

### Requirement: Import from CSV
The system SHALL import viewing entries from a CSV file with columns
for title, date, start time, end time, medium, and venue, applying the
same validation and duplicate-detection rules as interactive logging.

#### Scenario: Valid CSV import
- **WHEN** the user imports a CSV file with valid rows
- **THEN** each row is persisted as a movie-log entry and synced to the
  calendar

### Requirement: Import from JSON
The system SHALL import viewing entries from a JSON file structured as
a list of objects with the same fields as CSV import, applying the same
validation and duplicate-detection rules.

#### Scenario: Valid JSON import
- **WHEN** the user imports a JSON file with valid entries
- **THEN** each entry is persisted as a movie-log entry and synced to
  the calendar

### Requirement: Import summary
The system SHALL report, after each import run, how many rows were
imported, how many were skipped as likely duplicates, and how many
failed validation, without stopping the entire import on a single row's
failure.

#### Scenario: Partial failure
- **WHEN** a bulk import contains one row that fails validation
- **THEN** the remaining valid rows are imported, and the failing row
  is reported in the summary

### Requirement: Metadata fetch can be skipped
The system SHALL accept a `--no-metadata` option that skips the OMDb
lookup for every imported row, so a large historical import doesn't
have to fetch ratings within a single run - the calendar push still
happens. Ratings can be backfilled afterward via the calendar-sync
refresh operation.

#### Scenario: Importing with --no-metadata
- **WHEN** the user imports a file with `--no-metadata`
- **THEN** every row is persisted and pushed to the calendar with no
  OMDb lookup
