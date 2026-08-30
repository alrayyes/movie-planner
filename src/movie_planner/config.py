"""Loads the TOML config: CalDAV credentials, the OMDb API key, and the
local SQLite database path. See design.md's "Config" decision.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    """Raised for anything wrong with the config file - missing file,
    invalid TOML, or a missing required key. The message is shown to the
    user as-is, so it names the file and the problem in plain language.
    """


@dataclass(frozen=True)
class Config:
    caldav_url: str
    caldav_username: str
    caldav_password: str
    omdb_api_key: str
    db_path: Path


def default_config_path() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(xdg_config_home).expanduser() / "movie-planner" / "config.toml"


def _require(table: dict, key: str, dotted_path: str) -> object:
    if key not in table:
        raise ConfigError(f"config is missing required key '{dotted_path}'")
    return table[key]


def load_config(path: Path | None = None) -> Config:
    config_path = path or default_config_path()

    if not config_path.is_file():
        raise ConfigError(f"no config file found at {config_path}")

    try:
        with config_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{config_path} is not valid TOML: {e}") from e

    caldav = _require(data, "caldav", "caldav")
    omdb = _require(data, "omdb", "omdb")
    storage = _require(data, "storage", "storage")

    return Config(
        caldav_url=str(_require(caldav, "url", "caldav.url")),
        caldav_username=str(_require(caldav, "username", "caldav.username")),
        caldav_password=str(_require(caldav, "password", "caldav.password")),
        omdb_api_key=str(_require(omdb, "api_key", "omdb.api_key")),
        db_path=Path(str(_require(storage, "db_path", "storage.db_path"))).expanduser(),
    )
