# Import examples

The same three fictional viewings, in each format `movie-planner import`
accepts. Between them, they cover all three time-completeness cases: a
full start/end range, a start with no known end, and a date with no
known time at all.

- `movies.csv` / `movies.json` — `title`, `date`, `medium` are required;
  `start_time`, `end_time`, `venue`, `imdb_url`, `notes` are optional.

Try one:

```sh
movie-planner import examples/movies.csv
```
