"""The text fields movie-planner-web's export and import carry beyond the
core ones, shared by `export` and `import` so they can't drift apart. The key
is the web app's name for the field, the value is this tool's `Entry`
attribute. Three differ: the web app's `synopsis` is our `plot`, and its
`movie_language` and `movie_country` are our `language` and `country`.
"""

EXTRA_TEXT_FIELDS: dict[str, str] = {
    "synopsis": "plot",
    "rated": "rated",
    "runtime": "runtime",
    "movie_language": "language",
    "movie_country": "country",
    "metascore": "metascore",
    "imdb_votes": "imdb_votes",
    "dvd": "dvd",
    "box_office": "box_office",
    "production": "production",
    "website": "website",
    "released": "released",
    "awards": "awards",
    "trailer_url": "trailer_url",
    "collection": "collection",
    "certification": "certification",
    "keywords": "keywords",
}
