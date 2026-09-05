#!/usr/bin/env bash
# One man page per command and subcommand, generated straight from each
# Typer app rather than hand-maintained, so a page can't drift out of
# sync with the --help text it documents. Shared by the nfpm build and
# the AUR PKGBUILD's package() function, so the two can't disagree
# about what ships.
#
# Covers movie-planner's own app and the pathe-mail-import tool's -
# pathe-translate has no man page, since it's a stdin/stdout filter
# with no Typer app or flags of its own to document this way.
set -euo pipefail

cd "$(dirname "$0")/.."

rm -rf man
mkdir -p man

uv run python3 -c "
import datetime
import importlib.metadata

import typer.main
from click_man.core import write_man_pages

from movie_planner.cli import app as movie_planner_app
from movie_planner.mail_import.cli import app as pathe_mail_import_app

version = importlib.metadata.version('movie-planner')
today = datetime.date.today()

write_man_pages(
    'movie-planner',
    typer.main.get_command(movie_planner_app),
    version=version,
    target_dir='man',
    date=today,
)
write_man_pages(
    'pathe-mail-import',
    typer.main.get_command(pathe_mail_import_app),
    version=version,
    target_dir='man',
    date=today,
)
"

# gzip is the convention both dpkg and rpm expect man pages in; nfpm and
# makepkg both just place whatever file is here, they don't compress it
# for you.
gzip -f -9 man/*.1
