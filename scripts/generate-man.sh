#!/usr/bin/env bash
# One man page per command and subcommand, generated straight from the
# Typer app rather than hand-maintained, so a page can't drift out of
# sync with the --help text it documents. Shared by the nfpm build and
# the AUR PKGBUILD's package() function, so the two can't disagree
# about what ships.
set -euo pipefail

cd "$(dirname "$0")/.."

rm -rf man
mkdir -p man

uv run python3 -c "
import datetime
import importlib.metadata

import typer.main
from click_man.core import write_man_pages

from movie_planner.cli import app

write_man_pages(
    'movie-planner',
    typer.main.get_command(app),
    version=importlib.metadata.version('movie-planner'),
    target_dir='man',
    date=datetime.date.today(),
)
"

# gzip is the convention both dpkg and rpm expect man pages in; nfpm and
# makepkg both just place whatever file is here, they don't compress it
# for you.
gzip -f -9 man/*.1
