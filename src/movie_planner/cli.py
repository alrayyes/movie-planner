"""The Typer app wiring every capability (movie-log, calendar-sync,
metadata, duplicate-detection, import) into commands.
"""

import dataclasses
import re
import sys
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Annotated

import httpx
import typer

from movie_planner import config as config_module
from movie_planner.calendar_sync import CalendarClient, CalendarSync
from movie_planner.display import detect_terminal_image_protocol, format_entry, render_poster
from movie_planner.duplicates import find_duplicate
from movie_planner.importers import parse_csv, parse_json, run_import
from movie_planner.omdb import OmdbClient, fetch_and_store_ratings
from movie_planner.pathe import PatheBooking, PatheEmailParseError, parse_pathe_email
from movie_planner.store import Entry, Store, StoreError

app = typer.Typer(help="movie-planner: log watched movies and sync them to a calendar.")
locations_app = typer.Typer(help="Manage the medium and venue lists.")
media_app = typer.Typer(help="Manage the medium list.")
venues_app = typer.Typer(help="Manage the venue list.")
sync_app = typer.Typer(help="Manage calendar sync.")
locations_app.add_typer(media_app, name="media")
locations_app.add_typer(venues_app, name="venues")
app.add_typer(locations_app, name="locations")
app.add_typer(sync_app, name="sync")


@dataclass(frozen=True)
class _ConfigOverrides:
    """Flags/env vars that override the config file for one invocation —
    every field except the CalDAV password, which stays config-file-only
    (via `caldav.password` or `caldav.password_command`) rather than risk
    landing in shell history or a process list.
    """

    config_path: Path | None
    caldav_url: str | None = None
    caldav_username: str | None = None
    omdb_api_key: str | None = None
    db_path: Path | None = None


# Click derives each env var from its option name under this prefix, e.g.
# --caldav-url becomes MOVIE_PLANNER_CALDAV_URL. rules/cli.md: flags >
# environment variables > config file > built-in defaults.
@app.callback(context_settings={"auto_envvar_prefix": "MOVIE_PLANNER"})
def callback(
    ctx: typer.Context,
    config: Annotated[
        Path | None,
        typer.Option(help="Path to config.toml. Defaults to the XDG config location."),
    ] = None,
    caldav_url: Annotated[
        str | None, typer.Option(help="Override caldav.url from the config file.")
    ] = None,
    caldav_username: Annotated[
        str | None, typer.Option(help="Override caldav.username from the config file.")
    ] = None,
    omdb_api_key: Annotated[
        str | None, typer.Option(help="Override omdb.api_key from the config file.")
    ] = None,
    db_path: Annotated[
        Path | None, typer.Option(help="Override storage.db_path from the config file.")
    ] = None,
) -> None:
    """movie-planner: log watched movies and sync them to a calendar."""
    # Stores the raw overrides rather than loading the config here: loading
    # eagerly in the group callback runs even for `movie-planner <command>
    # --help`, so a missing config file would break --help itself.
    ctx.obj = _ConfigOverrides(
        config_path=config,
        caldav_url=caldav_url,
        caldav_username=caldav_username,
        omdb_api_key=omdb_api_key,
        db_path=db_path,
    )


_STARTER_CONFIG = """\
[caldav]
url = "https://baikal.example.com/dav.php/calendars/moviewatcher/movies/"
username = "moviewatcher"
password = "..."
# Or, instead of a plaintext password above, run a command that prints
# it to stdout (e.g. a password manager) - set only one of the two:
# password_command = "pass show caldav/movie-planner"

[omdb]
api_key = "..."

[storage]
db_path = "~/.local/share/movie-planner/movies.db"
"""


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _confirm_via_tty(message: str) -> bool:
    """Reads a yes/no confirmation from the controlling terminal directly,
    for when stdin is occupied by piped content (a piped email). See
    design.md's "Confirmation reads from /dev/tty" decision.
    """
    try:
        with open("/dev/tty") as tty_in, open("/dev/tty", "w") as tty_out:
            tty_out.write(f"{message} [y/N] ")
            tty_out.flush()
            answer = tty_in.readline()
    except OSError as e:
        typer.secho(
            "No controlling terminal available to confirm. Pass --yes to skip confirmation.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from e
    return answer.strip().lower() in ("y", "yes")


def _confirm(message: str, *, from_stdin: bool) -> bool:
    if from_stdin:
        return _confirm_via_tty(message)
    return typer.confirm(message)


def _write_starter_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_STARTER_CONFIG)


