# Calendar data schema

movie-planner's SQLite store is private to wherever the CLI runs. The
only data surface anything else can actually consume is what gets
pushed to the Baikal (CalDAV) calendar — this is that contract, for
movie-planner-web or any other CalDAV reader.

Sync is push-only: movie-planner never reads the calendar back, so this
document describes what it writes, not a two-way protocol. Everything
here is built by `build_vevent`/`build_description` in
[`src/movie_planner/calendar_sync.py`](../src/movie_planner/calendar_sync.py) —
keep this doc in sync with that file in the same commit that changes
either.

## `VEVENT` fields

- **UID** — a `uuid7` string, generated once per entry (at its first
  push) and stored as the entry's `caldav_uid`. This is how the CLI
  finds the event again to update or delete it. `uuid7`, not `uuid4`:
  time-ordered, so newly created entries insert sequentially rather
  than at a random point - Python 3.14's stdlib `uuid.uuid7()`, no
  dependency needed. A reader can extract the creation timestamp from
  it (the leading 48 bits are a Unix millisecond timestamp per RFC
  9562), but shouldn't assume any other structure. An entry synced
  before this changed keeps its existing `uuid4` UID - this isn't
  retroactive.
- **SUMMARY** — the movie title, verbatim.
- **LOCATION** — present only when the entry has a venue (only a
  physical-place medium - a cinema, not `netflix`/`youtube`/etc. - can
  have one). One of:
  - `{venue name}` — a venue not in the hardcoded chain/location table
    (see below)
  - `{venue name}, {city}, {country}` — a venue that matches the
    table, deliberately shaped as a real, geocodable address string:
    most calendar clients (Google Calendar, Apple Calendar) already
    try to map from `LOCATION`. Commas inside it are backslash-escaped
    per RFC 5545 `TEXT` escaping, same as any other `TEXT` value with a
    literal comma.
- `DTSTART`/`DTEND`, depending on how much time data the entry has:
  - date only → `DTSTART` is a `DATE` value (an all-day event), no
    `DTEND`.
  - date + start time, no end time → `DTSTART` is a `DATE-TIME`, no
    `DTEND`.
  - date + start + end time → both `DTSTART` and `DTEND` are
    `DATE-TIME`.
- **DESCRIPTION** — optional, omitted entirely (not an empty string)
  when there's nothing to show. See below for its content.
- Custom `X-` properties (bare `X-NAME` form, matching
  movie-planner-web's own convention on its read side), each present
  only when the entry has that field. Everything else here is
  standard iCalendar.
  - **`X-POSTER-URL`** — the poster image URL.
  - **`X-DIRECTOR`** — OMDb's `Director`, verbatim (can itself be a
    comma-separated list for a co-directed film).
  - **`X-ACTORS`** — OMDb's `Actors`, a comma-separated string,
    verbatim - not split into a list.
  - **`X-GENRE`** — OMDb's `Genre`, also comma-separated, verbatim.
  - **`X-YEAR`** — the release year, as a plain integer string (for
    example `2021`) - not the watched date, which is `DTSTART`/`DTEND`
    instead.

## DESCRIPTION content

Plain text, newline-separated. Lines appear in this order, each
included only when its underlying field is set:

1. **IMDb** — one of:
   - `IMDb: {imdb_rating}` — rating only, for example `IMDb: 8.5/10`
   - `IMDb: {imdb_rating} ({imdb_url})` — rating and link, for example
     `IMDb: 8.5/10 (https://www.imdb.com/title/tt1160419/)`
   - `IMDb: {imdb_url}` — link only, no rating
2. **Rotten Tomatoes** — `Rotten Tomatoes: {rotten_tomatoes_rating}`,
   for example `91%`
3. **Metacritic** — `Metacritic: {metacritic_rating}`, for example
   `80` or `74/100` — OMDb's own format, not normalized
4. **Letterboxd** — `Letterboxd: {letterboxd_url}`, or
   `Letterboxd: {letterboxd_url} ({letterboxd_rating})` when a rating
   is set
5. **Chain** — `Chain: {chain}`, for example `Chain: Pathé`. Only
   present when the venue matches the hardcoded chain/location table
   (see below); city/country for that same venue go on `LOCATION`
   instead, not here.
6. **Notes** — `Notes: {notes}`. Personal context about the viewing
   (who it was watched with, a reaction) - stored on `notes` and
   unlike screening details, does persist across a `sync refresh` or
   `update` that changes nothing else. Labelled, unlike screening
   details below, specifically so the two can't be confused when an
   entry has both: nothing but position would otherwise tell them
   apart, since both are free text.
7. **Screening details** — free text, no label prefix. Only present
   for an entry sourced from a Pathé booking confirmation email
   (auditorium/format/seat, parsed from that email). Provenance for
   the calendar event, not a stored field on the entry itself.

Ratings come straight from OMDb, not normalized — string fields, not
floats, with no guaranteed format beyond whatever OMDb returned that
day.

`imdb_url` is populated automatically from an OMDb match's `imdbID`
(`https://www.imdb.com/title/<id>/`) unless the entry already has one
set by hand, which is never overwritten — see
[`src/movie_planner/omdb.py`](../src/movie_planner/omdb.py)'s
`fetch_and_store_ratings`.

`poster_url`, `director`, `actors`, `genre`, and `release_year` all
come straight from OMDb's own `Poster`/`Director`/`Actors`/`Genre`/
`Year` fields on every successful match - no manual-override
protection the way `imdb_url` has, since there's no way to set any of
them by hand. All are overwritten on every fetch, same as the ratings
themselves. `Year` is parsed down to a single four-digit release year
(OMDb sometimes returns a range like `2019-2023` for a series; the
first year in it is what's stored).

## Venue chain/location

A venue's chain, city, and country come from a hardcoded table in
[`src/movie_planner/venue_locations.py`](../src/movie_planner/venue_locations.py),
not dynamic geocoding — a venue name not listed there gets none of
this, never a guess. It's applied when the venue is first created
(`log`, `import`, `locations venues add`) and backfilled for an
existing venue the first time the store opens after an upgrade. A
consumer reading the calendar only ever sees the result on
`LOCATION`/the `Chain:` line above - it has no way to tell "no chain
data available" apart from "not in the table at all"; both just omit
the fields.

Screening details aren't stored anywhere on the entry itself — only
`from-pathe-email` ever supplies them for a push. `sync refresh`,
`sync retry`, and `update` all re-push with no screening details, so
that line doesn't survive past the push that first added it. Don't
rely on it persisting through any later CLI operation, and the same
holds for anything external editing the calendar directly.

## A note for anything else editing the calendar

movie-planner never reads the calendar back, so it has no way to
detect or react to an external edit. movie-planner-web (a separate,
read/write consumer) parses `DESCRIPTION` when its own `X-*`
properties aren't present yet, and writes those `X-*` properties on
its first edit of an entry — after that, its own properties take
priority over parsing `DESCRIPTION` again. If another consumer starts
writing its own structured properties, document that alongside this
file rather than only in that project's own repo, so the shared
contract stays in one place.
