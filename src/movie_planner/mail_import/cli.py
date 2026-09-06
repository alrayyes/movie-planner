"""The mail-fetch tool's own Typer app - entirely separate from
movie_planner.cli (design.md's "Same repo, new module, second
console-script entry point" decision). `movie-planner --help` never
mentions any of this.
"""

import getpass
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from movie_planner import config_file
from movie_planner.mail_import.config import (
    ImapSource,
    MailConfigError,
    MaildirSource,
    MboxSource,
    default_config_path,
    load_config,
)
from movie_planner.mail_import.dispatch import dispatch_all
from movie_planner.mail_import.envelope import (
    MailClient,
    MailEnvelope,
    MailFetchError,
    envelope_to_json,
    extract_envelope,
)
from movie_planner.mail_import.imap_client import ImapMailClient
from movie_planner.mail_import.maildir_client import MaildirMailClient
from movie_planner.mail_import.mbox_client import MboxMailClient

app = typer.Typer(help="Fetches cinema booking confirmations from a mailbox and emits import.json.")

_DEFAULT_CHAIN_SENDER_DOMAIN = "service.pathe.nl"
_DEFAULT_CHAIN_TRANSLATE = "pathe-translate"

_RELATIVE_TIME_RE = re.compile(
    r"^(?P<amount>\d+)\s+(?P<unit>second|minute|hour|day|week)s?\s+ago$", re.IGNORECASE
)
_UNIT_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800}


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_time_bound(value: str, *, flag: str) -> datetime:
    """Accepts '<N> <unit> ago' (seconds/minutes/hours/days/weeks) for a
    cron job's own relative window, or an ISO 8601 date/datetime for an
    absolute one - naive ISO values are treated as UTC.
    """
    match = _RELATIVE_TIME_RE.match(value.strip())
    if match:
        seconds = int(match["amount"]) * _UNIT_SECONDS[match["unit"].lower()]
        return _now() - timedelta(seconds=seconds)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as e:
        typer.secho(
            f"Could not parse {flag} value '{value}' - use '<N> <unit> ago' "
            "(seconds/minutes/hours/days/weeks) or an ISO 8601 date/datetime.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from e
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _required(
    value: str | None, *, prompt: str, flag: str, interactive: bool, default: str | None = None
) -> str:
    if value:
        return value
    if interactive:
        answer = (
            typer.prompt(prompt, default=default) if default is not None else typer.prompt(prompt)
        )
        return str(answer)
    if default is not None:
        return default
    typer.secho(
        f"No {flag} given and not running interactively; pass {flag} explicitly.",
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=1)


def _resolve_password(
    password_command: str | None, *, interactive: bool
) -> tuple[str | None, str | None]:
    """Returns (password, password_command) - exactly one is set. The
    literal password is never accepted as a CLI flag (design.md's IMAP-
    password decision) - only a password command, or a masked
    interactive prompt.
    """
    if password_command:
        return None, password_command
    if not interactive:
        typer.secho(
            "No --imap-password-command given and not running interactively; pass it "
            "explicitly (the literal password is never accepted as a flag).",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    use_command = typer.confirm(
        "Use a password command (e.g. a password manager CLI) instead of typing the password?",
        default=False,
    )
    if use_command:
        return None, typer.prompt("Password command")
    return getpass.getpass("IMAP password (not echoed): "), None


@app.command()
def init(
    config: Annotated[
        Path | None,
        typer.Option(
            help="Path to write config.toml. Defaults to the XDG location "
            "($XDG_CONFIG_HOME/pathe-mail-import/config.toml, or "
            "~/.config/pathe-mail-import/config.toml if that's unset). Point this at the "
            "same path as movie-planner's own config to share one file (issue #157)."
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite the whole file, including any [movie_planner] section "
            "movie-planner already wrote there. Without --force, adding this tool's own "
            "[mail_import] section to a file that already has one is refused rather than "
            "silently replacing it - --force is the explicit 'yes, start over' for that.",
        ),
    ] = False,
    source: Annotated[
        str | None,
        typer.Option(
            help='Mail source: "imap" (a real mailbox, fetched live over the network), '
            '"mbox" (a local mbox-format file - mutt\'s own storage, or a Thunderbird '
            'local folder, which is also plain mbox), or "maildir" (a local Maildir '
            "directory - one file per message under cur/new/tmp, mutt's own default "
            "local sync format, and not readable by --source mbox even with extra_paths). "
            "Prompted for interactively if omitted."
        ),
    ] = None,
    imap_host: Annotated[
        str | None, typer.Option(help="IMAP server hostname or IP. Required for --source imap.")
    ] = None,
    imap_port: Annotated[
        int | None,
        typer.Option(help="IMAP server port. Defaults to 993 (implicit TLS) if left blank."),
    ] = None,
    imap_username: Annotated[
        str | None, typer.Option(help="IMAP login username. Required for --source imap.")
    ] = None,
    imap_password_command: Annotated[
        str | None,
        typer.Option(
            help="Command to run for the IMAP password, printing it to stdout - a password "
            "manager CLI, for example. The literal password is never accepted as a flag "
            "(it would leak into shell history and the process list) - only this, or a "
            "masked interactive prompt when running in a terminal."
        ),
    ] = None,
    mbox_path: Annotated[
        Path | None,
        typer.Option(
            help="Path to a local mbox file (INBOX, typically). Required for --source mbox. "
            "A second config edit can add mail.mbox.extra_paths afterward to also scan an "
            "Archive folder or similar (issue #188) - not offered as an init prompt, since "
            "most setups only need the one file."
        ),
    ] = None,
    maildir_path: Annotated[
        Path | None,
        typer.Option(
            help="Path to a Maildir directory (the folder containing cur/new/tmp, not one "
            "of those subfolders itself). Required for --source maildir."
        ),
    ] = None,
    chain_sender_domain: Annotated[
        str | None,
        typer.Option(
            help="Sender domain for the first configured chain - only email from this "
            "domain is fetched and handed to --chain-translate. Real Pathé confirmations "
            "come from service.pathe.nl specifically, not the bare pathe.nl domain (other "
            "Pathé mail - the newsletter, a membership invoice - uses other subdomains and "
            "is correctly left unrecognized by a chain scoped this narrowly)."
        ),
    ] = None,
    chain_translate: Annotated[
        str | None,
        typer.Option(
            help="Translation script command for the first configured chain - reads one "
            "JSON envelope per line on stdin, writes one import.json row per line on "
            "stdout for anything it recognizes. pathe-translate (installed alongside this "
            "tool) is the only one that ships today."
        ),
    ] = None,
) -> None:
    """Write a starter config.toml, ready to edit. Prompts for anything
    not given as a flag, unless running non-interactively (no TTY), in
    which case a missing required value fails clearly rather than
    hanging on a prompt that will never be answered. Sharing the file
    with movie-planner (issue #157): if it already exists but has no
    [mail_import] section yet - e.g. movie-planner already wrote its
    own [movie_planner] section there - this adds this tool's section
    alongside it, no --force needed.
    """
    config_path = config or default_config_path()
    if config_path.is_file() and not force:
        try:
            already_configured = config_file.has_section(config_path, "mail_import")
        except config_file.ConfigFileError:
            already_configured = True  # unreadable existing content - don't guess, don't clobber
        if already_configured:
            typer.secho(
                f"{config_path} already exists. Pass --force to overwrite it.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

    interactive = _is_interactive()

    resolved_source = (
        source.strip().lower()
        if source
        else _required(
            None,
            prompt='Mail source ("imap", "mbox" or "maildir")',
            flag="--source",
            interactive=interactive,
            default="imap",
        )
    )
    if resolved_source not in ("imap", "mbox", "maildir"):
        typer.secho(
            f"--source must be 'imap', 'mbox' or 'maildir', got '{resolved_source}'",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    if resolved_source == "imap":
        host = _required(imap_host, prompt="IMAP host", flag="--imap-host", interactive=interactive)
        port = (
            str(imap_port)
            if imap_port is not None
            else _required(
                None, prompt="IMAP port", flag="--imap-port", interactive=interactive, default="993"
            )
        )
        username = _required(
            imap_username, prompt="IMAP username", flag="--imap-username", interactive=interactive
        )
        password, password_command = _resolve_password(
            imap_password_command, interactive=interactive
        )

        source_block = (
            f'[mail_import.mail]\nsource = "imap"\n\n[mail_import.mail.imap]\n'
            f'host = "{host}"\nport = {port}\nusername = "{username}"\n'
        )
        source_block += (
            f'password_command = "{password_command}"\n'
            if password_command
            else f'password = "{password}"\n'
        )
    elif resolved_source == "mbox":
        path = _required(
            str(mbox_path) if mbox_path else None,
            prompt="Path to the mbox file",
            flag="--mbox-path",
            interactive=interactive,
        )
        source_block = (
            f'[mail_import.mail]\nsource = "mbox"\n\n[mail_import.mail.mbox]\npath = "{path}"\n'
        )
    else:
        path = _required(
            str(maildir_path) if maildir_path else None,
            prompt="Path to the Maildir directory",
            flag="--maildir-path",
            interactive=interactive,
        )
        source_block = (
            f'[mail_import.mail]\nsource = "maildir"\n\n'
            f'[mail_import.mail.maildir]\npath = "{path}"\n'
        )

    sender_domain = chain_sender_domain or _required(
        None,
        prompt="First chain's sender domain",
        flag="--chain-sender-domain",
        interactive=interactive,
        default=_DEFAULT_CHAIN_SENDER_DOMAIN,
    )
    translate = chain_translate or _required(
        None,
        prompt="First chain's translation command",
        flag="--chain-translate",
        interactive=interactive,
        default=_DEFAULT_CHAIN_TRANSLATE,
    )
    chains_block = (
        f'\n[[mail_import.chains]]\nsender_domain = "{sender_domain}"\ntranslate = "{translate}"\n'
    )

    if force:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(source_block + chains_block)
    else:
        config_file.write_section(config_path, source_block + chains_block)
    typer.echo(f"Wrote a starter config to {config_path}.")


def _build_client(source: ImapSource | MboxSource | MaildirSource) -> MailClient:
    if isinstance(source, ImapSource):
        return ImapMailClient(
            host=source.host, port=source.port, username=source.username, password=source.password
        )
    if isinstance(source, MaildirSource):
        return MaildirMailClient(source.path)
    return MboxMailClient(source.path, extra_paths=source.extra_paths)


def _print_review_table(envelopes: list[MailEnvelope]) -> None:
    rows = [(e.from_address, e.subject, e.date.date().isoformat()) for e in envelopes]
    headers = ("From", "Subject", "Date")
    widths = [max(len(row[i]) for row in [headers, *rows]) for i in range(3)]

    def _line(row: tuple[str, str, str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True))

    typer.echo(_line(headers))
    typer.echo(_line(tuple("-" * w for w in widths)))  # type: ignore[arg-type]
    for row in rows:
        typer.echo(_line(row))


@app.command()
def fetch(
    config: Annotated[
        Path | None,
        typer.Option(
            help="Path to config.toml. Defaults to the XDG location "
            "($XDG_CONFIG_HOME/pathe-mail-import/config.toml)."
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            help="Where to write the import-ready JSON - feed this straight to "
            "'movie-planner import <file>' afterward. Ignored with --envelopes-only."
        ),
    ] = Path("import.json"),
    envelopes_only: Annotated[
        bool,
        typer.Option(
            "--envelopes-only",
            help="Print each fetched message as one JSON envelope per line on stdout "
            "instead of dispatching and writing --output - for composing by hand as "
            "`fetch --envelopes-only | pathe-translate | movie-planner import` instead "
            "of running this as one self-contained command.",
        ),
    ] = False,
    since: Annotated[
        str | None,
        typer.Option(
            help="Only fetch messages from after this time - '<N> <unit> ago' "
            "(seconds/minutes/hours/days/weeks) or an ISO 8601 date/datetime. "
            "For scoping a cron job to its own window."
        ),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option(help="Only fetch messages from before this time - same format as --since."),
    ] = None,
) -> None:
    """Fetches every configured chain's booking confirmations from the
    configured mail source and writes them to --output as import-ready
    JSON. An email no configured chain's translation script recognizes
    is shown in a review table instead - never written to --output.
    """
    config_path = config or default_config_path()
    try:
        cfg = load_config(config_path)
    except MailConfigError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e

    since_dt = _parse_time_bound(since, flag="--since") if since else None
    until_dt = _parse_time_bound(until, flag="--until") if until else None

    client = _build_client(cfg.source)
    domains = [chain.sender_domain for chain in cfg.chains]
    try:
        raw_messages = list(client.fetch(domains, since=since_dt, until=until_dt))
    except MailFetchError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e

    envelopes: list[MailEnvelope] = []
    for raw in raw_messages:
        try:
            envelopes.append(extract_envelope(raw))
        except MailFetchError:
            # Not even a well-formed email - nothing to show in a
            # from/subject/date review table, so it's dropped rather
            # than reported.
            continue

    if envelopes_only:
        for envelope in envelopes:
            typer.echo(json.dumps(envelope_to_json(envelope)))
        return

    rows, unrecognized = dispatch_all(envelopes, cfg.chains)

    output.write_text(json.dumps(rows, indent=2))
    typer.echo(f"Wrote {len(rows)} row(s) to {output}.")

    if unrecognized:
        typer.echo("")
        typer.echo(f"{len(unrecognized)} email(s) not recognized by any configured chain:")
        _print_review_table(unrecognized)


def main() -> None:
    app()
