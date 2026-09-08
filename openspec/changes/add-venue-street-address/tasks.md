## 1. Schema

- [ ] 1.1 Add `street_address`/`postal_code` to `VenueLocation`
      (venue_locations.py) and verify `uv run mypy .` passes with the new
      fields as `str | None = None`
- [ ] 1.2 Add `street_address`/`postal_code` to `Venue` (store.py) and
      `_MIGRATED_VENUE_COLUMNS`; verify a test confirms a fresh database
      creates the columns and an existing one gets them ALTERed in
- [ ] 1.3 Thread `street_address`/`postal_code` through `add_venue`
      (copied from `KNOWN_VENUE_LOCATIONS` the same way chain/city/
      country/coordinates already are) and verify a test confirms a venue
      matching the table gets both fields set on creation

## 2. LOCATION and X-\* properties

- [ ] 2.1 Write a failing test: pushing an entry at a venue with a known
      street address and postal code produces a LOCATION string
      including both, then update `_venue_location()` (cli.py) to make it
      pass
- [ ] 2.2 Write a failing test: a venue with only one of street
      address/postal code known falls back to the shorter
      "venue, city, country" LOCATION shape, then confirm `_venue_location()`
      already handles it correctly (or fix it if not)
- [ ] 2.3 Write a failing test: pushing an entry at a venue with a known
      street address and postal code sets `X-STREET-ADDRESS` and
      `X-POSTAL-CODE` on the VEVENT, then update `_extra_properties()`
      (calendar_sync.py) to make it pass
- [ ] 2.4 Write a failing test: each of `X-STREET-ADDRESS`/
      `X-POSTAL-CODE` is omitted independently when its own value isn't
      known (not an all-or-nothing pair), then confirm it passes

## 3. Refresh existing venue rows

- [ ] 3.1 Write a failing test: `Store.refresh_venue_locations(apply=False)`
      reports which existing venue rows would gain a field the table now
      has for them, without writing anything, then implement it
      (mirroring `merge_venue_aliases`'s dry-run/apply shape)
- [ ] 3.2 Write a failing test: `apply=True` writes the table's current
      chain/city/country/coordinates/street_address/postal_code onto a
      matching existing row unconditionally (a full resync, not a
      fill-only-if-missing merge - per design.md's decision, there's no
      legitimate way for a row to hold a value that genuinely diverges
      from the table on purpose, since these fields are only ever set
      by copying from it), then implement it
- [ ] 3.3 Write a failing test: a venue row whose name has no entry in
      the table at all is left completely untouched by refresh, then
      confirm it passes
- [ ] 3.4 Add the `movie-planner locations venues refresh` CLI command
      (dry-run output by default, `--apply` to write) with its own CLI
      test covering both modes

## 4. Backfill real venue data

- [ ] 4.1 Add verified `street_address`/`postal_code` to as many of the
      14 existing `KNOWN_VENUE_LOCATIONS` `_add()` calls as an official
      source confirms, cross-checked against each venue's existing GPS
      coordinates - leave any unconfirmed venue without one, verified by
      re-running the full test suite (`uv run pytest -q`) to confirm
      nothing that reads the table breaks

## 5. Docs

- [ ] 5.1 Update `docs/calendar-schema.md` with the extended LOCATION
      shape and the two new `X-*` properties, verified by the docs lint
      suite (prettier/markdownlint/vale/ltex)
- [ ] 5.2 Update `README.md` with the new `locations venues refresh`
      command and a short explanation of when to run it, verified by the
      same docs lint suite

## 6. Verification

- [ ] 6.1 Full local check suite green: `uv run pytest -q`,
      `uv run ruff check .`/`ruff format --check .`, `uv run mypy .`,
      `uv run bandit -r src/movie_planner`
- [ ] 6.2 Mutation spot-check on the LOCATION-composition pairing rule
      (task 2.2) and the refresh command's "leave a non-matching venue
      untouched" rule (task 3.3), confirming a deliberately introduced
      bug in each is caught by the test suite
