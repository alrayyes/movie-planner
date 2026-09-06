"""Merge-safe TOML section reads/writes, for movie-planner and
pathe-mail-import sharing one config file (issue #157): a read-modify-
write that preserves whatever's already in the file - comments, other
tools' sections - instead of overwriting it whole. `content` is a
self-contained TOML fragment naming its own top-level table(s), e.g.
`[movie_planner]\\ncaldav_url = "..."\\n` - what gets merged in is
whatever top-level keys that fragment defines.
"""

from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError


class ConfigFileError(Exception):
    """Raised when the config file exists but isn't valid TOML. The
    message is shown to the user as-is.
    """


def _read(path: Path) -> tomlkit.TOMLDocument:
    try:
        return tomlkit.parse(path.read_text())
    except ParseError as e:
        raise ConfigFileError(f"{path} is not valid TOML: {e}") from e


def has_section(path: Path, section: str) -> bool:
    """True when `path` exists and already defines a top-level
    `section` table - the signal a tool's own `init` uses to tell
    "nothing here yet" from "the other tool already wrote its part".
    """
    if not path.is_file():
        return False
    return section in _read(path)


def write_section(path: Path, content: str) -> None:
    """Merges `content`'s top-level keys into the TOML file at `path`,
    preserving every other top-level key already there. Creates the
    file (and its parent directory) if it doesn't exist yet.
    """
    doc = _read(path) if path.is_file() else tomlkit.document()
    for key, value in tomlkit.parse(content).items():
        doc[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(doc))
