"""Runs before pytest collects any test module - Typer/rich forces styled
--help output whenever $GITHUB_ACTIONS is set (rich_utils.FORCE_TERMINAL),
even though CliRunner captures to a StringIO, not a real terminal. That
splits "--flag" text across ANSI escape codes and breaks any literal
substring check against --help output - only reproduces on CI, never
locally, since $GITHUB_ACTIONS isn't set there (issue #258).

This has to be a module-level statement, not a fixture: rich_utils reads
the env var once at import time, and by the time a fixture runs, Typer is
already imported and FORCE_TERMINAL already decided.
"""

import os

os.environ.setdefault("_TYPER_FORCE_DISABLE_TERMINAL", "1")
