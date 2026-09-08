## Why

LOCATION currently only ever carries "venue name, city, country" for a
recognized venue - close enough to geocode to the right neighborhood, but not
the right building. A full street address lets a calendar client (Google
Calendar, Apple Calendar) resolve LOCATION to the actual venue when tapped.
Cross-repo coordinated with movie-planner-web: city/country got dedicated
`X-CITY`/`X-COUNTRY` properties (issue #217) precisely because LOCATION is
fragile for anything reading the value back structured rather than just
displaying it - the same reasoning applies here, so this ships a street
address alongside dedicated `X-STREET-ADDRESS`/`X-POSTAL-CODE` properties,
not LOCATION alone.

## What Changes

- `Venue` (store.py) and `VenueLocation` (venue_locations.py) gain
  `street_address`/`postal_code` fields, following the same "verified
  against a real source, never guessed" rule already governing
  chain/city/country/coordinates in `KNOWN_VENUE_LOCATIONS`.
- `_venue_location()` (cli.py) composes a fuller LOCATION string
  (`"{venue}, {street address}, {postal code} {city}, {country}"`) when
  street address and postal code are both known, falling back to today's
  shorter shape otherwise.
- `_extra_properties()` (calendar_sync.py) writes `X-STREET-ADDRESS` and
  `X-POSTAL-CODE` as independent fields - split, not one combined
  `X-ADDRESS` - each omitted independently when its own value isn't known,
  same "omit, never guess" rule as every other `X-*` property here.
- `KNOWN_VENUE_LOCATIONS`'s existing 14 venue groups backfilled with real,
  verified street addresses/postal codes wherever an official source
  confirms one - any that can't be confirmed stay without one.
- New `movie-planner locations venues refresh` command
  (dry-run by default, `--apply` to write) backfills an *already
  existing* venue row's chain/city/country/coordinates/street address/
  postal code from the current table - needed because a `Venue` row only
  ever copies the table's data once, at creation time, and Ryan's real
  database already has rows for most of these 14 venues from before this
  change. Without it, the new fields would never reach his real calendar.
- `docs/calendar-schema.md` documents the two new properties and the
  extended LOCATION shape.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `calendar-sync`: the existing "Venue location on the pushed event"
  requirement gains a fuller LOCATION shape and two new independently-set
  `X-*` properties for a venue with verified street-level data.
- `movie-log`: the existing "User-editable medium and venue lists"
  requirement gains a new `locations venues refresh` command that
  backfills an already-existing venue row's chain/city/country/
  coordinates/street address/postal code from the current hardcoded
  table - needed because that table only ever gets consulted once, when
  a venue row is first created.

## Impact

- `src/movie_planner/store.py` - `Venue` dataclass, `_MIGRATED_VENUE_COLUMNS`,
  new `refresh_venue_locations()` method.
- `src/movie_planner/venue_locations.py` - `VenueLocation` dataclass, `_add()`,
  and the 14 existing venue-group calls.
- `src/movie_planner/cli.py` - `_venue_location()`, new `locations venues
  refresh` command.
- `src/movie_planner/calendar_sync.py` - `_extra_properties()`.
- `docs/calendar-schema.md`, `README.md`.
- No breaking change: every new field is optional and additive: an entry at a
  venue with no street-level data behaves exactly as it does today.
