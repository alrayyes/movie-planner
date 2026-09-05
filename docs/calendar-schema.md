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

- **UID** — a `uuid4` string, generated once per entry and stored as
  the entry's `caldav_uid`. This is how the CLI finds the event again
  to update or delete it; a reader shouldn't assume any other structure
  from it.
- **SUMMARY** — the movie title, verbatim.
- **LOCATION** — the venue name, present only when the entry has one.
  Only a physical-place medium (a cinema, not `netflix`/`youtube`/etc.)
  can have a venue.
- `DTSTART`/`DTEND`, depending on how much time data the entry has:
  - date only → `DTSTART` is a `DATE` value (an all-day event), no
    `DTEND`.
  - date + start time, no end time → `DTSTART` is a `DATE-TIME`, no
    `DTEND`.
  - date + start + end time → both `DTSTART` and `DTEND` are
    `DATE-TIME`.
- **DESCRIPTION** — optional, omitted entirely (not an empty string)
  when there's nothing to show. See below for its content.

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
5. **Notes** — free text, no label prefix. Personal context about the
   viewing (who it was watched with, a reaction) - stored on `notes`
   and unlike screening details, does persist across a `sync refresh`
   or `update` that changes nothing else.
6. **Screening details** — free text, no label prefix. Only present
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
