"""The mail-fetch tool's own Typer app - entirely separate from
movie_planner.cli (design.md's "Same repo, new module, second
console-script entry point" decision). `movie-planner --help` never
mentions any of this.
"""

import getpass
import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from movie_planner.mail_import.config import (
    ImapSource,
    MailConfigError,
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
from movie_planner.mail_import.mbox_client import MboxMailClient

app = typer.Typer(help="Fetches cinema booking confirmations from a mailbox and emits import.json.")

_DEFAULT_CHAIN_SENDER_DOMAIN = "pathe.nl"
_DEFAULT_CHAIN_TRANSLATE = "pathe-translate"


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
        Path | None, typer.Option(help="Path to write config.toml. Defaults to the XDG location.")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing config file.")
    ] = False,
    source: Annotated[str | None, typer.Option(help='Mail source: "imap" or "mbox".')] = None,
    imap_host: Annotated[str | None, typer.Option(help="IMAP host.")] = None,
    imap_port: Annotated[int | None, typer.Option(help="IMAP port.")] = None,
    imap_username: Annotated[str | None, typer.Option(help="IMAP username.")] = None,
    imap_password_command: Annotated[
        str | None,
        typer.Option(
            help="Command to run for the IMAP password. The literal password is never "
            "accepted as a flag - only this, or a masked interactive prompt."
        ),
    ] = None,
    mbox_path: Annotated[Path | None, typer.Option(help="Path to a local mbox file.")] = None,
    chain_sender_domain: Annotated[
        str | None, typer.Option(help="Sender domain for the first configured chain.")
    ] = None,
    chain_translate: Annotated[
        str | None,
        typer.Option(help="Translation script command for the first configured chain."),
    ] = None,
) -> None:
    """Write a starter config.toml, ready to edit. Prompts for anything
    not given as a flag, unless running non-interactively (no TTY), in
    which case a missing required value fails clearly rather than
    hanging on a prompt that will never be answered.
    """
    config_path = config or default_config_path()
    if config_path.is_file() and not force:
        typer.secho(
            f"{config_path} already exists. Pass --force to overwrite it.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    interactive = _is_interactive()

    resolved_source = (
        source.strip().lower()
        if source
        else _required(
            None,
            prompt='Mail source ("imap" or "mbox")',
            flag="--source",
            interactive=interactive,
            default="imap",
        )
    )
    if resolved_source not in ("imap", "mbox"):
        typer.secho(
            f"--source must be 'imap' or 'mbox', got '{resolved_source}'", fg=typer.colors.RED
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

        source_block = f'[mail]\nsource = "imap"\n\n[mail.imap]\nhost = "{host}"\nport = {port}\nusername = "{username}"\n'
        source_block += (
            f'password_command = "{password_command}"\n'
            if password_command
            else f'password = "{password}"\n'
        )
    else:
        path = _required(
            str(mbox_path) if mbox_path else None,
            prompt="Path to the mbox file",
            flag="--mbox-path",
            interactive=interactive,
        )
        source_block = f'[mail]\nsource = "mbox"\n\n[mail.mbox]\npath = "{path}"\n'

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
    chains_block = f'\n[[chains]]\nsender_domain = "{sender_domain}"\ntranslate = "{translate}"\n'

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(source_block + chains_block)
    typer.echo(f"Wrote a starter config to {config_path}.")


def _build_client(source: ImapSource | MboxSource) -> MailClient:
    if isinstance(source, ImapSource):
        return ImapMailClient(
            host=source.host, port=source.port, username=source.username, password=source.password
        )
    return MboxMailClient(source.path)


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
        Path | None, typer.Option(help="Path to config.toml. Defaults to the XDG location.")
    ] = None,
    output: Annotated[Path, typer.Option(help="Where to write the import-ready JSON.")] = Path(
        "import.json"
    ),
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

    client = _build_client(cfg.source)
    domains = [chain.sender_domain for chain in cfg.chains]
    try:
        raw_messages = list(client.fetch(domains))
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
