# Calendar data schema

movie-planner's SQLite store is private to wherever the CLI runs. The
only data surface anything else can actually consume is what gets
pushed to the Baikal (CalDAV) calendar — this is that contract, for
movie-planner-web or any other CalDAV reader.

Sync is push-only by default: `log`/`import`/`update`/`sync refresh`/
`sync retry` never read the calendar back, so most of this document
describes what movie-planner writes, not a two-way protocol. The one
exception is `sync pull` (issue #235) - a manually run, approval-gated
reconciliation step, not automatic - see "A note for anything else
editing the calendar" below for exactly what it reads back and how.
Everything here is built by
`build_vevent`/`build_description`/`_extra_properties` in
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
  retroactive. If the calendar no longer has an entry's UID (the
  calendar was wiped or rebuilt outside movie-planner), the next
  `sync refresh`/`sync retry` recovers automatically: it treats the
  entry as never synced, generates a fresh UID, and pushes a new
  event, rather than warning forever about the same missing UID.
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
  - `{venue name}, {street address}, {postal code} {city}, {country}`
    — a venue with a verified street address _and_ postal code (issue
    #283), extending the shape above to a full address a calendar
    client can geocode to the actual building, not just the city. Only
    when both are known: a street address with no postal code (or vice
    versa) falls back to the shorter `{venue name}, {city}, {country}`
    shape instead of a partial address - a worse geocoding hint than
    the plain city/country string it would otherwise be.
- **GEO** — present only for a venue with known coordinates (issue
  #170): `{latitude};{longitude}`, `icalendar`'s `vGeo` FLOAT pair. A
  venue with no coordinates on record gets no `GEO` property at all -
  never a guessed value, same "never a guess" rule the chain/city/
  country table above already follows. Additive to `LOCATION`, not a
  replacement - a client without `GEO` support still gets the address
  string.
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
  - **`X-ACTORS`** — a comma-separated string, verbatim, not split into
    a list. OMDb's own `Actors` by default, but overridden with TMDb's
    full cast (issue #311) whenever TMDb resolves a match for the
    entry - OMDb's own field only ever returns a handful of top-billed
    names, with no full-cast endpoint at any tier, so TMDb's fuller
    list wins when it's available. A TMDb match with no cast data
    leaves OMDb's own value standing rather than blanking it.
  - **`X-GENRE`** — OMDb's `Genre`, also comma-separated, verbatim.
  - **`X-YEAR`** — the release year, as a plain integer string (for
    example `2021`) - not the watched date, which is `DTSTART`/`DTEND`
    instead.
  - **`X-CITY`**/**`X-COUNTRY`** — a venue matching the hardcoded
    chain/location table below, same source as the `city`/`country`
    already baked into `LOCATION` (issue #217) - a structured field a
    reader can consume without parsing `LOCATION` apart. Additive, not
    a replacement, same "omit, never guess" rule `GEO` already
    follows: a venue not in the table gets neither property.
  - **`X-STREET-ADDRESS`**/**`X-POSTAL-CODE`** — a venue with a
    verified street address/postal code (issue #283), same source as
    the fuller `LOCATION` shape above. Split into two properties, not
    one combined `X-ADDRESS`: international address ordering varies
    too much for one string to serialize cleanly (postal-code-before-
    city is Dutch convention, not universal; some countries have no
    postal code at all), and it reuses `X-CITY`/`X-COUNTRY`'s exact
    pattern - a direct 1:1 pass-through, no joining logic. Each is set
    **independently** of the other, unlike `LOCATION` above, which
    only includes either when both are known: a venue with a
    confirmed street but no confirmed postal code still gets
    `X-STREET-ADDRESS` alone, and vice versa.
  - **`X-ROW`**/**`X-SEAT`** — an entry's seat assignment, as text (for
    example `5`/`17`) - only ever set from a Pathé booking confirmation
    parse (issue #218), never from a manually logged entry. Same
    "omit, never guess" rule: an entry with no known row/seat gets
    neither property, same as `screening_details` below being the only
    other place this text shows up (in `DESCRIPTION`, free-form,
    combined with the auditorium/format) - these two properties are
    the structured equivalent, not a replacement for it.
  - **`X-RATED`**, **`X-RUNTIME`**, **`X-MOVIE-LANGUAGE`**,
    **`X-MOVIE-COUNTRY`**, **`X-METASCORE`**, **`X-IMDB-VOTES`**,
    **`X-DVD`**, **`X-BOX-OFFICE`**, **`X-PRODUCTION`**, **`X-WEBSITE`**
    — the rest of OMDb's own response fields (issue #237), verbatim,
    no normalization. `X-MOVIE-LANGUAGE`/`X-MOVIE-COUNTRY`, not
    `X-LANGUAGE`/`X-COUNTRY` - these are the _movie's_ own
    country/language of origin, a different thing from the _venue's_
    `X-CITY`/`X-COUNTRY` above, and reusing that name would collide.
    `Plot`, `Awards`, and `Released` are longer-form text and go into
    `DESCRIPTION` instead - see below. `X-WEBSITE` is overridden with
    TMDb's own `homepage` (issue #311) whenever TMDb has one - OMDb's
    own `Website` field is routinely `N/A`, same override rule as
    `X-ACTORS` above.
  - **`X-TRAILER-URL`** — a YouTube link to the movie's official trailer
    (issue #236), from TMDb rather than OMDb - looked up by the `imdbID`
    an OMDb match already returned, so it only ever runs right after a
    successful OMDb fetch, never on its own. Same "omit, never guess"
    rule as everything else here: no `tmdb.api_key` configured (it's
    optional, unlike `omdb.api_key`), no TMDb match, or no official
    YouTube trailer among TMDb's videos, and the entry simply has no
    `X-TRAILER-URL` at all.
  - **`X-COLLECTION`**, **`X-CERTIFICATION`**, **`X-KEYWORDS`**,
    **`X-BUDGET`**, **`X-POPULARITY`** — the rest of TMDb's own response
    fields with no OMDb equivalent (issue #311), fetched in the same
    call as `X-TRAILER-URL` above, same "piggybacks on a successful OMDb
    match, never on its own" rule. `X-CERTIFICATION` is TMDb's own
    content rating, always the US (MPAA) certification when TMDb has
    one - deliberately distinct from `X-RATED` (OMDb's field, a
    different rating system) and never falls back to another country's
    rating, which would use an incompatible scale. `X-BUDGET` is a
    plain integer string (production budget, in US dollars) - TMDb's
    own box-office revenue figure is deliberately never captured here,
    since revenue keeps changing after release and budget doesn't.
    `X-POPULARITY` is TMDb's own popularity score, a plain decimal
    string - a genuine `0` is kept, not treated as unset, unlike
    `X-BUDGET`, where TMDb itself uses `0` as "nothing entered." A
    refresh that gets a thinner TMDb response than a previous one (a
    missing sub-resource, a transient gap in TMDb's own data) never
    resets an already-known value on any of these back to unset.
  - **`X-IMPORTER`**/**`X-IMPORTER-VERSION`** — debugging provenance
    (issue #257): which movie-planner command performed this push
    (`log`, `import:csv`, `import:json`, `from-pathe-email`,
    `sync-retry`, `sync-refresh`, `update`) and which version of the
    tool did it, read from the installed package at push time. Same
    "omit, never guess" rule as everything else here - a caller that
    doesn't pass an importer label (a test using `CalendarSync`
    directly, for example) gets neither property.

A real example — an entry at a known venue, with a genre tag,
coordinates, and a verified street address on record, exactly as
`build_vevent` produces it:

```text
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//movie-planner//EN
BEGIN:VEVENT
SUMMARY:Insidious: Out of the Further
DTSTART:20260827T134000
DTEND:20260827T154600
UID:0199c1f2-3a4b-7def-8a9b-0123456789ab
GEO:52.3633802;4.8838439
LOCATION:City\, Kleine-Gartmanplantsoen 15-19\, 1017 RP Amsterdam\, Nether
 lands
X-BUDGET:10000000
X-CERTIFICATION:PG-13
X-COLLECTION:Insidious Collection
X-GENRE:Horror
X-KEYWORDS:haunted house, medium, supernatural
X-POPULARITY:45.231
X-POSTAL-CODE:1017 RP
X-STREET-ADDRESS:Kleine-Gartmanplantsoen 15-19
END:VEVENT
END:VCALENDAR
```

Note the commas in `X-KEYWORDS` aren't backslash-escaped the way the ones
in `LOCATION` are - `LOCATION` is one of iCalendar's own known TEXT-typed
properties, so the `icalendar` library escapes it automatically; a custom
`X-*` property is opaque to it and gets added as a plain string, no
escaping applied.

Line-folded per RFC 5545 (75-octet limit, continuation lines start with a
single space) - a real `LOCATION` this long always wraps like this; a
reader needs to unfold it the same way a real CalDAV client would, not
match it as one line.

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
4. **Released** — `Released: {released}`, OMDb's own full release date
   (for example `22 Oct 2021`) - distinct from `X-YEAR`, which is
   parsed down to a bare four-digit year.
5. **Plot** — `Plot: {plot}`, OMDb's synopsis, verbatim.
6. **Awards** — `Awards: {awards}`, OMDb's own summary text, verbatim.
7. **Letterboxd** — `Letterboxd: {letterboxd_url}`, or
   `Letterboxd: {letterboxd_url} ({letterboxd_rating})` when a rating
   is set
8. **Chain** — `Chain: {chain}`, for example `Chain: Pathé`. Only
   present when the venue matches the hardcoded chain/location table
   (see below); city/country for that same venue go on `LOCATION`
   instead, not here.
9. **Notes** — `Notes: {notes}`. Personal context about the viewing
   (who it was watched with, a reaction) - stored on `notes` and
   unlike screening details, does persist across a `sync refresh` or
   `update` that changes nothing else. Labelled, unlike screening
   details below, specifically so the two can't be confused when an
   entry has both: nothing but position would otherwise tell them
   apart, since both are free text.
10. **Screening details** — free text, no label prefix. Only present
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

`poster_url`, `director`, `actors`, `genre`, `release_year`, and the
rest of OMDb's response (issue #237: `rated`, `released`, `runtime`,
`writer`, `plot`, `language`, `country`, `awards`, `metascore`,
`imdb_votes`, `dvd`, `box_office`, `production`, `website`) all come
straight from OMDb's own response fields on every successful match -
no manual-override protection the way `imdb_url` has, since there's no
way to set any of them by hand. All are overwritten on every fetch,
same as the ratings themselves. `Year` is parsed down to a single
four-digit release year (OMDb sometimes returns a range like
`2019-2023` for a series; the first year in it is what's stored) -
`released`, unlike it, keeps OMDb's own full date string unparsed.

The fields added in #237 deliberately don't factor into whether an
entry "needs" an OMDb fetch (`needs_omdb_fetch` in
[`src/movie_planner/omdb.py`](../src/movie_planner/omdb.py)): several
of them (`dvd`/`box_office`/`production`/`website` especially) are
routinely `"N/A"` even for a real match, so treating their absence as
"still needs fetching" would re-fetch forever for a title OMDb simply
has no data for. A fetch already happening for another reason still
captures these too, at no extra request cost; `sync refresh --force` is
the explicit way to backfill them onto an already-complete older entry.

`trailer_url` (issue #236) follows the same "don't factor into whether
a fetch is needed" rule, for the same reason - `needs_omdb_fetch`
doesn't check it either, since a title with genuinely no official
YouTube trailer would otherwise be re-fetched forever too. It only ever
gets set as a side effect of an OMDb fetch that was already going to
happen (or already has a `caldav_uid` update pending), never fetched on
its own - so an entry logged before `tmdb.api_key` was configured, or
before #236 shipped, needs `sync refresh --force` to backfill it, same
as the rest of OMDb's response.

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

**Venue identity (issue #196):** a venue name that bakes a screen/
format into it ("De Munt 4DX", "De Munt Dolby Atmos") already resolves
to the _same_ chain/city/country/coordinates as its plain-name
counterpart ("De Munt") via `KNOWN_VENUE_LOCATIONS`'s `canonical_name`

- `log`/`import`/`locations venues add` all resolve a known alias to
  its canonical venue automatically now, rather than creating a second
  row for it. A database with venue rows split before this fix landed
  still needs a one-time `locations venues merge-aliases` run (dry-run
  by default; `--apply` to actually reassign entries and remove the
  orphaned alias rows) - and, separately, a `sync refresh --force` over
  the affected date range afterward, since the migration only touches
  the local store and never rewrites an already-pushed calendar event's
  `LOCATION` on its own. The same command also catches and fixes a
  known venue's own `LOCATION` string baked whole into the venue name
  (movie-planner-web#400) - the shape a now-fixed `sync pull` bug could
  produce; see the `sync pull` section below for the mechanism.

Screening details aren't stored anywhere on the entry itself — only
`from-pathe-email` ever supplies them for a push. `sync refresh`,
`sync retry`, and `update` all re-push with no screening details, so
that line doesn't survive past the push that first added it. Don't
rely on it persisting through any later CLI operation, and the same
holds for anything external editing the calendar directly.

## A note for anything else editing the calendar

Aside from `sync pull` (below), movie-planner never reads the calendar
back, so it has no way to detect or react to an external edit on its
own. movie-planner-web (a separate, read/write consumer) parses
`DESCRIPTION` when its own `X-*` properties aren't present yet, and
writes those `X-*` properties on its first edit of an entry — after
that, its own properties take priority over parsing `DESCRIPTION`
again. If another consumer starts writing its own structured
properties, document that alongside this file rather than only in
that project's own repo, so the shared contract stays in one place.

### `sync pull`

`movie-planner sync pull` fetches every event on the calendar and
compares it, by `UID`, against the local store's `caldav_uid`s -
detecting a calendar event with no matching entry (candidate new
entry), an entry whose linked event's structured fields differ
(candidate change), and an entry whose linked event no longer exists
(candidate removal). Every candidate is shown for approval before
anything is written; declining one just means it's offered again next
run, nothing is recorded to suppress it.

Only the same structured fields this document already describes are
ever read back or compared: `SUMMARY`, `DTSTART`/`DTEND`, `LOCATION`
(resolved to a venue name the same way `Store.get_or_create_venue`
already does, alias resolution included), and the `X-DIRECTOR`/
`X-ACTORS`/`X-GENRE`/`X-YEAR`/`X-POSTER-URL`/`X-ROW`/`X-SEAT`
properties. `DESCRIPTION` is never parsed - ratings, Letterboxd, chain,
and notes have no reliable per-field boundary in that free text, so
they're left alone entirely: unset on a new candidate, unchanged on a
changed one. A candidate new entry's medium (a required field with no
calendar-side signal at all) is asked for at approval time, the same
way `log` already asks for it - never guessed or defaulted from
`LOCATION`'s mere presence.

A structured property missing entirely from an event (row/seat
especially - see movie-planner-web#294) is shown as the field going to
"unknown," not phrased as a confirmed deletion, since a missing
property doesn't by itself mean someone removed it on purpose.

`LOCATION` resolution strips a trailing address suffix only when it
exactly matches the event's own `X-CITY`/`X-COUNTRY` (and, when
present, `X-STREET-ADDRESS`/`X-POSTAL-CODE`) - issue #283's fuller
shape is tried first, since it's the more specific match, falling back
to the plain "name, city, country" shape. A bug here (movie-planner-
web#400) tried only the plain shape, so it never matched the fuller
one - the postal code sits between the comma and the city - and
`sync pull` ended up treating the venue's _entire_ `LOCATION` string as
its name. `locations venues merge-aliases` (Venue identity, earlier in
this file) catches and fixes any venue row this already created, the
same way it already fixed a pre-#196 aliased name.