def _apply_overrides(
    cfg: config_module.Config, overrides: _ConfigOverrides
) -> config_module.Config:
    return dataclasses.replace(
        cfg,
        caldav_url=overrides.caldav_url or cfg.caldav_url,
        caldav_username=overrides.caldav_username or cfg.caldav_username,
        omdb_api_key=overrides.omdb_api_key or cfg.omdb_api_key,
        db_path=overrides.db_path or cfg.db_path,
    )


def _cfg(ctx: typer.Context) -> config_module.Config:
    overrides: _ConfigOverrides = ctx.obj
    config_path = overrides.config_path or config_module.default_config_path()

    if not config_path.is_file():
        if _is_interactive() and typer.confirm(
            f"No config file found at {config_path}. Create a starter one now?",
            default=True,
        ):
            _write_starter_config(config_path)
            typer.echo(
                f"Wrote a starter config to {config_path}. Edit it with your CalDAV "
                "credentials and OMDb API key, then run this command again."
            )
        else:
            typer.secho(
                f"No config file found at {config_path}. "
                "Run 'movie-planner init' to create a starter one.",
                fg=typer.colors.RED,
                err=True,
            )
        raise typer.Exit(code=1)

    try:
        cfg = config_module.load_config(config_path)
    except config_module.ConfigError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    return _apply_overrides(cfg, overrides)


