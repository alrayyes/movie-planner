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
  `booking_ref`, `letterboxd_url`, and `letterboxd_rating`. Supplying any
  of these directly (as `The Clockmaker's Daughter` does here) skips the
  OMDb lookup for that row entirely once every OMDb-derived field is
  present - useful for re-importing a previously enriched export without
  burning a fresh API call.

Try one:

```sh
movie-planner import examples/movies.csv
```
