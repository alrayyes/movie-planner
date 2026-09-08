## MODIFIED Requirements

### Requirement: Venue location on the pushed event
When a venue has a known city and country (from the hardcoded
chain/location table), the system SHALL set the pushed VEVENT's
LOCATION to "venue name, city, country" instead of just the venue
name, and SHALL include the venue's chain, when known, as a line in the
description. When the venue additionally has a known street address and
postal code, the system SHALL extend LOCATION to "venue name, street
address, postal code city, country" instead, and SHALL set the pushed
VEVENT's `X-STREET-ADDRESS` and `X-POSTAL-CODE` properties. Each of
street address and postal code is set independently: a venue with only
one of the two SHALL have only that property set, and LOCATION SHALL
still use the shorter "venue name, city, country" shape unless both are
known. An already-existing venue row whose street address/postal code
weren't known when it was created SHALL pick them up automatically the
next time the store is opened, once the hardcoded table has verified
data for it - the same automatic backfill chain/city/country/
coordinates already get, never overwriting a value the row already
has.

#### Scenario: Pushing an entry at a venue with a known location
- **WHEN** an entry at a venue with a known chain, city, and country is
  pushed
- **THEN** the pushed VEVENT's LOCATION includes the city and country,
  and its description includes the chain

#### Scenario: Pushing an entry at a venue with no known location
- **WHEN** an entry at a venue not in the hardcoded table is pushed
- **THEN** the pushed VEVENT's LOCATION is just the venue name, and the
  description has no chain line

#### Scenario: Pushing an entry at a venue with a known street address
- **WHEN** an entry at a venue with a known street address and postal
  code (in addition to city and country) is pushed
- **THEN** the pushed VEVENT's LOCATION includes the street address and
  postal code, and the VEVENT carries both `X-STREET-ADDRESS` and
  `X-POSTAL-CODE` properties

#### Scenario: Pushing an entry at a venue with only a street address known
- **WHEN** an entry at a venue with a known street address but no known
  postal code is pushed
- **THEN** the VEVENT carries `X-STREET-ADDRESS` but not `X-POSTAL-CODE`,
  and LOCATION uses the shorter "venue name, city, country" shape

#### Scenario: Pushing an entry at a venue with no street-level data
- **WHEN** an entry at a venue with a known city and country but no
  known street address or postal code is pushed
- **THEN** the VEVENT carries neither `X-STREET-ADDRESS` nor
  `X-POSTAL-CODE`, and LOCATION uses the shorter "venue name, city,
  country" shape

#### Scenario: An existing venue row picks up a newly-verified street address
- **WHEN** the store is opened and an existing venue row's name matches
  a hardcoded table entry that now has a street address/postal code the
  row doesn't
- **THEN** the row is updated with those values, and a subsequent push
  for an entry at that venue includes them

#### Scenario: Backfill never overwrites a value a venue row already has
- **WHEN** the store is opened and an existing venue row already has its
  own value for a field the hardcoded table also has a value for
- **THEN** the row's existing value is left unchanged
