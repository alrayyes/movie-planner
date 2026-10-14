# Usage

The full behaviour behind each `movie-planner` command — see the main
[README](../README.md#usage) for installation, the golden-path `log`/
`from-pathe-email` examples, and the full one-line command reference.

## Filtering and limiting `list`

`list` also filters on what OMDb stored about each film: `--title`,
`--director`, `--actor` and `--genre` match part of the text, ignoring case
(`--actor zendaya` finds a film whose cast list includes her); `--venue`
matches a venue's exact name, ignoring case; `--year` is the release year;
`--rated` is the rating class, such as `PG-13`, ignoring case. Every filter
you give must match, and they combine with `--from`, `--to`, `--medium`,
`--chain` and `--city`. `--json` prints the filtered set.

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

## `--json` output

`--json` on `list` or `show` prints every field movie-planner stores for
the matching entry/entries as JSON instead of the preceding plain-text
layouts — a full object per entry, including fields those layouts never
show (the entry's own id, its start/end time, `poster_url`,
`letterboxd_url`/`letterboxd_rating`, `notes`, `source`), plus the
medium/venue names its foreign keys join to, along with an IMDb ID
(`imdb_id`) pulled from `imdb_url`. Every key is always present —
`null` rather than omitted when unset, so a consuming script never has
to guard against a missing key — and `list --json` prints `[]` rather
than the plain-text `No entries.` for a filter that matches nothing.
Built for external tooling that wants the full record without scraping
text or reaching into the SQLite file directly; combines with every
preceding `list` filter.

## Editing a venue

`locations venues edit "Grand Vista Cinema" --street "1 Main St" --postal-code
1011AB --city Amsterdam --country NL` sets a venue's address, so a venue you
added with just a name can gain one later. `--chain` sets its chain, and
`--lat` with `--lon` sets its coordinates (latitude -90 to 90, longitude -180
to 180; give both or neither). Fields you leave out stay as they are, and an
empty value such as `--street ""` clears one, and it stays cleared even on a venue
from the built-in table. An unknown name fails and
changes nothing. The calendar events at the venue are updated to carry the new
LOCATION and GEO straight away; if the calendar can't be reached you get a
warning, and `sync refresh` pushes them later. `locations venues list` shows
each venue's chain, address and coordinates.

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

A Letterboxd `diary.csv` (from Letterboxd's Import & Export settings) imports
too, recognised by its `Name`, `Letterboxd URI` and `Watched Date` columns.
Each row becomes an entry dated `Watched Date`, not `Date`, which is the day
you logged it. It keeps the film's Letterboxd link, rating and year, and any
tags as a note (`Tags: sci-fi, imax`). A diary doesn't say where you watched,
so `--medium` is required: `movie-planner import diary.csv --medium netflix`.
Without it the command stops before writing anything.

An IMDb `ratings.csv` imports the same way, recognised by its `Const`, `Title`,
`Your Rating` and `Date Rated` columns (a list export without the rating
columns isn't one). IMDb keeps no watched date, so each entry is dated the day
you rated it, with the year, genres, director, IMDb link and score, and "Your
IMDb rating: 9/10" as a note. `--medium` is required here too. The file also
lists series, episodes, games, podcasts and music videos. Those are skipped
and named in the run summary (`skipped: row 3: "Severance" is a TV series on
IMDb, not a movie`), not recorded as failures, and nothing is written for them.
Any other title type imports as a film.

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
that already have them too, useful when a rating's changed since, instead
of the default of only fetching for
entries still missing one. `update --refresh-metadata` does the same
thing for one specific entry, by ID - no need to work out its date or
risk force-refreshing a sibling entry that happens to share it.

If OMDb refuses a request, because the day's quota is spent or the API key is
wrong, that isn't a missing title: the entry isn't marked as having no match,
and `sync refresh` and `import` stop asking, say how many titles they had done,
and carry on pushing the rest to the calendar. Run `sync refresh` again once
OMDb answers. `log` and `update` save the entry without metadata, as they do
for any failed lookup.

Some films OMDb knows but has no poster or plot for, so they stay incomplete
after every lookup. A plain `sync refresh` remembers a title OMDb answered for
but couldn't complete, and leaves it out for the next 30 days instead of
spending the daily quota on it again; it says how many it left out. Only an
answer counts: a refusal, a failed request and "no match" mark nothing. The
note is kept in the local database, not on the calendar. `--force`, or
`--date` for one day, asks OMDb anyway. Changing an entry's title or IMDb ID with
`update` drops its note, since that asks OMDb something new.

An entry that already has an IMDb link is always refreshed from the ID in that
link, never by looking its title up again, so a match you corrected by hand
stays put. If OMDb has nothing for that ID the entry is left as it is.
That also means `--force` and `--refresh-metadata` can't fix a wrong match:
they re-fetch the same ID. Use `update --imdb-id` with the right one.

Only `--force`, `update --refresh-metadata` and `update --imdb-id` replace
values an entry already has. A plain lookup, whether from `log`, `import` or
a plain `sync refresh`, fills the fields that are empty and leaves the rest
alone, so a synopsis you edited or imported isn't overwritten. Neither kind of
lookup ever blanks a value because OMDb has no answer for it. The same goes
for the TMDb fields, and for ratings: a plain refresh won't update one an entry
already has, so use `--force` for that.

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

## `export`

`export` writes your entries as the JSON array `import` reads, the same rows
movie-planner-web's "Export as JSON" writes. Use it to back up the log, move
it to another machine, or edit it and import it again. It validates against
[`examples/movies.schema.json`](../examples/movies.schema.json).

```sh
movie-planner export > movies.json
movie-planner export --from 2026-01-01 --to 2026-01-31 --medium cinema -o january.json
```

`--from`, `--to` and `--medium` filter as `list` does. `--output`/`-o` writes
a file and prints a one-line count instead of the JSON. A field that isn't set
is left out of its row rather than written as `null`, and `booking_ref` is
never written, since only `from-pathe-email` understands it. A row also
carries its venue's `city`, `country`, `street_address`, `postal_code`,
`latitude` and `longitude` when the venue has them, so importing the file into
movie-planner-web keeps the venue maps. `import` reads the same six fields back,
filling only what the venue doesn't have yet, so a venue you corrected here
isn't overwritten. A latitude without a longitude, or one out of range, fails
its row. A field you cleared on purpose stays cleared. Events
already on the calendar for a venue that gains data keep what they had until
`sync refresh --force` pushes them again. Each row also carries `synopsis`,
`rated`, `runtime`, `movie_language`, `movie_country`, `metascore`,
`imdb_votes`, `dvd`, `box_office`, `production`, `website`, `released`,
`awards`, `trailer_url`, `collection`, `certification`, `keywords`, `budget`
and `popularity`, and `import` reads them back. They use the web app's names,
so `synopsis` is the `plot` stored here. This differs from
`list --json`, which keeps every key and uses movie-planner's own names.

## `purge`

`purge` deletes every event from the calendar and can't be undone. It leaves
the local database alone, so your entries stay and a later `sync` or edit can
put them back on the calendar. It asks you to type `DELETE` first. `--yes`
skips the prompt for scripts, and without `--yes` it refuses to run when
there's no terminal. If some events fail to delete, it says how many and exits
non-zero; run it again.

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
