"""The Typer app wiring every capability (movie-log, calendar-sync,
metadata, duplicate-detection, import) into commands.
"""

import dataclasses
import email
import email.policy
import email.utils
import re
import sys
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Annotated

import httpx
import typer

from movie_planner import config as config_module
from movie_planner import config_file
from movie_planner.calendar_pull import (
    Candidate,
    ChangedCandidate,
    NewCandidate,
    ParsedEvent,
    RemovedCandidate,
    detect_candidates,
)
from movie_planner.calendar_sync import CalendarClient, CalendarSync
from movie_planner.display import detect_terminal_image_protocol, format_entry, render_poster
from movie_planner.duplicates import find_duplicate
from movie_planner.importers import IMPORT_FORMATS, parse_json_text, run_import
from movie_planner.omdb import OmdbClient, fetch_and_store_ratings, needs_omdb_fetch
from movie_planner.pathe import PatheBooking, PatheEmailParseError, parse_pathe_email
from movie_planner.store import Entry, Medium, Store, StoreError, Venue
from movie_planner.tmdb import TmdbClient

app = typer.Typer(help="movie-planner: log watched movies and sync them to a calendar.")
locations_app = typer.Typer(help="Manage the medium and venue lists.")
media_app = typer.Typer(help="Manage the medium list.")
venues_app = typer.Typer(help="Manage the venue list.")
sync_app = typer.Typer(help="Manage calendar sync.")
import_failures_app = typer.Typer(help="Inspect and clear past import failures.")
locations_app.add_typer(media_app, name="media")
locations_app.add_typer(venues_app, name="venues")
app.add_typer(locations_app, name="locations")
app.add_typer(sync_app, name="sync")
app.add_typer(import_failures_app, name="import-failures")


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
    tmdb_api_key: str | None = None
    db_path: Path | None = None


