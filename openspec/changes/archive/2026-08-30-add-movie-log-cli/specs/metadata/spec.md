## Purpose

Enriches a logged movie with ratings and links from IMDb, Rotten
Tomatoes, Metacritic, and Letterboxd — fetching what can be automated
and accepting what can't.

## ADDED Requirements

### Requirement: Fetch ratings via OMDb
The system SHALL fetch IMDb, Rotten Tomatoes, and Metacritic ratings for
a movie from OMDb given a title or IMDb ID, and SHALL store the returned
ratings against the entry.

#### Scenario: Successful fetch by title
- **WHEN** the user logs a movie and OMDb returns a match for its title
- **THEN** the entry is stored with IMDb, Rotten Tomatoes, and
  Metacritic ratings from that match

#### Scenario: No OMDb match
- **WHEN** OMDb returns no match for the given title
- **THEN** the entry is stored without ratings, and the user is told no
  match was found

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
