## ADDED Requirements

### Requirement: Fetch metadata during bulk import
The system SHALL fetch OMDb ratings for each row imported via bulk
CSV/JSON import, the same as interactive logging does, unless explicitly
skipped.

#### Scenario: Imported row gets ratings
- **WHEN** a CSV or JSON row is imported and OMDb returns a match for its
  title
- **THEN** the resulting entry is stored with OMDb ratings

### Requirement: Refresh backfills missing ratings only
During refresh, the system SHALL fetch OMDb ratings only for entries that
do not already have them, and SHALL NOT re-fetch ratings for an entry
that already has them.

#### Scenario: Entry already has ratings
- **WHEN** refresh runs against an entry that already has OMDb ratings
  stored
- **THEN** no OMDb lookup is made for that entry

#### Scenario: Entry is missing ratings
- **WHEN** refresh runs against an entry with no OMDb ratings stored
- **THEN** an OMDb lookup is made for that entry and any match is stored
