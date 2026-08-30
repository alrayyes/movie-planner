# Import examples

The same three viewings, in each format `movie-planner import` accepts.
Between them, they cover all three time-completeness cases: a full
start/end range, a start with no known end, and a date with no known
time at all.

- `movies.csv` / `movies.json` — `title`, `date`, `medium` are required;
  `start_time`, `end_time`, `venue`, `imdb_url` are optional.
- `movies.org` — matches the structure of a hand-kept org-mode log: a
  heading per movie, an org timestamp for date/time, and `CINEMA`/`IMDB`
  properties. The medium comes from the immediate parent heading's own
  tag (`:cinema:`, `:netflix:`, and so on), not the movie heading itself.

Try one:

```sh
movie-planner import examples/movies.csv
```
