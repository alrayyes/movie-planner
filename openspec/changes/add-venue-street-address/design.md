## Context

See `proposal.md` - Why for motivation. Relevant current state:

- `KNOWN_VENUE_LOCATIONS` (`venue_locations.py`) is the single hardcoded
  source of verified chain/city/country/coordinate data, keyed by venue
  name (including aliases, resolved to a canonical name via `_add()`).
- `Store.add_venue`/`get_or_create_venue` copy chain/city/country/
  latitude/longitude from that table into the `venues` table **once, at
  row-creation time** - a `Venue` row never re-reads the table again
  after that. `_venue_location`/`_venue_geo` (`cli.py`) both read the
  stored `Venue` fields, not a live lookup.
- Ryan's real database already has venue rows for most/all of the 14
  groups in the table today, created long before this change. This
  matters: it means simply adding `street_address`/`postal_code` to
  `KNOWN_VENUE_LOCATIONS` does **not** make them reach his real calendar
  - his existing `Venue` rows have no mechanism to pick up a field added
  to the table after they were created. This gap already exists today
  for chain/city/country/coordinates too (undocumented until now), but
  this change is the first time it actually blocks the feature it ships
  from working for the motivating real-world case.

## Goals / Non-Goals

**Goals**: street address reaches `LOCATION` and the new `X-*`
properties for a venue with verified data, including venues that
already exist in a real database today.

**Non-goals**: dynamic/live geocoding of a venue's address (still
hardcoded/verified-only, same as every other field in the table);
changing `_venue_location`/`_venue_geo` to read `KNOWN_VENUE_LOCATIONS`
live instead of the stored `Venue` row (a bigger behavior change for
every existing field, not just the two this change adds - out of
scope); a generic "any field, any table" migration framework (this adds
one command scoped to the fields `KNOWN_VENUE_LOCATIONS` actually has).

## Decisions

**Split `X-STREET-ADDRESS`/`X-POSTAL-CODE`, not combined `X-ADDRESS`.**
Agreed jointly with movie-planner-web. `LOCATION`'s own display string
already needs address-composition logic (joining name + street + postal
code + city + country); a combined `X-*` property would need a second,
different composed format (unclear ordering - postal-code-before-city
is Dutch convention, not universal; some countries have no postal code
at all). Split reuses `X-CITY`/`X-COUNTRY`'s exact existing pattern in
`_extra_properties` - a direct 1:1 field passthrough, no joining logic
on the `X-*` side at all.

**LOCATION includes the street address only when both street address
and postal code are known; the two `X-*` properties are still set
independently.** Mirrors the existing asymmetry between `LOCATION`
(requires city *and* country together) and `X-CITY`/`X-COUNTRY`
(each set independently) - `_venue_location` already treats
city/country as a pair for `LOCATION`'s purposes while writing them to
`X-*` unconditionally. A `LOCATION` with a street name but no postal
code (or vice versa) is a worse geocoding hint than the plain
"venue, city, country" it would otherwise fall back to; each `X-*`
property is still exposed independently either way, so nothing is lost
by holding `LOCATION` to the stricter pairing.

**A new `Store.refresh_venue_locations()` method + `movie-planner
locations venues refresh` command backfills existing venue
rows from the current `KNOWN_VENUE_LOCATIONS` table.** For every venue
row whose name matches a table entry, sets
chain/city/country/latitude/longitude/street_address/postal_code to the
table's current values, unconditionally - a full resync, not a
fill-only-if-missing merge. This is safe because these six fields have
exactly one writer: `add_venue` copying them from this same table at
creation time. Nothing else ever sets them (there's no `--chain`/
`--city`/etc. flag on `venues add`), so a row's value can only ever be
"what the table said when the row was created" - there's no legitimate
case of a row holding a value that deliberately diverges from the
table, only a stale one. A venue row whose name isn't in the table at
all is left completely untouched either way. Dry-run by default,
`--apply` to write - mirrors `merge-aliases`'s existing UX exactly,
since it's the same kind of "the hardcoded table now knows more than an
existing row does" problem, just for "already correctly named" rows
rather than aliases. Considered folding this into `merge-aliases`
itself, rejected: that command's contract is specifically about alias
collapsing (moving entries between rows); this is about refreshing a
row's own columns in place - different operation, same UX shape, worth
keeping separate so each command's name says what it actually does.

**Street address/postal code sourced the same way as every other
verified field in the table** - each venue's chain/city/country/
coordinates was confirmed against an official source (Pathé's own
listings, GSC's, Nominatim for coordinates); street address/postal code
follow the identical rule, researched from each venue's own official
site or an equivalent authoritative source, and left unset (not
guessed) for anything not confidently confirmed.

## Risks / Trade-offs

- **A venue row created between this shipping and someone running
  `refresh --apply` still shows the old, shorter LOCATION.**
  Mitigation: same as every other backfill in this codebase (GEO,
  #196's alias merge) - documented as a one-time step in the README,
  not automatic. `sync refresh` alone doesn't fix a `Venue` row's own
  stale columns; `refresh --apply` does that, and `sync
  refresh` (or `--force`) is still what re-pushes the calendar events
  once the row itself is current.
- **A venue whose name doesn't exactly match a `KNOWN_VENUE_LOCATIONS`
  key (an alias not yet merged) won't be refreshed by the new command.**
  Mitigation: none needed beyond documenting the order - run
  `merge-aliases --apply` first if it hasn't already been run, then
  `refresh --apply`, same two-step shape the "Known gaps"
  note in `docs/architecture.md` already describes for the alias case.

## Migration Plan

1. Ship the schema (new `Venue` columns via `_MIGRATED_VENUE_COLUMNS`,
   new `VenueLocation` fields), `_venue_location`/`_extra_properties`
   changes, and `refresh`.
2. Anyone with an existing database runs `locations venues
   refresh --apply` once to backfill existing venue rows'
   `street_address`/`postal_code` (and refresh chain/city/country/
   coordinates too, in case those ever drift from the table - no reason
   to scope this narrower than "resync everything the table knows").
3. `sync refresh --force` (documented already, same as every prior
   LOCATION-affecting change) re-pushes every entry so the calendar
   reflects the refreshed venue data.

No rollback concern: every new field is optional and additive, and
`refresh` without `--apply` only reports what it would
change.

## Open Questions

None - the address-data sourcing itself (which of the 14 venues get a
confirmed street address vs. staying without one) is being researched
now and will land as part of implementation, not a spec/design
question.
