## 1. Schema (already done in the working tree)

- [x] 1.1 Add `street_address`/`postal_code` to `VenueLocation`
      (venue_locations.py)
- [x] 1.2 Add `street_address`/`postal_code` to `Venue` (store.py) and
      `_MIGRATED_VENUE_COLUMNS`
- [x] 1.3 Thread `street_address`/`postal_code` through `add_venue` and
      `_backfill_known_venue_locations` (COALESCE fill, same as every
      other column in that loop)

## 2. LOCATION and X-\* properties

- [x] 2.1 Write a failing test: pushing an entry at a venue with a known
      street address and postal code produces a LOCATION string
      including both, then update `_venue_location()` (cli.py) to make it
      pass
- [x] 2.2 Write a failing test: a venue with only one of street
      address/postal code known falls back to the shorter
      "venue, city, country" LOCATION shape, then confirm it passes
- [x] 2.3 Write a failing test: pushing an entry at a venue with a known
      street address and postal code sets `X-STREET-ADDRESS` and
      `X-POSTAL-CODE` on the VEVENT, then update `_extra_properties()`
      (calendar_sync.py) to make it pass
- [x] 2.4 Write a failing test: each of `X-STREET-ADDRESS`/
      `X-POSTAL-CODE` is omitted independently when its own value isn't
      known (not an all-or-nothing pair), then confirm it passes

## 3. Backfill real venue data

- [x] 3.1 Add verified `street_address`/`postal_code` to as many of the
      14 existing `KNOWN_VENUE_LOCATIONS` `_add()` calls as an official
      source confirms, cross-checked against each venue's existing GPS
      coordinates - leave any unconfirmed venue without one, verified by
      re-running the full test suite (`uv run pytest -q`). 13 of 14 fully
      confirmed; GSC Gurney Plaza's unit address confirmed via GSC's own
      site, postal code left unset (no source confirms one).

## 4. Docs

- [x] 4.1 Update `docs/calendar-schema.md` with the extended LOCATION
      shape and the two new `X-*` properties, verified by the docs lint
      suite (prettier/markdownlint/vale/ltex)
- [x] 4.2 Update `README.md`'s venue-location paragraph to mention the
      street-address extension and that it backfills automatically on
      the next store open, verified by the same docs lint suite

## 5. Verification

- [x] 5.1 Full local check suite green: `uv run pytest -q`,
      `uv run ruff check .`/`ruff format --check .`, `uv run mypy .`,
      `uv run bandit -r src/movie_planner`
- [x] 5.2 Mutation spot-check on the LOCATION-composition pairing rule
      (task 2.2), confirming a deliberately introduced bug is caught by
      the test suite

## 6. Ship

- [ ] 6.1 Commit, push, PR opened against #283, CI green
- [ ] 6.2 Issue #283 closed via the merged PR
- [ ] 6.3 movie-planner-web notified once merged
