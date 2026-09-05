## Purpose

Enriches a logged movie with ratings and links from IMDb, Rotten
Tomatoes, Metacritic, and Letterboxd — fetching what can be automated
and accepting what can't.

## Requirements

### Requirement: Fetch ratings via OMDb
The system SHALL fetch IMDb, Rotten Tomatoes, and Metacritic ratings,
and a poster URL, for a movie from OMDb given a title or IMDb ID, and
SHALL store all of it against the entry. Unlike ratings, the poster
URL is pushed to the calendar as a custom `X-POSTER-URL` property, not
in the description - see `calendar-sync`'s spec.

#### Scenario: Successful fetch by title
- **WHEN** the user logs a movie and OMDb returns a match for its title
- **THEN** the entry is stored with IMDb, Rotten Tomatoes, and
  Metacritic ratings from that match, and its poster URL if OMDb
  returned one

#### Scenario: No OMDb match
- **WHEN** OMDb returns no match for the given title
- **THEN** the entry is stored without ratings, and the user is told no
  match was found

### Requirement: Watched-year hint disambiguates a title search
When looking up by title (not IMDb ID) for an entry with a known
watched date, the system SHALL first try OMDb's title search scoped to
that watched year, and SHALL fall back to a plain title-only search
when the year-scoped search finds nothing - the watched year is a
disambiguation hint, not a strict filter, since a re-watch of an older
film has a watched year that's never the release year.

#### Scenario: Year-scoped search finds a match
- **WHEN** a title search scoped to the entry's watched year finds a
  match
- **THEN** that match is used, with no further OMDb call

#### Scenario: Year-scoped search finds nothing
- **WHEN** a title search scoped to the entry's watched year finds no
  match
- **THEN** the system falls back to a plain title-only search instead
  of reporting no match

### Requirement: Manual Letterboxd link/rating
The system SHALL let the user attach a Letterboxd URL and, optionally,
a rating to an entry, entered by hand rather than fetched.

#### Scenario: Adding a Letterboxd link
- **WHEN** the user provides a Letterboxd URL for an entry
- **THEN** the URL is stored against that entry

### Requirement: Metadata is optional
The system SHALL allow an entry to be logged, updated, and synced to
the calendar with no metadata attached.

#### Scenario: Logging without metadata
- **WHEN** the user skips the metadata step while logging
- **THEN** the entry is still saved and synced to the calendar

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