@app.command()
def init(
    ctx: typer.Context,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing config file.")
    ] = False,
) -> None:
    """Write a starter config.toml, ready to edit."""
    overrides: _ConfigOverrides = ctx.obj
    config_path = overrides.config_path or config_module.default_config_path()
    if config_path.is_file() and not force:
        typer.secho(
            f"{config_path} already exists. Pass --force to overwrite it.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    _write_starter_config(config_path)
    typer.echo(
        f"Wrote a starter config to {config_path}. Edit it with your CalDAV "
        "credentials and OMDb API key before running any other command."
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise typer.BadParameter(f"'{value}' is not a valid date (expected YYYY-MM-DD)") from e


def _parse_time(value: str | None) -> time | None:
    if value is None:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError as e:
        raise typer.BadParameter(f"'{value}' is not a valid time (expected HH:MM)") from e


def _open_store(cfg: config_module.Config) -> Store:
    return Store(cfg.db_path)


def _connect_calendar(cfg: config_module.Config) -> CalendarClient:
    return CalendarClient.connect(
        url=cfg.caldav_url, username=cfg.caldav_username, password=cfg.caldav_password
    )


def _push_new_or_warn(
    cfg: config_module.Config,
    store: Store,
    entry: Entry,
    *,
    venue: str | None,
    screening_details: str | None = None,
) -> Entry:
    try:
        client = _connect_calendar(cfg)
        return CalendarSync(store, client).push_new(
            entry, venue=venue, screening_details=screening_details
        )
    except Exception as e:  # noqa: BLE001 - any connect/push failure is a warning
        typer.secho(
            f"Warning: could not sync '{entry.title}' to the calendar: {e}",
            fg=typer.colors.YELLOW,
        )
        return entry


def _push_update_or_warn(
    cfg: config_module.Config,
    store: Store,
    entry: Entry,
    *,
    venue: str | None,
    screening_details: str | None = None,
) -> None:
    if entry.caldav_uid is None:
        return
    try:
        client = _connect_calendar(cfg)
        CalendarSync(store, client).push_update(
            entry, venue=venue, screening_details=screening_details
        )
    except Exception as e:  # noqa: BLE001
        typer.secho(
            f"Warning: could not sync the update to '{entry.title}' to the calendar: {e}",
            fg=typer.colors.YELLOW,
        )


def _finalize_entry(
    cfg: config_module.Config,
    store: Store,
    entry: Entry,
    *,
    venue: str | None,
    fetch_metadata: bool,
    imdb_id: str | None = None,
    screening_details: str | None = None,
) -> Entry:
    """Metadata fetch (optional), then a calendar push - create if the
    entry has never been synced, update otherwise. The one orchestration
    sequence shared by every command that ends with "an entry now
    exists/changed locally, make the calendar agree" - see design.md's
    "One shared orchestration helper" decision.
    """
    if fetch_metadata:
        entry = _fetch_metadata_or_warn(cfg, store, entry, imdb_id=imdb_id)
    if entry.caldav_uid is None:
        return _push_new_or_warn(
            cfg, store, entry, venue=venue, screening_details=screening_details
        )
    _push_update_or_warn(cfg, store, entry, venue=venue, screening_details=screening_details)
    return entry


def _push_delete_or_warn(cfg: config_module.Config, store: Store, entry: Entry) -> None:
    if entry.caldav_uid is None:
        return
    try:
        client = _connect_calendar(cfg)
        CalendarSync(store, client).push_delete(entry)
    except Exception as e:  # noqa: BLE001
        typer.secho(
            f"Warning: could not remove '{entry.title}' from the calendar: {e}",
            fg=typer.colors.YELLOW,
        )


def _fetch_metadata_or_warn(
    cfg: config_module.Config, store: Store, entry: Entry, *, imdb_id: str | None
) -> Entry:
    try:
        client = OmdbClient(cfg.omdb_api_key)
        updated, matched = fetch_and_store_ratings(store, client, entry, imdb_id=imdb_id)
    except Exception as e:  # noqa: BLE001 - metadata is optional, never fatal
        typer.secho(f"Warning: could not fetch ratings: {e}", fg=typer.colors.YELLOW)
        return entry
    if not matched:
        typer.echo(f"No OMDb match found for '{entry.title}'.")
    return updated


def _venue_name(store: Store, entry: Entry) -> str | None:
    if entry.venue_id is None:
        return None
    venue = next((v for v in store.list_venues() if v.id == entry.venue_id), None)
    return venue.name if venue else None


# --- log: requirement "Log a watched movie interactively" ---


@app.command()
def log(
    ctx: typer.Context,
    title: Annotated[str | None, typer.Option(help="Movie title.")] = None,
    entry_date: Annotated[
        str | None, typer.Option("--date", help="Date watched (YYYY-MM-DD).")
    ] = None,
    start_time: Annotated[str | None, typer.Option(help="Start time (HH:MM).")] = None,
    end_time: Annotated[str | None, typer.Option(help="End time (HH:MM).")] = None,
    medium: Annotated[str | None, typer.Option(help="Medium (e.g. cinema, netflix).")] = None,
    venue: Annotated[
        str | None, typer.Option(help="Venue - only meaningful for a physical medium.")
    ] = None,
    imdb_id: Annotated[str | None, typer.Option(help="IMDb ID for a precise OMDb lookup.")] = None,
    letterboxd_url: Annotated[
        str | None, typer.Option(help="Manually entered Letterboxd URL.")
    ] = None,
    letterboxd_rating: Annotated[
        str | None, typer.Option(help="Manually entered Letterboxd rating.")
    ] = None,
    notes: Annotated[str | None, typer.Option(help="Personal notes about the viewing.")] = None,
    no_metadata: Annotated[
        bool, typer.Option("--no-metadata", help="Skip the OMDb lookup.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Log even if it looks like a duplicate.")
    ] = False,
) -> None:
    """Interactively log a watched movie."""
    cfg = _cfg(ctx)
    interactive = _is_interactive()

    if title is None and interactive:
        title = typer.prompt("Title")
    if not title:
        typer.secho("Title is required (pass --title, or run interactively).", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if entry_date is None and interactive:
        entry_date = typer.prompt("Date (YYYY-MM-DD)")
    if not entry_date:
        typer.secho("Date is required (pass --date, or run interactively).", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    parsed_date = _parse_date(entry_date)

    parsed_start = _parse_time(start_time)
    parsed_end = _parse_time(end_time)

    if medium is None and interactive:
        medium = typer.prompt("Medium")
    if not medium:
        typer.secho(
            "Medium is required (pass --medium, or run interactively).", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    if venue is None and interactive and medium.strip():
        venue = (
            typer.prompt("Venue (blank if not applicable)", default="", show_default=False) or None
        )

    store = _open_store(cfg)
    try:
        duplicate = find_duplicate(title, parsed_date, store.list_entries())
        if duplicate is not None and not force:
            if interactive:
                confirmed = typer.confirm(
                    f"'{title}' looks like a duplicate of '{duplicate.title}' "
                    f"logged {duplicate.date}. Add anyway?"
                )
                if not confirmed:
                    typer.echo("Not added.")
                    raise typer.Exit(code=1)
            else:
                typer.secho(
                    f"'{title}' looks like a duplicate of '{duplicate.title}' logged "
                    f"{duplicate.date}. Re-run with --force to add it anyway.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)

        medium_row = store.get_or_create_medium(medium, is_physical_place=venue is not None)
        venue_row = store.get_or_create_venue(venue) if venue else None
        entry = store.create_entry(
            title=title,
            date=parsed_date,
            medium_id=medium_row.id,
            start_time=parsed_start,
            end_time=parsed_end,
            venue_id=venue_row.id if venue_row else None,
        )

        if letterboxd_url or letterboxd_rating:
            entry = store.update_entry(
                entry.id, letterboxd_url=letterboxd_url, letterboxd_rating=letterboxd_rating
            )

        if notes:
            entry = store.update_entry(entry.id, notes=notes)

        entry = _finalize_entry(
            cfg, store, entry, venue=venue, fetch_metadata=not no_metadata, imdb_id=imdb_id
        )

        typer.echo(f"Logged '{title}' as entry {entry.id}.")
    finally:
        store.close()


# --- list: requirement "List logged entries" ---


@app.command(name="list")
def list_entries(
    ctx: typer.Context,
    date_from: Annotated[
        str | None, typer.Option("--from", help="Only entries on or after this date.")
    ] = None,
    date_to: Annotated[
        str | None, typer.Option("--to", help="Only entries on or before this date.")
    ] = None,
    medium: Annotated[str | None, typer.Option(help="Only entries with this medium.")] = None,
) -> None:
    """List logged entries."""
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        media_by_id = {m.id: m for m in store.list_media()}
        venues_by_id = {v.id: v for v in store.list_venues()}
        medium_id = None
        if medium is not None:
            match = next((m for m in media_by_id.values() if m.name == medium), None)
            if match is None:
                typer.echo("No entries.")
                return
            medium_id = match.id

        entries = store.list_entries(
            date_from=_parse_date(date_from) if date_from else None,
            date_to=_parse_date(date_to) if date_to else None,
            medium_id=medium_id,
        )
        if not entries:
            typer.echo("No entries.")
            return
        for entry in entries:
            medium_name = media_by_id[entry.medium_id].name
            venue_name = venues_by_id[entry.venue_id].name if entry.venue_id else None
            line = f"{entry.id}  {entry.date}  {entry.title}  [{medium_name}]"
            if venue_name:
                line += f" @ {venue_name}"
            typer.echo(line)
    finally:
        store.close()


# --- show: issue #106, structured single-entry output with an inline poster ---

_IMDB_ID_RE = re.compile(r"(tt\d+)")


def _fetch_poster_bytes(url: str) -> bytes:
    response = httpx.get(url, follow_redirects=True, timeout=10)
    response.raise_for_status()
    return response.content


def _poster_url_for(cfg: config_module.Config, entry: Entry) -> str | None:
    if not entry.imdb_url:
        return None
    match = _IMDB_ID_RE.search(entry.imdb_url)
    if match is None:
        return None
    client = OmdbClient(cfg.omdb_api_key)
    ratings = client.lookup(imdb_id=match.group(1))
    return ratings.poster if ratings else None


@app.command()
def show(
    ctx: typer.Context,
    entry_id: Annotated[int, typer.Argument(help="ID of the entry to show.")],
) -> None:
    """Show one logged entry's full metadata, with the poster rendered
    inline where the terminal supports it (iTerm2/WezTerm or Kitty/Ghostty
    - see display.py for why Sixel and JPEG-on-Kitty aren't covered).
    """
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        try:
            entry = store.get_entry(entry_id)
        except StoreError as e:
            typer.secho(str(e), fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

        media_by_id = {m.id: m for m in store.list_media()}
        venues_by_id = {v.id: v for v in store.list_venues()}
        medium_name = media_by_id[entry.medium_id].name
        venue_name = venues_by_id[entry.venue_id].name if entry.venue_id else None
        typer.echo(format_entry(entry, medium_name=medium_name, venue_name=venue_name))

        protocol = detect_terminal_image_protocol()
        if protocol is None:
            return
        poster_url = _poster_url_for(cfg, entry)
        if poster_url is None:
            return
        try:
            image_bytes = _fetch_poster_bytes(poster_url)
        except httpx.HTTPError:
            return
        rendered = render_poster(image_bytes, protocol)
        if rendered:
            typer.echo(rendered)
    finally:
        store.close()


# --- update: requirement "Update a logged entry" ---


@app.command()
def update(
    ctx: typer.Context,
    entry_id: Annotated[int, typer.Argument(help="ID of the entry to update.")],
    title: Annotated[str | None, typer.Option(help="New title.")] = None,
    entry_date: Annotated[str | None, typer.Option("--date", help="New date (YYYY-MM-DD).")] = None,
    start_time: Annotated[str | None, typer.Option(help="New start time (HH:MM).")] = None,
    end_time: Annotated[str | None, typer.Option(help="New end time (HH:MM).")] = None,
    medium: Annotated[str | None, typer.Option(help="New medium.")] = None,
    venue: Annotated[str | None, typer.Option(help="New venue.")] = None,
    imdb_id: Annotated[
        str | None, typer.Option(help="Re-fetch OMDb ratings for this IMDb ID.")
    ] = None,
    letterboxd_url: Annotated[str | None, typer.Option(help="New Letterboxd URL.")] = None,
    letterboxd_rating: Annotated[str | None, typer.Option(help="New Letterboxd rating.")] = None,
    notes: Annotated[str | None, typer.Option(help="New notes about the viewing.")] = None,
) -> None:
    """Update an existing logged entry."""
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        try:
            current = store.get_entry(entry_id)
        except StoreError as e:
            typer.secho(str(e), fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

        medium_id = current.medium_id
        if medium is not None:
            medium_row = store.get_or_create_medium(medium, is_physical_place=venue is not None)
            medium_id = medium_row.id

        venue_id = current.venue_id
        if venue is not None:
            venue_id = store.get_or_create_venue(venue).id

        updated = store.update_entry(
            entry_id,
            title=title if title is not None else current.title,
            date=_parse_date(entry_date) if entry_date is not None else current.date,
            start_time=_parse_time(start_time) if start_time is not None else current.start_time,
            end_time=_parse_time(end_time) if end_time is not None else current.end_time,
            medium_id=medium_id,
            venue_id=venue_id,
            letterboxd_url=letterboxd_url if letterboxd_url is not None else current.letterboxd_url,
            letterboxd_rating=letterboxd_rating
            if letterboxd_rating is not None
            else current.letterboxd_rating,
            notes=notes if notes is not None else current.notes,
        )

        if imdb_id is not None:
            updated = _fetch_metadata_or_warn(cfg, store, updated, imdb_id=imdb_id)

        _push_update_or_warn(cfg, store, updated, venue=_venue_name(store, updated))
        typer.echo(f"Updated entry {entry_id}.")
    finally:
        store.close()


# --- delete: requirement "Delete a logged entry" ---


@app.command()
def delete(
    ctx: typer.Context, entry_id: Annotated[int, typer.Argument(help="ID of the entry to delete.")]
) -> None:
    """Delete a logged entry."""
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        try:
            entry = store.get_entry(entry_id)
        except StoreError as e:
            typer.secho(str(e), fg=typer.colors.RED)
            raise typer.Exit(code=1) from e

        store.delete_entry(entry_id)
        _push_delete_or_warn(cfg, store, entry)
        typer.echo(f"Deleted entry {entry_id}.")
    finally:
        store.close()


# --- locations: requirement "User-editable medium and venue lists" ---


@media_app.command("add")
def media_add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument()],
    physical: Annotated[
        bool, typer.Option("--physical/--no-physical", help="Is this a physical place?")
    ] = False,
) -> None:
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        store.add_medium(name, is_physical_place=physical)
        typer.echo(f"Added medium '{name}'.")
    except StoreError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e
    finally:
        store.close()


@media_app.command("list")
def media_list(ctx: typer.Context) -> None:
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        for medium in store.list_media():
            kind = "physical" if medium.is_physical_place else "non-physical"
            typer.echo(f"{medium.name} ({kind})")
    finally:
        store.close()


@media_app.command("remove")
def media_remove(ctx: typer.Context, name: Annotated[str, typer.Argument()]) -> None:
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        store.remove_medium(name)
        typer.echo(f"Removed medium '{name}'.")
    except StoreError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e
    finally:
        store.close()


@venues_app.command("add")
def venues_add(ctx: typer.Context, name: Annotated[str, typer.Argument()]) -> None:
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        store.add_venue(name)
        typer.echo(f"Added venue '{name}'.")
    except StoreError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e
    finally:
        store.close()


@venues_app.command("list")
def venues_list(ctx: typer.Context) -> None:
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        for venue in store.list_venues():
            typer.echo(venue.name)
    finally:
        store.close()


@venues_app.command("remove")
def venues_remove(ctx: typer.Context, name: Annotated[str, typer.Argument()]) -> None:
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        store.remove_venue(name)
        typer.echo(f"Removed venue '{name}'.")
    except StoreError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e
    finally:
        store.close()


# --- import: requirements "Import from CSV/JSON", "Import summary" ---


@app.command(name="import")
def import_command(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(help="CSV or JSON file to import.")],
    force: Annotated[
        bool, typer.Option("--force", help="Persist rows that look like duplicates.")
    ] = False,
    no_metadata: Annotated[
        bool,
        typer.Option(
            "--no-metadata",
            help="Skip the OMDb lookup. Useful for a large historical import that would "
            "otherwise exceed OMDb's daily request limit - run 'sync refresh --from/--to' "
            "afterward to backfill ratings in date-scoped batches.",
        ),
    ] = False,
) -> None:
    """Bulk import viewing entries from a CSV or JSON file."""
    cfg = _cfg(ctx)
    if path.suffix == ".csv":
        rows = parse_csv(path)
    elif path.suffix == ".json":
        rows = parse_json(path)
    else:
        typer.secho(
            f"Unsupported file type '{path.suffix}' (expected .csv or .json).", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    store = _open_store(cfg)
    try:
        summary = run_import(store, rows, force=force)
        for imported in summary.imported_entries:
            _finalize_entry(
                cfg,
                store,
                imported.entry,
                venue=imported.venue,
                fetch_metadata=not no_metadata,
            )

        typer.echo(
            f"{summary.imported} imported, {summary.skipped_duplicates} skipped, "
            f"{summary.failed} failed."
        )
        for detail in summary.skipped_details:
            typer.echo(f"  skipped: {detail}")
        for detail in summary.failed_details:
            typer.echo(f"  failed: {detail}")
    finally:
        store.close()


# --- from-pathe-email: requirements in specs/pathe-email-import ---


def _echo_parsed_booking(booking: PatheBooking) -> None:
    typer.echo(f"Booking {booking.booking_ref}:")
    typer.echo(f"  {booking.title}")
    typer.echo(f"  {booking.date} {booking.start_time}-{booking.end_time}")
    typer.echo(f"  {booking.cinema}")
    if booking.screening_details:
        typer.echo(f"  {booking.screening_details}")


@app.command(name="from-pathe-email")
def from_pathe_email(
    ctx: typer.Context,
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Pathé booking confirmation email (raw .eml or plain text). "
            "Omit to read from stdin."
        ),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the confirmation prompt.")] = False,
    no_metadata: Annotated[
        bool, typer.Option("--no-metadata", help="Skip the OMDb lookup.")
    ] = False,
) -> None:
    """Parse a Pathé booking confirmation email and log or update the
    matching entry. Reads from the given file, or from stdin when no path
    is given - e.g. `cat ticket.eml | movie-planner from-pathe-email`.
    """
    cfg = _cfg(ctx)
    from_stdin = path is None
    raw = sys.stdin.read() if path is None else path.read_text(encoding="utf-8")

    try:
        booking = parse_pathe_email(raw)
    except PatheEmailParseError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e

    store = _open_store(cfg)
    try:
        target = store.get_entry_by_booking_ref(booking.booking_ref)
        duplicate = (
            None
            if target is not None
            else find_duplicate(booking.title, booking.date, store.list_entries())
        )
        match = target or duplicate

        _echo_parsed_booking(booking)
        if target is not None:
            prompt = (
                f"Booking {booking.booking_ref} is already logged as entry {target.id} "
                f"('{target.title}', {target.date} {target.start_time}-{target.end_time}). "
                "Update it to match this email?"
            )
        elif duplicate is not None:
            prompt = (
                f"'{booking.title}' looks like a duplicate of entry {duplicate.id} "
                f"('{duplicate.title}', logged {duplicate.date}). Attach this booking to "
                "that entry instead of creating a new one?"
            )
        else:
            prompt = f"Log '{booking.title}' on {booking.date}?"

        if not (yes or _confirm(prompt, from_stdin=from_stdin)):
            typer.echo("Not added.")
            raise typer.Exit(code=1)

        medium_row = store.get_or_create_medium("cinema", is_physical_place=True)
        venue_row = store.get_or_create_venue(booking.cinema)

        if match is not None:
            entry = store.update_entry(
                match.id,
                title=booking.title,
                date=booking.date,
                start_time=booking.start_time,
                end_time=booking.end_time,
                medium_id=medium_row.id,
                venue_id=venue_row.id,
                booking_ref=booking.booking_ref,
            )
        else:
            entry = store.create_entry(
                title=booking.title,
                date=booking.date,
                start_time=booking.start_time,
                end_time=booking.end_time,
                medium_id=medium_row.id,
                venue_id=venue_row.id,
            )
            entry = store.update_entry(entry.id, booking_ref=booking.booking_ref)

        entry = _finalize_entry(
            cfg,
            store,
            entry,
            venue=booking.cinema,
            fetch_metadata=not no_metadata,
            screening_details=booking.screening_details,
        )

        verb = "Updated" if match is not None else "Logged"
        typer.echo(f"{verb} '{booking.title}' as entry {entry.id}.")
    finally:
        store.close()


# --- sync retry: design.md's "sync failure does not lose the local entry" ---


@sync_app.command("retry")
def sync_retry(ctx: typer.Context) -> None:
    """Retry pushing any entries that failed to sync to the calendar."""
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        unsynced = [e for e in store.list_entries() if e.caldav_uid is None]
        if not unsynced:
            typer.echo("Nothing to retry.")
            return
        for entry in unsynced:
            _finalize_entry(
                cfg, store, entry, venue=_venue_name(store, entry), fetch_metadata=False
            )
        retried = sum(1 for e in unsynced if store.get_entry(e.id).caldav_uid is not None)
        typer.echo(f"Retried {len(unsynced)} entries, {retried} synced successfully.")
    finally:
        store.close()


# --- sync refresh: design.md's "refresh stays separate from sync retry" ---


@sync_app.command("refresh")
def sync_refresh(
    ctx: typer.Context,
    date_from: Annotated[
        str | None, typer.Option("--from", help="Only entries on or after this date.")
    ] = None,
    date_to: Annotated[
        str | None, typer.Option("--to", help="Only entries on or before this date.")
    ] = None,
    entry_date: Annotated[
        str | None, typer.Option("--date", help="Only entries on this exact date.")
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Re-fetch OMDb ratings even for entries that already have them.",
        ),
    ] = False,
) -> None:
    """Backfill missing OMDb ratings and re-push every entry's calendar
    event, so its description reflects current data. Kept separate from
    `sync retry` - this touches every entry and can make many OMDb calls
    on a first run; `retry` stays the cheap, unsynced-only, no-OMDb path.

    With no date arguments, every entry is refreshed. `--from`/`--to` scope
    it to a date range; `--date` scopes it to a single day and can't be
    combined with either. `--force` re-fetches ratings for entries that
    already have them, instead of only entries missing one.
    """
    if entry_date is not None and (date_from is not None or date_to is not None):
        typer.secho("--date can't be combined with --from or --to.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if entry_date is not None:
        date_from = date_to = entry_date

    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        entries = store.list_entries(
            date_from=_parse_date(date_from) if date_from else None,
            date_to=_parse_date(date_to) if date_to else None,
        )
        if not entries:
            typer.echo("No entries to refresh.")
            return

        to_fetch = entries if force else [e for e in entries if e.imdb_rating is None]
        if to_fetch:
            typer.echo(
                f"About to look up OMDb ratings for {len(to_fetch)} of {len(entries)} entries."
            )

        fetched = 0
        for entry in entries:
            fetch_metadata = force or entry.imdb_rating is None
            refreshed = _finalize_entry(
                cfg, store, entry, venue=_venue_name(store, entry), fetch_metadata=fetch_metadata
            )
            if fetch_metadata and refreshed.imdb_rating is not None:
                fetched += 1

        typer.echo(f"Refreshed {len(entries)} entries ({fetched} metadata fetches).")
    finally:
        store.close()


def main() -> None:
    app()
