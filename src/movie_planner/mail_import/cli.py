"""The mail-fetch tool's own Typer app - entirely separate from
movie_planner.cli (design.md's "Same repo, new module, second
console-script entry point" decision). `movie-planner --help` never
mentions any of this.
"""

import getpass
import sys
from pathlib import Path
from typing import Annotated

import typer

from movie_planner.mail_import.config import default_config_path

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


def main() -> None:
    app()
