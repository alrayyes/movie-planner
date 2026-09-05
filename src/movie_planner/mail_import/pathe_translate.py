"""The Pathé chain's own translation script - a thin, standalone CLI
wrapping movie_planner.pathe.parse_pathe_email, which stays entirely
untouched by this whole tool (design.md's "Chain-specific parsing
lives entirely outside the tool" decision). Reads one envelope as JSON
on stdin, prints one movies.schema.json-shaped row on stdout and exits
0 on success; on anything it doesn't recognize, prints a diagnostic to
stderr, nothing to stdout, and exits non-zero - the same signal a
standalone run and an internally-dispatched run both need (see
design.md's "Envelope-only mode" decision).
"""

import json
import sys
from typing import Any

from movie_planner.pathe import PatheEmailParseError, parse_pathe_email


def _row_from_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    booking = parse_pathe_email(str(envelope["body"]))
    row: dict[str, Any] = {
        "title": booking.title,
        "date": booking.date.isoformat(),
        "medium": "cinema",
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat(),
    }
    if booking.cinema:
        row["venue"] = booking.cinema
    return row


def main() -> None:
    raw = sys.stdin.read()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"pathe-translate: invalid envelope JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        row = _row_from_envelope(envelope)
    except PatheEmailParseError as e:
        print(f"pathe-translate: {e}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, TypeError) as e:
        print(f"pathe-translate: envelope missing expected field: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(row))


if __name__ == "__main__":
    main()