# Click derives each env var from its option name under this prefix, e.g.
# --caldav-url becomes MOVIE_PLANNER_CALDAV_URL. rules/cli.md: flags >
# environment variables > config file > built-in defaults.
@app.callback(context_settings={"auto_envvar_prefix": "MOVIE_PLANNER"})
def callback(
    ctx: typer.Context,
    config: Annotated[
        Path | None,
        typer.Option(
            help="Path to config.toml. Defaults to the XDG config location "
            "($XDG_CONFIG_HOME/movie-planner/config.toml, or ~/.config/movie-planner/config.toml "
            "if that's unset). Point this elsewhere to run against a second account or a "
            "test database without touching the default file."
        ),
    ] = None,
    caldav_url: Annotated[
        str | None,
        typer.Option(
            help="Override caldav.url from the config file for this one invocation - the "
            "config file stays the persisted default; this is for a throwaway run against a "
            "different calendar. Also settable as $MOVIE_PLANNER_CALDAV_URL, for scripting "
            "without a second config file."
        ),
    ] = None,
    caldav_username: Annotated[
        str | None,
        typer.Option(
            help="Override caldav.username from the config file for this one invocation. "
            "Also settable as $MOVIE_PLANNER_CALDAV_USERNAME."
        ),
    ] = None,
    omdb_api_key: Annotated[
        str | None,
        typer.Option(
            help="Override omdb.api_key from the config file for this one invocation - useful "
            "for trying a different key (a higher-tier plan, a per-CI key) without editing the "
            "config file. Also settable as $MOVIE_PLANNER_OMDB_API_KEY."
        ),
    ] = None,
    tmdb_api_key: Annotated[
        str | None,
        typer.Option(
            help="Override tmdb.api_key from the config file for this one invocation. Optional - "
            "with no key set (here, in the config file, or as $MOVIE_PLANNER_TMDB_API_KEY), "
            "trailer lookups are simply skipped rather than treated as an error."
        ),
    ] = None,
    db_path: Annotated[
        Path | None,
        typer.Option(
            help="Override storage.db_path from the config file for this one invocation - "
            "point at a scratch database for testing, or a second one for a different movie "
            "log, without editing the config file. Also settable as $MOVIE_PLANNER_DB_PATH."
        ),
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
        tmdb_api_key=tmdb_api_key,
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

# Optional - trailer lookups are simply skipped without it:
# [tmdb]
# api_key = "..."

[storage]
db_path = "~/.local/share/movie-planner/movies.db"
"""


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _required_value(value: str | None, *, prompt: str, flag: str, interactive: bool) -> str:
    if value:
        return value
    if interactive:
        return str(typer.prompt(prompt))
    typer.secho(
        f"No {flag} given and not running interactively; pass {flag} explicitly.",
        fg=typer.colors.RED,
    )
    raise typer.Exit(code=1)


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
        tmdb_api_key=overrides.tmdb_api_key or cfg.tmdb_api_key,
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
        bool,
        typer.Option(
            "--force",
            help="Overwrite the whole file, including any [mail_import] section "
            "pathe-mail-import already wrote there (issue #157). Without --force, adding "
            "movie-planner's own [movie_planner] section to a file that already has one is "
            "refused rather than silently replacing it - --force is the explicit 'yes, "
            "start over' for that.",
        ),
    ] = False,
) -> None:
    """Write a starter config.toml, ready to edit. Prompts for the
    CalDAV URL, CalDAV username, and OMDb API key - unless already
    given as a flag or environment variable - or fails clearly instead
    of hanging when not running in a terminal (issue #144). The CalDAV
    password stays out of it, same as everywhere else: edit it in by
    hand afterwards, as `password` or `password_command`.

    Sharing the file with pathe-mail-import (issue #157): if it
    already exists but has no [movie_planner] section yet - e.g.
    pathe-mail-import already wrote its own [mail_import] section
    there - this adds movie-planner's section alongside it, no
    --force needed.
    """
    overrides: _ConfigOverrides = ctx.obj
    config_path = overrides.config_path or config_module.default_config_path()

    if config_path.is_file() and not force:
        try:
            already_configured = config_file.has_section(config_path, "movie_planner")
        except config_file.ConfigFileError:
            already_configured = True  # unreadable existing content - don't guess, don't clobber
        if already_configured:
            typer.secho(
                f"{config_path} already exists. Pass --force to overwrite it.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

    interactive = _is_interactive()
    caldav_url = _required_value(
        overrides.caldav_url, prompt="CalDAV URL", flag="--caldav-url", interactive=interactive
    )
    caldav_username = _required_value(
        overrides.caldav_username,
        prompt="CalDAV username",
        flag="--caldav-username",
        interactive=interactive,
    )
    omdb_api_key = _required_value(
        overrides.omdb_api_key,
        prompt="OMDb API key",
        flag="--omdb-api-key",
        interactive=interactive,
    )

    content = f"""\
[movie_planner.caldav]
url = "{caldav_url}"
username = "{caldav_username}"
password = "..."
# Or, instead of a plaintext password above, run a command that prints
# it to stdout (e.g. a password manager) - set only one of the two:
# password_command = "pass show caldav/movie-planner"

[movie_planner.omdb]
api_key = "{omdb_api_key}"

# Optional - trailer lookups are simply skipped without it:
# [movie_planner.tmdb]
# api_key = "..."

[movie_planner.storage]
db_path = "~/.local/share/movie-planner/movies.db"
"""

    if force:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(content)
    else:
        config_file.write_section(config_path, content)
    typer.echo(
        f"Wrote a starter config to {config_path}. Edit in your CalDAV "
        "password before running any other command."
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


def _venue_for_entry(store: Store, entry: Entry) -> Venue | None:
    if entry.venue_id is None:
        return None
    return next((v for v in store.list_venues() if v.id == entry.venue_id), None)


def _push_new_or_warn(
    cfg: config_module.Config,
    store: Store,
    entry: Entry,
    *,
    screening_details: str | None = None,
) -> Entry:
    venue = _venue_for_entry(store, entry)
    try:
        client = _connect_calendar(cfg)
        return CalendarSync(store, client).push_new(
            entry,
            venue=_venue_location(venue),
            chain=venue.chain if venue else None,
            screening_details=screening_details,
            geo=_venue_geo(venue),
            city=venue.city if venue else None,
            country=venue.country if venue else None,
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
    screening_details: str | None = None,
) -> None:
    if entry.caldav_uid is None:
        return
    venue = _venue_for_entry(store, entry)
    try:
        client = _connect_calendar(cfg)
        CalendarSync(store, client).push_update(
            entry,
            venue=_venue_location(venue),
            chain=venue.chain if venue else None,
            screening_details=screening_details,
            geo=_venue_geo(venue),
            city=venue.city if venue else None,
            country=venue.country if venue else None,
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
        return _push_new_or_warn(cfg, store, entry, screening_details=screening_details)
    _push_update_or_warn(cfg, store, entry, screening_details=screening_details)
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


_IMDB_ID_RE = re.compile(r"tt\d+")


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
    return _fetch_trailer_or_warn(cfg, store, updated)


def _fetch_trailer_or_warn(cfg: config_module.Config, store: Store, entry: Entry) -> Entry:
    """TMDb trailer lookup (issue #236) - piggybacks on the imdb_id an
    OMDb match already produced, so it's only ever attempted right after
    a successful OMDb fetch, never on its own. A config with no
    tmdb.api_key set is the common case, not an error - simply skipped.
    """
    if not cfg.tmdb_api_key or not entry.imdb_url:
        return entry
    match = _IMDB_ID_RE.search(entry.imdb_url)
    if match is None:
        return entry
    try:
        client = TmdbClient(cfg.tmdb_api_key)
        trailer_url = client.lookup_trailer_url(imdb_id=match.group())
    except Exception as e:  # noqa: BLE001 - trailer lookup is optional, never fatal
        typer.secho(f"Warning: could not fetch a trailer: {e}", fg=typer.colors.YELLOW)
        return entry
    if trailer_url is None:
        return entry
    return store.update_entry(entry.id, trailer_url=trailer_url)


def _venue_location(venue: Venue | None) -> str | None:
    """Builds the VEVENT LOCATION string: just the venue name, or, for a
    venue matching the hardcoded chain/city/country table, "name, city,
    country" - a real, geocodable address string most calendar clients
    (Google Calendar, Apple Calendar) already try to map from LOCATION,
    which is why chain isn't folded in here too - see docs/calendar-schema.md.
    """
    if venue is None:
        return None
    if venue.city and venue.country:
        return f"{venue.name}, {venue.city}, {venue.country}"
    return venue.name


def _venue_geo(venue: Venue | None) -> tuple[float, float] | None:
    """The VEVENT GEO value for a venue with known coordinates (issue
    #170), or None - never a guessed value - for one without.
    """
    if venue is None or venue.latitude is None or venue.longitude is None:
        return None
    return (venue.latitude, venue.longitude)


# --- log: requirement "Log a watched movie interactively" ---


@app.command()
def log(
    ctx: typer.Context,
    title: Annotated[
        str | None,
        typer.Option(help="Movie title. Prompted for if omitted and running in a terminal."),
    ] = None,
    entry_date: Annotated[
        str | None,
        typer.Option(
            "--date",
            help="Date watched (YYYY-MM-DD). Prompted for if omitted and running in a "
            "terminal. This alone (no start/end time) makes an all-day calendar event.",
        ),
    ] = None,
    start_time: Annotated[
        str | None,
        typer.Option(
            help="Start time (HH:MM). Optional - omit for an all-day event. Given without "
            "--end-time, the calendar event gets a start with no end."
        ),
    ] = None,
    end_time: Annotated[
        str | None,
        typer.Option(
            help="End time (HH:MM). Only meaningful together with --start-time - a bare "
            "--end-time with no start is ignored the same as omitting both."
        ),
    ] = None,
    medium: Annotated[
        str | None,
        typer.Option(
            help="Medium (for example cinema, netflix, blu-ray). Determines whether --venue "
            "applies: only a medium already marked physical (see "
            "'locations media add --physical') can have one."
        ),
    ] = None,
    venue: Annotated[
        str | None,
        typer.Option(
            help="Venue - only meaningful for a physical medium. A name matching the "
            "hardcoded chain/location table (Pathé's own cinemas, GSC's, a handful of "
            "independent Amsterdam venues) gets its chain, city, country, and GPS "
            "coordinates filled in automatically; any other name is stored as-is, no guess."
        ),
    ] = None,
    imdb_id: Annotated[
        str | None,
        typer.Option(
            help="IMDb ID (e.g. tt1160419) for a precise OMDb lookup, instead of matching by "
            "title - use this when the title alone matched the wrong film or found nothing."
        ),
    ] = None,
    letterboxd_url: Annotated[
        str | None,
        typer.Option(
            help="Manually entered Letterboxd URL - movie-planner has no Letterboxd "
            "integration, so this and --letterboxd-rating are the only way either ever "
            "lands on the entry."
        ),
    ] = None,
    letterboxd_rating: Annotated[
        str | None, typer.Option(help="Manually entered Letterboxd rating (free text).")
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option(
            help="Personal notes about the viewing (who with, a reaction). Unlike Pathé "
            "screening details, notes persist across a later 'sync refresh'/'update' that "
            "changes nothing else about the entry."
        ),
    ] = None,
    no_metadata: Annotated[
        bool,
        typer.Option(
            "--no-metadata",
            help="Skip the OMDb lookup entirely - no ratings, poster, director, cast, "
            "genre, or release year. Useful when OMDb's daily request cap is a concern; "
            "backfill later with 'sync refresh'.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Log even if it looks like a duplicate (same normalized title, same day) - "
            "skips the confirmation prompt that would otherwise ask first.",
        ),
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
        duplicate = find_duplicate(
            title, parsed_date, store.list_entries(), start_time=parsed_start, end_time=parsed_end
        )
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

        entry = _finalize_entry(cfg, store, entry, fetch_metadata=not no_metadata, imdb_id=imdb_id)

        typer.echo(f"Logged '{title}' as entry {entry.id}.")
    finally:
        store.close()


# --- list: requirement "List logged entries" ---


@app.command(name="list")
def list_entries(
    ctx: typer.Context,
    date_from: Annotated[
        str | None,
        typer.Option("--from", help="Only entries on or after this date (YYYY-MM-DD)."),
    ] = None,
    date_to: Annotated[
        str | None,
        typer.Option("--to", help="Only entries on or before this date (YYYY-MM-DD)."),
    ] = None,
    medium: Annotated[
        str | None,
        typer.Option(help="Only entries with this exact medium name (for example cinema)."),
    ] = None,
    chain: Annotated[
        str | None,
        typer.Option(
            help="Only entries at a venue in this chain (for example Pathé, GSC) - only "
            "matches a venue movie-planner already knows the chain for, from the hardcoded "
            "chain/location table; a venue it doesn't recognize never matches any --chain "
            "filter, regardless of the real chain."
        ),
    ] = None,
    city: Annotated[
        str | None,
        typer.Option(
            help="Only entries at a venue in this city - same known-venue-table limitation "
            "as --chain."
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            min=1,
            help="Only the N most recently-dated entries (applied after every other filter, "
            "same order 'list' already shows - oldest of the N first). Omit to show "
            "everything matching the other filters, same as today.",
        ),
    ] = None,
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

        venue_ids = None
        if chain is not None or city is not None:
            matches = [
                v
                for v in venues_by_id.values()
                if (chain is None or v.chain == chain) and (city is None or v.city == city)
            ]
            if not matches:
                typer.echo("No entries.")
                return
            venue_ids = [v.id for v in matches]

        entries = store.list_entries(
            date_from=_parse_date(date_from) if date_from else None,
            date_to=_parse_date(date_to) if date_to else None,
            medium_id=medium_id,
            venue_ids=venue_ids,
        )
        if limit is not None:
            entries = entries[-limit:]
        if not entries:
            typer.echo("No entries.")
            return
        for entry in entries:
            medium_name = media_by_id[entry.medium_id].name
            venue_name = venues_by_id[entry.venue_id].name if entry.venue_id else None
            title = f"{entry.title} ({entry.release_year})" if entry.release_year else entry.title
            line = f"{entry.id}  {entry.date}  {title}  [{medium_name}]"
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
    if entry.poster_url:
        return entry.poster_url
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
        venue = venues_by_id[entry.venue_id] if entry.venue_id else None
        typer.echo(format_entry(entry, medium_name=medium_name, venue=venue))

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
    title: Annotated[
        str | None, typer.Option(help="New title. Omit to leave the current title unchanged.")
    ] = None,
    entry_date: Annotated[
        str | None,
        typer.Option("--date", help="New date (YYYY-MM-DD). Omit to leave the date unchanged."),
    ] = None,
    start_time: Annotated[
        str | None,
        typer.Option(help="New start time (HH:MM). Omit to leave the start time unchanged."),
    ] = None,
    end_time: Annotated[
        str | None,
        typer.Option(help="New end time (HH:MM). Omit to leave the end time unchanged."),
    ] = None,
    medium: Annotated[
        str | None, typer.Option(help="New medium. Omit to leave the current medium unchanged.")
    ] = None,
    venue: Annotated[
        str | None,
        typer.Option(
            help="New venue - same chain/location auto-fill as 'log' --venue. Omit to leave "
            "the current venue unchanged."
        ),
    ] = None,
    imdb_id: Annotated[
        str | None,
        typer.Option(
            help="Re-fetch OMDb ratings for this specific IMDb ID, overwriting whatever "
            "ratings/poster/director/cast/genre/year the entry already has - use this to "
            "correct a wrong OMDb match, not to add ratings for the first time (that's "
            "'sync refresh')."
        ),
    ] = None,
    letterboxd_url: Annotated[
        str | None,
        typer.Option(help="New Letterboxd URL. Omit to leave the current one unchanged."),
    ] = None,
    letterboxd_rating: Annotated[
        str | None,
        typer.Option(help="New Letterboxd rating. Omit to leave the current one unchanged."),
    ] = None,
    notes: Annotated[
        str | None, typer.Option(help="New notes. Omit to leave the current notes unchanged.")
    ] = None,
    refresh_metadata: Annotated[
        bool,
        typer.Option(
            "--refresh-metadata",
            help="Re-fetch OMDb data for this entry alone, overwriting existing ratings/"
            "poster/director/cast/genre/year/etc. - the single-entry equivalent of 'sync "
            "refresh --force', without needing to know this entry's date or affect any other "
            "entry that happens to share it. Ignored if --imdb-id is also given, since that "
            "already re-fetches too.",
        ),
    ] = False,
) -> None:
    """Update an existing logged entry. Every option is optional and
    independent - give only the fields that are actually changing;
    anything omitted keeps its current value.
    """
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
        elif refresh_metadata:
            updated = _fetch_metadata_or_warn(cfg, store, updated, imdb_id=None)

        _push_update_or_warn(cfg, store, updated)
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
    name: Annotated[str, typer.Argument(help="Medium name (for example cinema, netflix).")],
    physical: Annotated[
        bool,
        typer.Option(
            "--physical/--no-physical",
            help="Whether this medium is a real, physical place - a cinema, not "
            "netflix/youtube/etc. Only a physical medium can have a --venue on 'log'/"
            "'update', since a venue means nothing for a streaming service.",
        ),
    ] = False,
) -> None:
    """Add a medium (a way of watching something - cinema, netflix,
    blu-ray) to the known list.
    """
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
    """List every known medium and whether it's physical."""
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        for medium in store.list_media():
            kind = "physical" if medium.is_physical_place else "non-physical"
            typer.echo(f"{medium.name} ({kind})")
    finally:
        store.close()


@media_app.command("remove")
def media_remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Medium name to remove.")],
) -> None:
    """Remove a medium - refused if any logged entry still references
    it, so a name in use can't silently orphan its entries.
    """
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
def venues_add(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(
            help="Venue name. A name matching the hardcoded chain/location table gets its "
            "chain, city, country, and GPS coordinates filled in automatically; any other "
            "name is stored as-is, never a guess. Usually unnecessary to run directly - "
            "'log'/'update' create a venue on first use."
        ),
    ],
) -> None:
    """Add a venue to the known list directly, without logging an
    entry at it.
    """
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
    """List every known venue name."""
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        for venue in store.list_venues():
            typer.echo(venue.name)
    finally:
        store.close()


@venues_app.command("remove")
def venues_remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Venue name to remove.")],
) -> None:
    """Remove a venue - refused if any logged entry still references
    it, so a name in use can't silently orphan its entries.
    """
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


@venues_app.command("merge-aliases")
def venues_merge_aliases(
    ctx: typer.Context,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Actually perform the merge - reassign every affected entry's venue and "
            "delete the now-orphaned alias venue rows. Without this, nothing changes; only "
            "a summary of what would happen is printed (issue #196).",
        ),
    ] = False,
) -> None:
    """Collapse venue rows that are really the same real-world venue,
    just logged with a screen/format suffix baked into the name (e.g.
    "De Munt 4DX" alongside "De Munt") - fixes rows created before
    `log`/`import`/`add` started resolving these automatically.
    Doesn't touch the calendar - a merged venue's already-pushed
    events still show the old LOCATION string until `sync refresh
    --force` re-pushes them.
    """
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        merges = store.merge_venue_aliases(apply=apply)
        if not merges:
            typer.echo("No alias venues found - nothing to merge.")
            return
        verb = "Merged" if apply else "Would merge"
        for merge in merges:
            entries_word = "entry" if merge.entries_moved == 1 else "entries"
            typer.echo(
                f"{verb} '{merge.alias_name}' into '{merge.canonical_name}' "
                f"({merge.entries_moved} {entries_word})"
            )
        if not apply:
            typer.echo("\nDry run - pass --apply to actually perform this merge.")
    finally:
        store.close()


# --- import: requirements "Import from CSV/JSON", "Import summary" ---


@app.command(name="import")
def import_command(
    ctx: typer.Context,
    path: Annotated[
        Path | None,
        typer.Argument(help="CSV or JSON file to import. Omit to read JSON from stdin."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Persist rows that look like duplicates (same normalized title, same day as "
            "an existing entry) instead of skipping them - a bulk-import equivalent of "
            "confirming 'yes' to every duplicate prompt 'log' would otherwise show one at a "
            "time.",
        ),
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
    """Bulk import viewing entries from a CSV or JSON file, or pipe JSON
    (an array, or a single row object) in on stdin when no path is
    given. A row that already supplies every OMDb-derived field itself
    (ratings, poster, director, actors, genre, release year) skips the
    OMDb lookup for that row alone, regardless of --no-metadata.
    """
    cfg = _cfg(ctx)
    source_label = str(path) if path is not None else "stdin"
    if path is None:
        rows = parse_json_text(sys.stdin.read())
    else:
        fmt = IMPORT_FORMATS.get(path.suffix)
        if fmt is None:
            supported = ", ".join(sorted(IMPORT_FORMATS))
            typer.secho(
                f"Unsupported file type '{path.suffix}' (expected {supported}).",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        rows = fmt.parse(path)

    store = _open_store(cfg)
    try:
        summary = run_import(store, rows, force=force)
        for imported in summary.imported_entries:
            _finalize_entry(
                cfg,
                store,
                imported.entry,
                fetch_metadata=not no_metadata and needs_omdb_fetch(imported.entry),
            )
        # Persisted (issue #254) so `import-failures list` can show them
        # after this run's own output has scrolled away - run_import
        # itself stays pure/ephemeral, this is the one place that writes.
        for row in rows:
            if row.error is not None:
                store.record_import_failure(
                    source=source_label, row_number=row.row_number, error=row.error
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


@import_failures_app.command("list")
def import_failures_list(ctx: typer.Context) -> None:
    """Show every past import failure, most recent first - what
    `movie-planner import` echoed at the time, still visible after that
    run's own output has scrolled away.
    """
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        failures = store.list_import_failures()
        if not failures:
            typer.echo("No import failures recorded.")
            return
        for failure in failures:
            when = failure.created_at.isoformat(timespec="seconds")
            typer.echo(
                f"[{failure.id}] {when} {failure.source} row {failure.row_number}: {failure.error}"
            )
    finally:
        store.close()


@import_failures_app.command("clear")
def import_failures_clear(ctx: typer.Context) -> None:
    """Delete every recorded import failure - once you've handled them
    (fixed the source file, re-imported the rows by hand), there's no
    reason for the list to keep growing.
    """
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        cleared = store.clear_import_failures()
        failures_word = "failure" if cleared == 1 else "failures"
        typer.echo(f"Cleared {cleared} import {failures_word}.")
    finally:
        store.close()


# --- from-pathe-email: requirements in specs/pathe-email-import ---


def _echo_parsed_booking(booking: PatheBooking) -> None:
    times = (
        f"{booking.start_time}-{booking.end_time}" if booking.end_time else f"{booking.start_time}"
    )
    typer.echo(f"Booking {booking.booking_ref}:")
    typer.echo(f"  {booking.title}")
    typer.echo(f"  {booking.date} {times}")
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
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip the confirmation prompt - needed for a mail-pipe automation with no "
            "terminal attached, since the confirmation is always read from the controlling "
            "terminal (/dev/tty), never from stdin, so piping an email in doesn't skip it "
            "on its own.",
        ),
    ] = False,
    no_metadata: Annotated[
        bool,
        typer.Option(
            "--no-metadata", help="Skip the OMDb lookup - same use case as 'log'/'import's own."
        ),
    ] = False,
) -> None:
    """Parse a Pathé booking confirmation email and log or update the
    matching entry. Reads from the given file, or from stdin when no path
    is given - e.g. `cat ticket.eml | movie-planner from-pathe-email`. A
    re-sent confirmation for a booking already logged (matched by its
    booking number) updates that entry instead of creating a second one.
    """
    cfg = _cfg(ctx)
    from_stdin = path is None
    raw = sys.stdin.read() if path is None else path.read_text(encoding="utf-8")

    # Only the three Dutch templates parse_pathe_email itself can't date
    # (movie-planner#200) actually need this - a message with no
    # parseable Date header (e.g. already-extracted plain text with no
    # headers at all) just leaves it None, same as those templates would
    # get with no year in their own text either way.
    try:
        received_date = email.utils.parsedate_to_datetime(
            str(email.message_from_string(raw, policy=email.policy.default).get("Date"))
        ).date()
    except TypeError, ValueError:
        received_date = None

    try:
        booking = parse_pathe_email(raw, received_date=received_date)
    except PatheEmailParseError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1) from e

    store = _open_store(cfg)
    try:
        target = store.get_entry_by_booking_ref(booking.booking_ref)
        duplicate = (
            None
            if target is not None
            else find_duplicate(
                booking.title,
                booking.date,
                store.list_entries(),
                start_time=booking.start_time,
                end_time=booking.end_time,
            )
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
                row=booking.row,
                seat=booking.seat,
            )
        else:
            entry = store.create_entry(
                title=booking.title,
                date=booking.date,
                start_time=booking.start_time,
                end_time=booking.end_time,
                medium_id=medium_row.id,
                venue_id=venue_row.id,
                row=booking.row,
                seat=booking.seat,
            )
            entry = store.update_entry(entry.id, booking_ref=booking.booking_ref)

        entry = _finalize_entry(
            cfg,
            store,
            entry,
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
    """Retry pushing any entry that's never been synced (its
    caldav_uid is still unset) - cheap and safe to run any time, since
    it never calls OMDb and only touches those entries. This is not
    the same as recovering an entry whose caldav_uid points at an
    event the calendar no longer has (an external wipe/rebuild) - that
    recovery happens automatically inside a normal 'sync refresh' or
    the next 'log'/'update' push for that specific entry, not here.
    """
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        unsynced = [e for e in store.list_entries() if e.caldav_uid is None]
        if not unsynced:
            typer.echo("Nothing to retry.")
            return
        for entry in unsynced:
            _finalize_entry(cfg, store, entry, fetch_metadata=False)
        retried = sum(1 for e in unsynced if store.get_entry(e.id).caldav_uid is not None)
        typer.echo(f"Retried {len(unsynced)} entries, {retried} synced successfully.")
    finally:
        store.close()


# --- sync refresh: design.md's "refresh stays separate from sync retry" ---


@sync_app.command("refresh")
def sync_refresh(
    ctx: typer.Context,
    date_from: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Only entries on or after this date (YYYY-MM-DD) - combine with --to to "
            "scope a large refresh to a range small enough to stay under OMDb's daily "
            "request limit.",
        ),
    ] = None,
    date_to: Annotated[
        str | None,
        typer.Option("--to", help="Only entries on or before this date (YYYY-MM-DD)."),
    ] = None,
    entry_date: Annotated[
        str | None,
        typer.Option(
            "--date",
            help="Only entries on this exact date - shorthand for --from/--to on the same "
            "day. Can't be combined with either.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Re-fetch OMDb ratings even for entries that already have them - useful "
            "after a wrong OMDb match, or when a rating's changed since. Without --force, "
            "only entries still missing at least one OMDb-derived field are fetched.",
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

        to_fetch = entries if force else [e for e in entries if needs_omdb_fetch(e)]
        if to_fetch:
            typer.echo(
                f"About to look up OMDb ratings for {len(to_fetch)} of {len(entries)} entries."
            )

        fetched = 0
        for entry in entries:
            fetch_metadata = force or needs_omdb_fetch(entry)
            refreshed = _finalize_entry(cfg, store, entry, fetch_metadata=fetch_metadata)
            if fetch_metadata and refreshed.imdb_rating is not None:
                fetched += 1

        typer.echo(f"Refreshed {len(entries)} entries ({fetched} metadata fetches).")
    finally:
        store.close()


# --- sync pull: issue #235/#168, calendar-side changes back into the store ---


def _format_time_range(parsed: ParsedEvent) -> str:
    if parsed.start_time and parsed.end_time:
        return f" {parsed.start_time.isoformat(timespec='minutes')}-{parsed.end_time.isoformat(timespec='minutes')}"
    if parsed.start_time:
        return f" {parsed.start_time.isoformat(timespec='minutes')}"
    return ""


def _describe_new_candidate(parsed: ParsedEvent) -> str:
    venue_part = f" @ {parsed.venue_name}" if parsed.venue_name else ""
    return f"New entry: '{parsed.title}' on {parsed.date}{_format_time_range(parsed)}{venue_part}"


def _format_diff_value(value: object) -> str:
    # design.md's "a missing X-* property is 'unknown', not 'user deleted
    # this'" - the same phrasing applies to any field whose calendar-side
    # value is simply absent, not just the OMDb/booking-derived ones the
    # spec scenario names explicitly.
    return "unknown" if value is None else repr(value)


def _describe_changed_candidate(candidate: ChangedCandidate) -> str:
    lines = [f"Changed entry {candidate.entry.id}: '{candidate.entry.title}'"]
    for diff in candidate.diffs:
        lines.append(
            f"  {diff.field}: {_format_diff_value(diff.stored)} -> "
            f"{_format_diff_value(diff.calendar)}"
        )
    return "\n".join(lines)


def _describe_removed_candidate(candidate: RemovedCandidate) -> str:
    entry = candidate.entry
    return f"Removed entry {entry.id}: '{entry.title}' ({entry.date}) - no longer on the calendar"


def _prompt_medium_name(store: Store, parsed: ParsedEvent) -> Medium:
    # design.md's "New candidate medium: prompted at approval time,
    # never guessed" - the same free-text prompt `log` already asks for,
    # pre-filled with "cinema" only when the candidate has a resolved
    # venue name (LOCATION says physical place; nothing says which one
    # when it's absent, so no default is offered there).
    if parsed.venue_name:
        name = str(typer.prompt("Medium for this entry", default="cinema"))
    else:
        name = str(typer.prompt("Medium for this entry"))
    return store.get_or_create_medium(name, is_physical_place=parsed.venue_name is not None)


def _apply_new_candidate(store: Store, parsed: ParsedEvent) -> None:
    medium_row = _prompt_medium_name(store, parsed)
    venue_row = store.get_or_create_venue(parsed.venue_name) if parsed.venue_name else None
    entry = store.create_entry(
        title=parsed.title,
        date=parsed.date,
        medium_id=medium_row.id,
        start_time=parsed.start_time,
        end_time=parsed.end_time,
        venue_id=venue_row.id if venue_row else None,
        row=parsed.row,
        seat=parsed.seat,
    )
    # caldav_uid links this new local entry back to the event it came
    # from - without it, the next `sync retry`/`refresh` would push a
    # second, duplicate event for it.
    store.update_entry(
        entry.id,
        caldav_uid=parsed.uid,
        director=parsed.director,
        actors=parsed.actors,
        genre=parsed.genre,
        release_year=parsed.release_year,
        poster_url=parsed.poster_url,
    )


def _apply_changed_candidate(store: Store, candidate: ChangedCandidate) -> None:
    parsed = candidate.parsed
    venue_row = store.get_or_create_venue(parsed.venue_name) if parsed.venue_name else None
    store.update_entry(
        candidate.entry.id,
        title=parsed.title,
        date=parsed.date,
        start_time=parsed.start_time,
        end_time=parsed.end_time,
        venue_id=venue_row.id if venue_row else None,
        director=parsed.director,
        actors=parsed.actors,
        genre=parsed.genre,
        release_year=parsed.release_year,
        poster_url=parsed.poster_url,
        row=parsed.row,
        seat=parsed.seat,
    )


def _handle_candidate(store: Store, candidate: Candidate) -> bool:
    """Shows one candidate and applies it if approved - spec.md's "every
    candidate change requires explicit approval", one at a time, same
    confirm-before-write shape `from-pathe-email` already uses. Returns
    whether it was approved, for the summary count.
    """
    if isinstance(candidate, NewCandidate):
        typer.echo(_describe_new_candidate(candidate.parsed))
        if not typer.confirm("Log this as a new entry?"):
            return False
        _apply_new_candidate(store, candidate.parsed)
        return True
    if isinstance(candidate, ChangedCandidate):
        typer.echo(_describe_changed_candidate(candidate))
        if not typer.confirm("Apply this change to the local store?"):
            return False
        _apply_changed_candidate(store, candidate)
        return True
    typer.echo(_describe_removed_candidate(candidate))
    if not typer.confirm("Remove this entry from the local store?"):
        return False
    store.delete_entry(candidate.entry.id)
    return True


@sync_app.command("pull")
def sync_pull(ctx: typer.Context) -> None:
    """Reads every event on the configured calendar back and reconciles
    it against the local store - the read side of an otherwise
    push-only sync (issue #168/#235). Presents each new/changed/removed
    candidate one at a time for approval; nothing is written to the
    store without it, and a declined candidate is simply offered again
    next time, not recorded anywhere. `list`/`show` are entirely
    unaffected - they still only ever read the local store.
    """
    cfg = _cfg(ctx)
    store = _open_store(cfg)
    try:
        client = _connect_calendar(cfg)
        candidates = detect_candidates(store, client.list_events())
        if not candidates:
            typer.echo("Nothing to pull - the calendar matches the local store.")
            return

        approved = 0
        for candidate in candidates:
            if _handle_candidate(store, candidate):
                approved += 1
        typer.echo(f"Applied {approved} of {len(candidates)} candidates.")
    finally:
        store.close()


def main() -> None:
    app()
