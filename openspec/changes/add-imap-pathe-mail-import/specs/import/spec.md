## ADDED Requirements

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

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: A row can supply `booking_ref`
**Reason**: `booking_ref` is a Pathé-specific reconciliation key, used
only by the `from-pathe-email` command to match a re-sent confirmation
to an already-logged entry (see `pathe-email-import`'s "Match an
existing entry by booking number"). Accepting it on a generic
CSV/JSON row coupled the vendor-agnostic import contract to one email
source's bookkeeping, with no equivalent reconciliation behavior on
this path - a supplied `booking_ref` was stored but never looked up
or matched against.
**Migration**: A row supplying `booking_ref` still imports successfully;
the field is silently ignored rather than stored. Reconciling a
Pathé-sourced re-import against an already-logged entry now only
happens through `movie-planner from-pathe-email` directly, which is
unaffected by this change.
