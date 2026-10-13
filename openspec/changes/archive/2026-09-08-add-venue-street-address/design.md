## Context

See `proposal.md` - Why for motivation. Relevant current state:

- `KNOWN_VENUE_LOCATIONS` (`venue_locations.py`) is the single hardcoded
  source of verified chain/city/country/coordinate data, keyed by venue
  name (including aliases, resolved to a canonical name via `_add()`).
- `Store.add_venue` copies chain/city/country/latitude/longitude from
  that table into the `venues` table at row-creation time.
  `_venue_location`/`_venue_geo` (`cli.py`) both read the stored `Venue`
  fields, not a live lookup.
- **`Store._backfill_known_venue_locations()` already exists** and runs
  automatically on every `Store()` open (from `_migrate()`), after the
  `_MIGRATED_VENUE_COLUMNS` ALTERs. For every venue whose name matches
  a `KNOWN_VENUE_LOCATIONS` entry, it `UPDATE`s each column with
  `COALESCE(column, ?)` - fills the column only if it's still `NULL`,
  one column at a time, never overwrites a value already set. Added for
  issue #185, specifically so a database that already ran an earlier,
  narrower migration (chain/city/country from #111) still picks up a
  later one (coordinates from #170) without a single
  all-columns-must-be-NULL gate skipping it. This already solves the
  exact problem this change would otherwise need a new command for:
  Ryan's real database has venue rows for most of the 14 groups today,
  created before this change - the next time he opens the store (any
  command), this mechanism fills in the two new columns automatically.

## Goals / Non-Goals

**Goals**: street address reaches `LOCATION` and the new `X-*`
properties for a venue with verified data, including venues that
already exist in a real database today.

**Non-goals**: dynamic/live geocoding of a venue's address (still
hardcoded/verified-only, same as every other field in the table); a new
CLI command for backfilling existing rows - `_backfill_known_venue_locations`
already does this and just needs the two new columns added to what it
fills in.

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

**No new command - extend the existing `_backfill_known_venue_locations`
COALESCE loop to the two new columns.** Simpler than a separate
`locations venues refresh` command (the originally-considered
approach): backfilling already happens automatically, for free, on the
very next `Store()` open after upgrading - nothing for Ryan to
remember to run. `COALESCE`'s fill-only semantics (vs. an unconditional
overwrite) is also the right behavior here, not just the existing
one: it's what already correctly handles the partial-migration case
(#185), and there's no reason street_address/postal_code needs a
different, stronger "always overwrite" rule than every other column in
that same loop already uses.

**Street address/postal code sourced the same way as every other
verified field in the table** - each venue's chain/city/country/
coordinates was confirmed against an official source (Pathé's own
listings, GSC's, Nominatim for coordinates); street address/postal code
follow the identical rule, researched from each venue's own official
site or an equivalent authoritative source, and left unset (not
guessed) for anything not confidently confirmed.

## Risks / Trade-offs

- **A venue row created between this shipping and the next `Store()`
  open still needs that next open to pick up the columns.** Not
  actually a risk in practice: `_backfill_known_venue_locations` runs
  on *every* open, including the very next command Ryan runs after
  upgrading - there's no separate step to remember, unlike the
  originally-considered `refresh --apply` command.
- **A venue whose name doesn't exactly match a `KNOWN_VENUE_LOCATIONS`
  key (an alias not yet merged) isn't backfilled.** Pre-existing
  behavior, unchanged by this change - `merge-aliases --apply` (issue
  #196) is what resolves that, same as it already does for
  chain/city/country/coordinates today.

## Migration Plan

1. Ship the schema (new `Venue` columns via `_MIGRATED_VENUE_COLUMNS`,
   new `VenueLocation` fields, `_backfill_known_venue_locations`
   extended to the two new columns), and the `_venue_location`/
   `_extra_properties` changes.
2. The next time anyone with an existing database runs any
   `movie-planner` command, `Store.__init__` backfills
   `street_address`/`postal_code` onto existing venue rows
   automatically - no explicit step required.
3. `sync refresh --force` (documented already, same as every prior
   LOCATION-affecting change) re-pushes every entry so the calendar
   reflects the refreshed venue data.

No rollback concern: every new field is optional and additive, and the
backfill only ever fills a `NULL` column.

## Open Questions

None - the address-data sourcing itself (which of the 14 venues get a
confirmed street address vs. staying without one) is being researched
now and will land as part of implementation, not a spec/design
question.
