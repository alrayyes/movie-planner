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
import click_man.core as click_man_core
from click_man.core import write_man_pages
from click_man.man import ManPage

# click-man's own generate_man_page() collects a command's options with
# 'isinstance(x, click.Option)' - real click.Option, from the click
# package. Typer's own params (TyperOption/TyperArgument) subclass
# typer's *own* internal click shim instead (typer._click.core.Parameter,
# not click.Parameter), confirmed live against typer==0.27.1 - so that
# isinstance check is always False for every Typer app, and every
# generated man page silently loses its whole OPTIONS section, with no
# error anywhere to notice by. Patched here with a duck-typed check
# (param_type_name, which both click's own Option and Typer's shim set
# to 'option') rather than waiting on an upstream click-man fix for a
# Typer version this old.
def _is_documentable_option(param):
    return getattr(param, 'param_type_name', None) == 'option' and not getattr(
        param, 'hidden', False
    )


def _generate_man_page(ctx, version=None, date=None):
    man_page = ManPage(ctx.command_path)
    man_page.version = version
    man_page.short_help = click_man_core.get_short_help_str(ctx.command)
    man_page.description = ctx.command.help
    man_page.synopsis = ' '.join(ctx.command.collect_usage_pieces(ctx))
    man_page.options = [
        x.get_help_record(ctx) for x in ctx.command.params if _is_documentable_option(x)
    ]
    if date:
        man_page.date = date
    commands = getattr(ctx.command, 'commands', None)
    if commands:
        man_page.commands = [
            (k, click_man_core.get_short_help_str(v)) for k, v in commands.items()
        ]
    return str(man_page)


click_man_core.generate_man_page = _generate_man_page

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
