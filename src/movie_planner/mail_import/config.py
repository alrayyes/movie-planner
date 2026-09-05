"""Loads the mail-fetch tool's own TOML config - entirely separate from
movie-planner's own config.toml (design.md's "doesn't concern itself
with the main command" boundary). Same password/password_command split
movie-planner's own CalDAV credential already uses.
"""

import os
import shlex

# password_command intentionally shells out, same as movie_planner.config.
import subprocess  # nosec B404
import tomllib
from dataclasses import dataclass
from pathlib import Path


class MailConfigError(Exception):
    """Raised for anything wrong with the config file - missing file,
    invalid TOML, or a missing/invalid required key. The message is
    shown to the user as-is.
    """


@dataclass(frozen=True)
class ImapSource:
    host: str
    port: int
    username: str
    password: str


@dataclass(frozen=True)
class MboxSource:
    path: Path


@dataclass(frozen=True)
class ChainConfig:
    sender_domain: str
    translate: str


@dataclass(frozen=True)
class MailImportConfig:
    source: ImapSource | MboxSource
    chains: tuple[ChainConfig, ...]


def default_config_path() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(xdg_config_home).expanduser() / "pathe-mail-import" / "config.toml"


def _require(table: dict[str, object], key: str, dotted_path: str) -> object:
    if key not in table:
        raise MailConfigError(f"config is missing required key '{dotted_path}'")
    return table[key]


def _require_table(data: dict[str, object], key: str) -> dict[str, object]:
    value = _require(data, key, key)
    if not isinstance(value, dict):
        raise MailConfigError(f"config's '{key}' section must be a table")
    return value


def _resolve_password(imap: dict[str, object]) -> str:
    has_password = "password" in imap
    has_command = "password_command" in imap

    if has_password and has_command:
        raise MailConfigError(
            "config sets both 'imap.password' and 'imap.password_command' - use only one"
        )
    if has_command:
        command = str(imap["password_command"])
        try:
            # No shell=True; command is user-configured, not untrusted input.
            result = subprocess.run(  # nosec B603
                shlex.split(command),
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as e:
            raise MailConfigError(f"imap.password_command failed: {e}") from e
        return result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
    if has_password:
        return str(imap["password"])
    raise MailConfigError(
        "config is missing required key 'imap.password' (or 'imap.password_command')"
    )


def _load_source(data: dict[str, object]) -> ImapSource | MboxSource:
    mail = _require_table(data, "mail")
    source_kind = str(_require(mail, "source", "mail.source"))

    if source_kind == "imap":
        imap = _require_table(mail, "imap")
        return ImapSource(
            host=str(_require(imap, "host", "mail.imap.host")),
            port=int(str(_require(imap, "port", "mail.imap.port"))),
            username=str(_require(imap, "username", "mail.imap.username")),
            password=_resolve_password(imap),
        )
    if source_kind == "mbox":
        mbox = _require_table(mail, "mbox")
        return MboxSource(
            path=Path(str(_require(mbox, "path", "mail.mbox.path"))).expanduser(),
        )
    raise MailConfigError(f"mail.source must be 'imap' or 'mbox', got '{source_kind}'")


def _load_chains(data: dict[str, object]) -> tuple[ChainConfig, ...]:
    raw_chains = data.get("chains", [])
    if not isinstance(raw_chains, list) or not raw_chains:
        raise MailConfigError("config needs at least one [[chains]] entry")
    chains = []
    for i, raw in enumerate(raw_chains):
        if not isinstance(raw, dict):
            raise MailConfigError(f"chains[{i}] must be a table")
        chains.append(
            ChainConfig(
                sender_domain=str(_require(raw, "sender_domain", f"chains[{i}].sender_domain")),
                translate=str(_require(raw, "translate", f"chains[{i}].translate")),
            )
        )
    return tuple(chains)


def load_config(path: Path | None = None) -> MailImportConfig:
    config_path = path or default_config_path()

    if not config_path.is_file():
        raise MailConfigError(f"no config file found at {config_path}")

    try:
        with config_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise MailConfigError(f"{config_path} is not valid TOML: {e}") from e

    return MailImportConfig(source=_load_source(data), chains=_load_chains(data))
