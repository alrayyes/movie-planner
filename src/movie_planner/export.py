"""The JSON `movie-planner export` writes: the same rows movie-planner-web's
"Export as JSON" writes, under the field names both tools' importers read, so
a file made by either imports into the other. A field that isn't set is left
out rather than written as null.
"""

import datetime

from movie_planner.extra_fields import EXTRA_TEXT_FIELDS
from movie_planner.store import Entry, Venue


def _time(value: datetime.time | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds" if value.second else "minutes")


def entry_to_export_row(
    entry: Entry, *, medium_name: str, venue: Venue | None
) -> dict[str, object]:
    """One entry as an import-shaped row. `booking_ref` is never written: it is
    a Pathé reconciliation key only `from-pathe-email` understands.
    """
    fields: dict[str, object | None] = {
        "uid": entry.caldav_uid,
        "title": entry.title,
        "date": entry.date.isoformat(),
        "start_time": _time(entry.start_time),
        "end_time": _time(entry.end_time),
        "medium": medium_name,
        "venue": venue.name if venue else None,
        "city": venue.city if venue else None,
        "country": venue.country if venue else None,
        "street_address": venue.street_address if venue else None,
        "postal_code": venue.postal_code if venue else None,
        "latitude": venue.latitude if venue else None,
        "longitude": venue.longitude if venue else None,
        "director": entry.director,
        "actors": entry.actors,
        "genre": entry.genre,
        "release_year": entry.release_year,
        "poster_url": entry.poster_url,
        "imdb_rating": entry.imdb_rating,
        "rotten_tomatoes_rating": entry.rotten_tomatoes_rating,
        "metacritic_rating": entry.metacritic_rating,
        "imdb_url": entry.imdb_url,
        "letterboxd_url": entry.letterboxd_url,
        "letterboxd_rating": entry.letterboxd_rating,
        "notes": entry.notes,
        "source": entry.source,
        "row": entry.row,
        "seat": entry.seat,
        "budget": None if entry.budget is None else str(entry.budget),
        "popularity": None if entry.popularity is None else str(entry.popularity),
    }
    for name, attr in EXTRA_TEXT_FIELDS.items():
        fields[name] = getattr(entry, attr)
    return {key: value for key, value in fields.items() if value is not None}
