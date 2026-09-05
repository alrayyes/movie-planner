# Import examples

The same three fictional viewings, in each format `movie-planner import`
accepts. Between them, they cover all three time-completeness cases: a
full start/end range, a start with no known end, and a date with no
known time at all.

- `movies.csv` / `movies.json` — `title`, `date`, `medium` are required;
  `start_time`, `end_time`, `venue`, `imdb_url`, `notes` are optional, as
  are the OMDb-derived fields normally fetched automatically -
  `imdb_rating`, `rotten_tomatoes_rating`, `metacritic_rating`,
  `poster_url`, `director`, `actors`, `genre`, `release_year`, plus
  `letterboxd_url` and `letterboxd_rating`. Supplying any of these
  directly (as `The Clockmaker's Daughter` does here) skips the OMDb
  lookup for that row entirely once every OMDb-derived field is present -
  useful for re-importing a previously enriched export without burning a
  fresh API call. `source` is also optional - a plain-text label for
  whatever produced the row (a mail-import tool tagging it with a sender
  domain, say). It's stored as given; nothing here ever interprets it.
- [`movies.schema.json`](movies.schema.json) is the JSON Schema for one
  row - required/optional fields, types, and the date/time formats
  expected. It's the same field-name shape whether the row came from
  `movies.json` or `movies.csv`'s header row; the schema's own
  `description` covers the one difference (CSV values are always plain
  text). [`movie-planner-web`](https://github.com/alrayyes/movie-planner-web)
  reads this file's field names to stay compatible.

Try one:

```sh
movie-planner import examples/movies.csv
```
