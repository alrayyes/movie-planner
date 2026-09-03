## ADDED Requirements

### Requirement: Include metadata in the event description
When pushing a VEVENT, whether creating or updating it, the system SHALL
set its description from the entry's available ratings and Letterboxd
link/rating, and, when the entry came from a Pathé booking confirmation,
the screening format and seat. An entry with no such data SHALL still be
pushed, with no description set.

#### Scenario: Entry with ratings and a Letterboxd link
- **WHEN** an entry with IMDb, Rotten Tomatoes, and Metacritic ratings and
  a Letterboxd link is pushed
- **THEN** the pushed VEVENT's description includes all of them

#### Scenario: Entry with no metadata
- **WHEN** an entry with no ratings, Letterboxd data, or screening details
  is pushed
- **THEN** the pushed VEVENT has no description

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
