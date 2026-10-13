import base64
import json
from datetime import date, time

import pytest

from movie_planner.display import (
    detect_terminal_image_protocol,
    entry_to_json,
    format_entry,
    render_poster,
)
from movie_planner.store import Entry, Venue

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(autouse=True)
def _clear_terminal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("KITTY_WINDOW_ID", "TERM", "TERM_PROGRAM"):
        monkeypatch.delenv(var, raising=False)


def test_detect_protocol_kitty_window_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITTY_WINDOW_ID", "1")

    assert detect_terminal_image_protocol() == "kitty"


def test_detect_protocol_kitty_term(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm-kitty")

    assert detect_terminal_image_protocol() == "kitty"


def test_detect_protocol_ghostty(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ghostty implements the Kitty graphics protocol but identifies
    # itself as TERM=xterm-ghostty, not xterm-kitty, and sets neither
    # KITTY_WINDOW_ID nor TERM_PROGRAM - confirmed against Ghostty's own
    # docs, not assumed.
    monkeypatch.setenv("TERM", "xterm-ghostty")

    assert detect_terminal_image_protocol() == "kitty"


@pytest.mark.parametrize("program", ["iTerm.app", "WezTerm"])
def test_detect_protocol_iterm2(program: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM_PROGRAM", program)

    assert detect_terminal_image_protocol() == "iterm2"


def test_detect_protocol_none() -> None:
    assert detect_terminal_image_protocol() is None


def test_render_poster_iterm2_wraps_any_bytes() -> None:
    rendered = render_poster(b"not really an image", "iterm2")

    assert rendered is not None
    assert rendered.startswith("\033]1337;File=")
    assert "bm90IHJlYWxseSBhbiBpbWFnZQ==" in rendered  # base64 of the input


def test_render_poster_kitty_png_bytes() -> None:
    rendered = render_poster(_PNG_MAGIC + b"restofimage", "kitty")

    assert rendered is not None
    assert rendered.startswith("\033_G")


def test_render_poster_kitty_non_png_bytes_returns_none() -> None:
    rendered = render_poster(b"\xff\xd8\xffJFIFjpegbytes", "kitty")

    assert rendered is None


# --- _render_kitty: exact escape-sequence layout, not just a leading marker ---


def test_render_kitty_single_chunk_is_final_with_control_data() -> None:
    from movie_planner.display import _render_kitty

    rendered = _render_kitty(_PNG_MAGIC + b"restofimage")

    encoded = base64.b64encode(_PNG_MAGIC + b"restofimage").decode("ascii")
    assert rendered == f"\033_Ga=T,f=100,m=0;{encoded}\033\\"


def test_render_kitty_splits_into_chunks_at_the_configured_chunk_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from movie_planner.display import _render_kitty

    # Shrink the chunk size instead of feeding in a >4096-char base64
    # payload: a couple of surviving mutants here turn the chunk loop's
    # range into something pathological (e.g. iterating the full encoded
    # length one character at a time), and pairing that with real-sized
    # data made the mutant's own test run time out rather than fail
    # cleanly. A tiny chunk size exercises the exact same multi-chunk
    # ("more data follows") logic with a handful of iterations either way.
    monkeypatch.setattr("movie_planner.display._KITTY_CHUNK_SIZE", 4)
    raw = b"hello"
    encoded = base64.b64encode(raw).decode("ascii")
    assert encoded == "aGVsbG8="

    rendered = _render_kitty(raw)

    assert rendered == "\033_Ga=T,f=100,m=1;aGVs\033\\\033_Gm=0;bG8=\033\\"


def _entry(**overrides: object) -> Entry:
    defaults: dict[str, object] = {
        "id": 1,
        "title": "Dune",
        "date": date(2026, 1, 1),
        "medium_id": 1,
    }
    defaults.update(overrides)
    return Entry(**defaults)  # type: ignore[arg-type]


def test_format_entry_includes_all_present_fields() -> None:
    entry = _entry(
        start_time=time(19, 0),
        end_time=time(21, 15),
        imdb_rating="8.5/10",
        imdb_url="https://www.imdb.com/title/tt1160419/",
        rotten_tomatoes_rating="91%",
        metacritic_rating="80",
        trailer_url="https://www.youtube.com/watch?v=8g18jFHCLXk",
        letterboxd_url="https://letterboxd.com/film/dune-2021/",
        letterboxd_rating="4.5",
        notes="Enjoyed the soundtrack",
        director="Denis Villeneuve",
        actors="Timothée Chalamet, Rebecca Ferguson, Zendaya",
        genre="Action, Adventure, Drama",
        release_year=2021,
    )
    venue = Venue(id=1, name="Grand Vista Cinema")

    text = format_entry(entry, medium_name="cinema", venue=venue)

    assert "Dune" in text
    assert "2026-01-01" in text
    assert "19:00" in text and "21:15" in text
    assert "cinema" in text
    assert "Grand Vista Cinema" in text
    assert "8.5/10" in text
    assert "91%" in text
    assert "80" in text
    assert "letterboxd.com/film/dune-2021" in text
    assert "4.5" in text
    assert "youtube.com/watch?v=8g18jFHCLXk" in text
    assert "Enjoyed the soundtrack" in text
    assert "Denis Villeneuve" in text
    assert "Timothée Chalamet, Rebecca Ferguson, Zendaya" in text
    assert "Action, Adventure, Drama" in text
    assert "2021" in text


def test_format_entry_includes_venue_chain_and_location() -> None:
    entry = _entry()
    venue = Venue(id=1, name="Tuschinski", chain="Pathé", city="Amsterdam", country="Netherlands")

    text = format_entry(entry, medium_name="cinema", venue=venue)

    assert "Tuschinski" in text
    assert "Pathé" in text
    assert "Amsterdam" in text
    assert "Netherlands" in text


def test_format_entry_omits_absent_fields() -> None:
    entry = _entry()

    text = format_entry(entry, medium_name="netflix", venue=None)

    assert "Dune" in text
    assert "netflix" in text
    assert "IMDb" not in text
    assert "Rotten Tomatoes" not in text
    assert "Metacritic" not in text
    assert "Trailer" not in text
    assert "Letterboxd" not in text
    assert "Notes" not in text
    assert "Director" not in text
    assert "Genre" not in text
    assert "Cast" not in text
    assert "Year" not in text


def test_format_entry_start_time_without_end_time_omits_the_range() -> None:
    entry = _entry(start_time=time(19, 0))

    text = format_entry(entry, medium_name="cinema", venue=None)

    lines = text.splitlines()
    assert lines[1] == "  19:00"


def test_format_entry_imdb_url_without_rating_shows_url_only() -> None:
    entry = _entry(imdb_url="https://www.imdb.com/title/tt1160419/")

    text = format_entry(entry, medium_name="cinema", venue=None)

    assert "  IMDb: https://www.imdb.com/title/tt1160419/" in text.splitlines()


def test_format_entry_letterboxd_url_without_rating_omits_the_suffix() -> None:
    entry = _entry(letterboxd_url="https://letterboxd.com/film/dune-2021/")

    text = format_entry(entry, medium_name="cinema", venue=None)

    assert "  Letterboxd: https://letterboxd.com/film/dune-2021/" in text.splitlines()


def test_format_entry_joins_lines_with_a_single_newline() -> None:
    entry = _entry()

    text = format_entry(entry, medium_name="netflix", venue=None)

    assert text == "Dune (2026-01-01)\n  netflix"


def test_entry_to_json_includes_every_stored_field_and_the_venue_join() -> None:
    entry = _entry(
        start_time=time(19, 0),
        end_time=time(21, 15),
        imdb_rating="8.5/10",
        imdb_url="https://www.imdb.com/title/tt1160419/",
        rotten_tomatoes_rating="91%",
        metacritic_rating="80",
        trailer_url="https://www.youtube.com/watch?v=8g18jFHCLXk",
        letterboxd_url="https://letterboxd.com/film/dune-2021/",
        letterboxd_rating="4.5",
        notes="Enjoyed the soundtrack",
        director="Denis Villeneuve",
        writer="Jon Spaihts",
        actors="Timothée Chalamet, Rebecca Ferguson, Zendaya",
        genre="Action, Adventure, Drama",
        release_year=2021,
    )
    venue = Venue(id=1, name="Tuschinski", chain="Pathé", city="Amsterdam", country="Netherlands")

    data = entry_to_json(entry, medium_name="cinema", venue=venue)

    assert data["id"] == 1
    assert data["title"] == "Dune"
    assert data["date"] == "2026-01-01"
    assert data["start_time"] == "19:00:00"
    assert data["end_time"] == "21:15:00"
    assert data["medium"] == "cinema"
    assert data["venue"] == "Tuschinski"
    assert data["venue_chain"] == "Pathé"
    assert data["venue_city"] == "Amsterdam"
    assert data["venue_country"] == "Netherlands"
    assert data["director"] == "Denis Villeneuve"
    assert data["writer"] == "Jon Spaihts"
    assert data["actors"] == "Timothée Chalamet, Rebecca Ferguson, Zendaya"
    assert data["genre"] == "Action, Adventure, Drama"
    assert data["release_year"] == 2021
    assert data["imdb_rating"] == "8.5/10"
    assert data["imdb_url"] == "https://www.imdb.com/title/tt1160419/"
    assert data["imdb_id"] == "tt1160419"
    assert data["rotten_tomatoes_rating"] == "91%"
    assert data["metacritic_rating"] == "80"
    assert data["trailer_url"] == "https://www.youtube.com/watch?v=8g18jFHCLXk"
    assert data["letterboxd_url"] == "https://letterboxd.com/film/dune-2021/"
    assert data["letterboxd_rating"] == "4.5"
    assert data["notes"] == "Enjoyed the soundtrack"
    json.dumps(data)  # every value must be JSON-serializable, not just present


def test_entry_to_json_absent_fields_are_null_not_omitted() -> None:
    entry = _entry()

    data = entry_to_json(entry, medium_name="netflix", venue=None)

    assert "director" in data
    assert data["director"] is None
    assert data["venue"] is None
    assert data["venue_chain"] is None
    assert data["venue_city"] is None
    assert data["venue_country"] is None
    assert data["imdb_id"] is None
    assert data["start_time"] is None
    assert data["end_time"] is None
