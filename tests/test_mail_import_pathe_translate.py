import json
import subprocess  # nosec B404
import sys
from pathlib import Path

from fixtures import PATHE_BOOKING_REF, PATHE_EMAIL_PLAIN

REPO_ROOT = Path(__file__).parent.parent


def _run(stdin_text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
        [sys.executable, "-m", "movie_planner.mail_import.pathe_translate"],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


def test_translate_a_recognized_booking_prints_a_row_and_exits_zero() -> None:
    envelope = json.dumps(
        {
            "from": "Pathé Nederland <noreply@pathe.nl>",
            "subject": "Your booking confirmation",
            "date": "2026-08-29T12:00:00+02:00",
            "body": PATHE_EMAIL_PLAIN,
        }
    )

    result = _run(envelope)

    assert result.returncode == 0, result.stderr
    row = json.loads(result.stdout)
    assert row["title"] == "The Dog Stars"
    assert row["date"] == "2026-08-29"
    assert row["medium"] == "cinema"
    assert row["start_time"] == "12:40:00"
    assert row["end_time"] == "14:58:00"
    assert row["venue"] == "Pathé De Munt"
    assert "notes" not in row
    assert "booking_ref" not in row
    assert PATHE_BOOKING_REF not in json.dumps(row)


def test_translate_an_unrecognized_email_writes_stderr_and_exits_nonzero() -> None:
    envelope = json.dumps(
        {
            "from": "Newsletter <news@unrelated-sender.com>",
            "subject": "This week in cinema",
            "date": "2026-07-05T10:00:00+02:00",
            "body": "Not a booking confirmation at all, just a newsletter.",
        }
    )

    result = _run(envelope)

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert result.stderr.strip() != ""


def test_translate_invalid_envelope_json_writes_stderr_and_exits_nonzero() -> None:
    result = _run("not json at all")

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert "envelope JSON" in result.stderr


def test_translate_streams_multiple_envelopes_ndjson_in_ndjson_out() -> None:
    recognized = json.dumps(
        {
            "from": "Pathé Nederland <noreply@pathe.nl>",
            "subject": "Your booking confirmation",
            "date": "2026-08-29T12:00:00+02:00",
            "body": PATHE_EMAIL_PLAIN,
        }
    )
    unrecognized = json.dumps(
        {
            "from": "Newsletter <news@unrelated-sender.com>",
            "subject": "This week in cinema",
            "date": "2026-07-05T10:00:00+02:00",
            "body": "Not a booking confirmation at all.",
        }
    )

    result = _run(f"{recognized}\n{unrecognized}\n{recognized}\n")

    assert result.returncode != 0  # one of the three wasn't recognized
    stdout_lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(stdout_lines) == 2  # the two recognized ones only
    assert all(json.loads(line)["title"] == "The Dog Stars" for line in stdout_lines)
    assert result.stderr.strip() != ""  # the unrecognized one's diagnostic
