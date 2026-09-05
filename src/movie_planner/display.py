"""Formats one entry for `show`, and renders its poster inline where the
terminal supports it.

Deliberately no image-library dependency: `term-image` (the obvious pick)
hard-pins `pillow<11`, and no Pillow 10.x release ships a `cp314` wheel, so
it can't install under this project's Python 3.14. Instead this wraps raw
bytes directly in the iTerm2/Kitty escape sequences.

iTerm2 decodes whatever image format itself, so any bytes work there. Kitty
only accepts raw pixel data or a PNG passthrough (`f=100`) - no JPEG
passthrough - so a JPEG poster (OMDb's usual format) only renders on
iTerm2/WezTerm; Kitty/Ghostty gracefully gets no image rather than a
misrendered one. No Sixel support: a real encoder is a much bigger, riskier
build from scratch than wrapping bytes in an escape sequence.
"""

import base64
import os
from typing import Literal

from movie_planner.store import Entry, Venue

TerminalImageProtocol = Literal["iterm2", "kitty"]

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_KITTY_CHUNK_SIZE = 4096


def detect_terminal_image_protocol() -> TerminalImageProtocol | None:
    # Ghostty implements the Kitty graphics protocol but identifies as
    # TERM=xterm-ghostty, not xterm-kitty, and sets neither
    # KITTY_WINDOW_ID nor TERM_PROGRAM.
    if os.environ.get("KITTY_WINDOW_ID") or os.environ.get("TERM") in (
        "xterm-kitty",
        "xterm-ghostty",
    ):
        return "kitty"
    if os.environ.get("TERM_PROGRAM") in ("iTerm.app", "WezTerm"):
        return "iterm2"
    return None


def render_poster(image_bytes: bytes, protocol: TerminalImageProtocol) -> str | None:
    if protocol == "iterm2":
        return _render_iterm2(image_bytes)
    if not image_bytes.startswith(_PNG_MAGIC):
        return None
    return _render_kitty(image_bytes)


def _render_iterm2(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"\033]1337;File=inline=1;size={len(image_bytes)}:{encoded}\a"


def _render_kitty(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    chunks = [encoded[i : i + _KITTY_CHUNK_SIZE] for i in range(0, len(encoded), _KITTY_CHUNK_SIZE)]
    parts = []
    for i, chunk in enumerate(chunks):
        more = 1 if i < len(chunks) - 1 else 0
        control = "a=T,f=100" if i == 0 else ""
        prefix = f"{control}," if control else ""
        parts.append(f"\033_G{prefix}m={more};{chunk}\033\\")
    return "".join(parts)


def format_entry(entry: Entry, *, medium_name: str, venue: Venue | None) -> str:
    lines = [f"{entry.title} ({entry.date})"]
    if entry.start_time and entry.end_time:
        lines.append(
            f"  {entry.start_time.isoformat(timespec='minutes')}"
            f"-{entry.end_time.isoformat(timespec='minutes')}"
        )
    elif entry.start_time:
        lines.append(f"  {entry.start_time.isoformat(timespec='minutes')}")
    location = f"  {medium_name}"
    if venue:
        location += f" @ {venue.name}"
        if venue.chain:
            location += f" ({venue.chain})"
        if venue.city:
            location += f" - {venue.city}"
            if venue.country:
                location += f", {venue.country}"
    lines.append(location)

    if entry.release_year:
        lines.append(f"  Year: {entry.release_year}")
    if entry.director:
        lines.append(f"  Director: {entry.director}")
    if entry.genre:
        lines.append(f"  Genre: {entry.genre}")
    if entry.actors:
        lines.append(f"  Cast: {entry.actors}")

    if entry.imdb_rating and entry.imdb_url:
        lines.append(f"  IMDb: {entry.imdb_rating} ({entry.imdb_url})")
    elif entry.imdb_rating:
        lines.append(f"  IMDb: {entry.imdb_rating}")
    elif entry.imdb_url:
        lines.append(f"  IMDb: {entry.imdb_url}")
    if entry.rotten_tomatoes_rating:
        lines.append(f"  Rotten Tomatoes: {entry.rotten_tomatoes_rating}")
    if entry.metacritic_rating:
        lines.append(f"  Metacritic: {entry.metacritic_rating}")
    if entry.letterboxd_url:
        suffix = f" ({entry.letterboxd_rating})" if entry.letterboxd_rating else ""
        lines.append(f"  Letterboxd: {entry.letterboxd_url}{suffix}")
    if entry.notes:
        lines.append(f"  Notes: {entry.notes}")

    return "\n".join(lines)
