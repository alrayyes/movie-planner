from datetime import date, time

import pytest

from movie_planner.display import (
    detect_terminal_image_protocol,
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
        letterboxd_url="https://letterboxd.com/film/dune-2021/",
        letterboxd_rating="4.5",
        notes="Enjoyed the soundtrack",
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
    assert "Enjoyed the soundtrack" in text


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
    assert "Letterboxd" not in text
    assert "Notes" not in text
