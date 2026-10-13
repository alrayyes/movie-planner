"""The Pathé chain's own translation script - a thin, standalone CLI
wrapping movie_planner.pathe.parse_pathe_email, which stays entirely
untouched by this whole tool (design.md's "Chain-specific parsing
lives entirely outside the tool" decision).

Reads one JSON envelope per line on stdin (a single line when invoked
internally by the fetch tool's own dispatch, one call per envelope; a
whole NDJSON stream when run standalone in a piped
`fetch --envelopes-only | pathe-translate | movie-planner import`).
For each line: a recognized booking prints one movies.schema.json-
shaped row on stdout; anything not recognized prints a diagnostic to
stderr instead and contributes nothing to stdout - the same "nothing
on stdout, something on stderr" signal works whether dispatch.py is
reading this script's exit code (single-line case) or nobody's
watching the exit code at all (piped case) - see design.md's
"Envelope-only mode" decision.
"""

import json
import sys
from datetime import datetime
from typing import Any

from movie_planner.pathe import PatheEmailParseError, parse_pathe_email


def _row_from_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    # The envelope's own "date" field (the email's Date header) is the
    # only source of a year for the Dutch templates parse_pathe_email
    # itself can't date (movie-planner#200) - every other template
    # ignores it.
    received_date = datetime.fromisoformat(str(envelope["date"])).date()
    booking = parse_pathe_email(str(envelope["body"]), received_date=received_date)
    row: dict[str, Any] = {
        "title": booking.title,
        "date": booking.date.isoformat(),
        "medium": "cinema",
        "start_time": booking.start_time.isoformat(),
    }
    if booking.end_time is not None:
        row["end_time"] = booking.end_time.isoformat()
    if booking.cinema:
        row["venue"] = booking.cinema
    if booking.row:
        row["row"] = booking.row
    if booking.seat:
        row["seat"] = booking.seat
    return row


def main() -> None:
    any_unrecognized = False

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            envelope = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"pathe-translate: invalid envelope JSON on stdin: {e}", file=sys.stderr)
            any_unrecognized = True
            continue

        try:
            row = _row_from_envelope(envelope)
        except PatheEmailParseError as e:
            print(f"pathe-translate: {e}", file=sys.stderr)
            any_unrecognized = True
            continue
        except (KeyError, TypeError) as e:
            print(f"pathe-translate: envelope missing expected field: {e}", file=sys.stderr)
            any_unrecognized = True
            continue

        print(json.dumps(row))

    if any_unrecognized:
        sys.exit(1)


if __name__ == "__main__":
    main()
