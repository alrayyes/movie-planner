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

### Requirement: A row can supply OMDb-derived fields directly
The system SHALL accept a CSV/JSON row that already carries any of the
OMDb-derived fields (ratings, poster URL, director, actors, genre,
release year), matching the `metadata` spec's own field names, and
SHALL store them as given rather than only ever fetching them from
OMDb. The system SHALL NOT make an OMDb lookup for a row supplying
every one of those fields already. `letterboxd_url` and
`letterboxd_rating` are accepted directly on a row the same way.

#### Scenario: Row supplies every OMDb-derived field
- **WHEN** a row is imported that already carries every OMDb-derived
  field
- **THEN** the entry is stored with those values and no OMDb lookup is
  made for that row

#### Scenario: Row supplies some but not all OMDb-derived fields
- **WHEN** a row is imported that carries only some OMDb-derived
  fields
- **THEN** the supplied fields are stored, and the existing OMDb-fetch
  behavior still runs for the row (skipped by `--no-metadata`, same as
  any other row)

### Requirement: A row can supply an opaque source label
The system SHALL accept an optional `source` field on a CSV/JSON row and
SHALL store it as given, without interpreting, validating, or acting on
its value. This is a plain provenance label (for example, a mail-import
tool tagging a row with the sender domain it came from), not a field
movie-planner attaches meaning to.

#### Scenario: Row supplies a source label
- **WHEN** a row is imported with a `source` value
- **THEN** the entry is stored with that value, unchanged

#### Scenario: Row supplies no source label
- **WHEN** a row is imported with no `source` field
- **THEN** the entry is stored with no source value, and nothing else
  about the import is affected

### Requirement: Accept import data piped on stdin, not only a file
The system SHALL accept `import` with no file path argument, reading
JSON from stdin instead - either a JSON array (the existing
`movies.json` shape) or a single bare JSON object (one row, for a
caller that doesn't want to construct an array just to import one
row). CSV via stdin is out of scope; a piped input is always parsed as
JSON.

#### Scenario: Piping a single row
- **WHEN** `import` is run with no path argument and a single JSON
  object (not wrapped in an array) is piped to it
- **THEN** that one row is imported, the same as if it were the only
  element of a `movies.json` array

#### Scenario: Piping an array of rows
- **WHEN** `import` is run with no path argument and a JSON array is
  piped to it
- **THEN** it's imported the same way a `movies.json` file would be

#### Scenario: A file path is still given
- **WHEN** `import` is run with a file path argument
- **THEN** behavior is unchanged - stdin is not read at all
