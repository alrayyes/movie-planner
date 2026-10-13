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
- `Store._backfill_known_venue_locations()` - the existing, automatic
  COALESCE backfill that already runs on every store open to catch up
  chain/city/country/coordinates on a `venues` row created before the
  hardcoded table had them - extended to cover `street_address`/
  `postal_code` the same way. No new command needed: this mechanism
  already exists (added for #170's coordinates), it just needs the two
  new columns added to what it fills in. This is what actually gets the
  new fields onto Ryan's real database - his venue rows for most of
  these 14 groups already exist, created before this change.
- `docs/calendar-schema.md` documents the two new properties and the
  extended LOCATION shape.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `calendar-sync`: the existing "Venue location on the pushed event"
  requirement gains a fuller LOCATION shape, two new independently-set
  `X-*` properties for a venue with verified street-level data, and
  extends the existing automatic venue-row backfill to the two new
  fields.

## Impact

- `src/movie_planner/store.py` - `Venue` dataclass, `_MIGRATED_VENUE_COLUMNS`,
  `add_venue`, `_backfill_known_venue_locations()`.
- `src/movie_planner/venue_locations.py` - `VenueLocation` dataclass, `_add()`,
  and the 14 existing venue-group calls.
- `src/movie_planner/cli.py` - `_venue_location()`.
- `src/movie_planner/calendar_sync.py` - `_extra_properties()`.
- `docs/calendar-schema.md`.
- No breaking change: every new field is optional and additive: an entry at a
  venue with no street-level data behaves exactly as it does today.
