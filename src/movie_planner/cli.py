"""The Typer app. Commands land here as the capabilities in
openspec/changes/add-movie-log-cli/tasks.md get implemented.
"""

import typer

app = typer.Typer(help="movie-planner: log watched movies and sync them to a calendar.")


@app.callback()
def callback() -> None:
    """movie-planner: log watched movies and sync them to a calendar.

    An empty callback, not a no-op — its only job is stopping Typer/Click
    from collapsing a single-command app into a bare one once the first
    real subcommand (`log`, `list`, ...) is added.
    """


def main() -> None:
    app()
