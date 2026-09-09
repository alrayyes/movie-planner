# Usage

The full behaviour behind each `movie-planner` command — see the main
[README](../README.md#usage) for installation, the golden-path `log`/
`from-pathe-email` examples, and the full one-line command reference.

## Filtering and limiting `list`

`list --limit N` shows only the N most recently dated entries, applied
after every other filter - combine it with `--chain`/`--city`/
`--medium`/`--from`/`--to` to get "the last 5 at this chain" rather
than the whole log. Omit it and `list` shows everything matching the
other filters, same as always.

`list --omdb-no-match` shows only entries whose most recent OMDb
lookup found no match - a title with a typo, a format suffix the
stripper missed, or one OMDb genuinely doesn't have - distinct from an
entry that was simply never looked up. Fix the title by hand, then
`update --refresh-metadata` (below) to try again.

## `show`

`show` prints one entry's full metadata — ratings, links, venue, times,
and, where OMDb had them, director, cast, genre, and release year — in
a structured, labelled layout instead of `list`'s single line, which
shows the release year alongside the title when known. On a
terminal identifiable as iTerm2/WezTerm or Kitty/Ghostty, it also renders
the poster inline — `poster_url` is fetched and stored the same time
ratings are (`log`, `import`, `sync refresh`), or, for an entry logged
before this existed, fetched live at display time instead; anywhere
else, or with no poster available, `show` just skips the image. Kitty
only renders a poster that's already PNG — OMDb's usual JPEG posters
render on iTerm2/WezTerm only. No Sixel support.

## Automatic venue fill-in

A venue created with a name matching a hardcoded table (Pathé's own
Amsterdam cinemas, GSC's Malaysia locations, and a handful of
independent Amsterdam venues) gets its chain, city, and country filled
in automatically — a name that doesn't match gets none of that, never
a guess. `list --chain`/`--city` filter on it; `show` displays it. Most
of those same venues also carry known GPS coordinates, pushed to the
calendar as the event's `GEO` property, and most now also carry a
verified street address and postal code, extending the calendar
event's `LOCATION` from "venue, city, country" to a full address a
calendar client can geocode to the actual building (see
[`calendar-schema.md`](calendar-schema.md)) — again, only
ever a verified value, never estimated. This backfills onto an
existing database automatically the next time any command runs — a
venue row created before its table entry had street-level data picks
it up on the next store open, nothing to run by hand. `sync refresh`
(plain, not `--force`) is what gets the refreshed data onto the
calendar itself for entries synced before this existed, without
re-fetching OMDb ratings for entries that already have them.

## `import`

`import` accepts a `.csv` or `.json` file with the same fields as
`examples/`, and fetches OMDb ratings the same as `log` does - unless a
row already supplies every OMDb-derived field itself (ratings, poster,
director, actors, genre, release year), in which case that row's OMDb
lookup is skipped entirely, same as an already-enriched entry is on
`sync refresh`. Useful for re-importing an export from somewhere that
already ran its own OMDb lookup. A row that fails to parse (a bad date,
a missing required field) is recorded rather than only echoed at the
time - `import-failures list` shows every past failure, most recent
first, and `import-failures clear` empties the list once you've dealt
with them. `sync retry`
re-pushes any entry that failed to sync when it was logged or imported —
cheap, and safe to run any time, since it never calls OMDb and only
touches entries that were never synced. `sync refresh` is the heavier
counterpart: it walks every entry, fetches OMDb data (ratings, poster,
and so on) for any entry still missing at least one such field — an
entry that already has a rating but was logged before a newer field
existed still gets that field backfilled — and re-pushes every
calendar event so its description reflects current data. Worth running
after upgrading, or to backfill data for entries imported before this
existed, not something to run reflexively the way `retry` is. Pass
`--from`/`--to` or a single `--date` to scope it to a range instead of
the whole log; `--date` can't be
combined with either. Pass `--force` to re-fetch ratings for entries
that already have them too — useful after a wrong OMDb match, or when a
rating's changed since — instead of the default of only fetching for
entries still missing one. `update --refresh-metadata` does the same
thing for one specific entry, by ID - no need to work out its date or
risk force-refreshing a sibling entry that happens to share it.

## Sync and `sync pull`

Sync is otherwise push-only — movie-planner never reads the calendar
back on its own, and the local SQLite store is the only source of
truth. See [`calendar-schema.md`](calendar-schema.md) for exactly what
gets written to the calendar, if something else needs to read it.

`sync pull` is the one exception: it fetches every
event on the calendar and compares it against the local store,
showing each new, changed, or removed entry it finds one at a time
for approval — nothing is written without an explicit yes, and
declining leaves it to be offered again next time. It's a manually
run, one-shot reconciliation, not a background job — for catching up
after using [movie-planner-web](https://github.com/alrayyes/movie-planner-web)
to create, edit, or delete an entry directly on the calendar. See
[`calendar-schema.md`](calendar-schema.md) for exactly which
fields it compares (only OMDb's/booking's own structured `X-*`
properties — never the free-text description).

## `activity`

`activity` shows a local log of every create/update/delete this tool
has made to your entries, most recent first - for an update, which
fields actually changed and their before/after values, not the whole
entry. It's populated automatically by `log`, `update`, `delete`,
`import`, `from-pathe-email`, and `sync refresh`/`sync pull`, since
they all go through the same three store operations underneath. Local
to this tool only - it's not a shared trail with
[movie-planner-web](https://github.com/alrayyes/movie-planner-web),
which keeps its own equivalent log of the actions it makes.

## `bug-report`

`bug-report` prints a diagnostic summary safe to share with an AI
session, in a GitHub issue, or with anyone helping debug — tool/Python
version, config shape, and store counts. It never includes CalDAV
credentials, API keys, entry titles/notes, or venue names (issue #256).
Pass `--output <path>` to write it to a file instead of stdout.

## Bulk historical imports

A large historical import (years of entries at once) can exceed OMDb's
daily request limit before it finishes. Pass `--no-metadata` to `import`
to create every entry with no OMDb calls at all, then backfill ratings
afterward with `sync refresh --from`/`--to`, one date range per day, as
many days as the limit takes to clear:

```sh
uv run movie-planner import movies-2020-2026.csv --no-metadata
uv run movie-planner sync refresh --from 2020-01-01 --to 2021-12-31
# next day:
uv run movie-planner sync refresh --from 2022-01-01 --to 2023-12-31
# ...and so on until every year is covered
```
