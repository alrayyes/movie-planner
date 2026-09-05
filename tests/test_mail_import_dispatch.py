import json
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path

from fixtures import PATHE_EMAIL_PLAIN

from movie_planner.mail_import.config import ChainConfig
from movie_planner.mail_import.dispatch import dispatch, dispatch_all
from movie_planner.mail_import.envelope import MailEnvelope

_ENVELOPE = MailEnvelope(
    from_address="Cinema Chain <noreply@example-chain.com>",
    subject="Your booking confirmation",
    date=datetime(2026, 7, 4, 19, 0, tzinfo=UTC),
    body="Good Boy\n=========\n\nBooking number\nAB1CD23\n",
)


def _write_script(tmp_path: Path, body: str) -> str:
    script_path = tmp_path / "fake-translate.py"
    script_path.write_text(body)
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    return f"{sys.executable} {script_path}"


_ECHO_ROW_SCRIPT = """\
import json
import sys

envelope = json.load(sys.stdin)
print(json.dumps({"title": "Good Boy", "date": "2026-07-04", "medium": "cinema"}))
"""

_REJECT_SCRIPT = """\
import sys

sys.stdin.read()
print("not recognized", file=sys.stderr)
sys.exit(1)
"""

_INVALID_JSON_SCRIPT = """\
import sys

sys.stdin.read()
print("not json")
"""


def test_dispatch_recognized_email_returns_a_stamped_row(tmp_path: Path) -> None:
    translate = _write_script(tmp_path, _ECHO_ROW_SCRIPT)
    chains = (ChainConfig(sender_domain="example-chain.com", translate=translate),)

    result = dispatch(_ENVELOPE, chains)

    assert result.row is not None
    assert result.row["title"] == "Good Boy"
    assert result.row["source"] == "example-chain.com"


def test_dispatch_script_receives_the_envelope_as_json_on_stdin(tmp_path: Path) -> None:
    capture_path = tmp_path / "captured.json"
    script = f"""\
import json
import sys

envelope = json.load(sys.stdin)
open({str(capture_path)!r}, "w").write(json.dumps(envelope))
print(json.dumps({{"title": "x", "date": "2026-07-04", "medium": "cinema"}}))
"""
    translate = _write_script(tmp_path, script)
    chains = (ChainConfig(sender_domain="example-chain.com", translate=translate),)

    dispatch(_ENVELOPE, chains)

    captured = json.loads(capture_path.read_text())
    assert captured["from"] == _ENVELOPE.from_address
    assert captured["subject"] == _ENVELOPE.subject
    assert captured["body"] == _ENVELOPE.body


def test_dispatch_script_exits_nonzero_is_unrecognized(tmp_path: Path) -> None:
    translate = _write_script(tmp_path, _REJECT_SCRIPT)
    chains = (ChainConfig(sender_domain="example-chain.com", translate=translate),)

    result = dispatch(_ENVELOPE, chains)

    assert result.row is None
    assert result.envelope == _ENVELOPE


def test_dispatch_script_prints_invalid_json_is_unrecognized(tmp_path: Path) -> None:
    translate = _write_script(tmp_path, _INVALID_JSON_SCRIPT)
    chains = (ChainConfig(sender_domain="example-chain.com", translate=translate),)

    result = dispatch(_ENVELOPE, chains)

    assert result.row is None


def test_dispatch_no_configured_chain_for_sender_domain_is_unrecognized() -> None:
    chains = (ChainConfig(sender_domain="somewhere-else.com", translate="irrelevant"),)

    result = dispatch(_ENVELOPE, chains)

    assert result.row is None


def test_dispatch_no_chains_at_all_is_unrecognized() -> None:
    result = dispatch(_ENVELOPE, ())

    assert result.row is None


def test_dispatch_all_splits_recognized_and_unrecognized(tmp_path: Path) -> None:
    recognized_translate = _write_script(tmp_path, _ECHO_ROW_SCRIPT)
    other_envelope = MailEnvelope(
        from_address="Newsletter <news@unrelated-sender.com>",
        subject="This week in cinema",
        date=datetime(2026, 7, 5, tzinfo=UTC),
        body="not a booking",
    )
    chains = (ChainConfig(sender_domain="example-chain.com", translate=recognized_translate),)

    rows, unrecognized = dispatch_all([_ENVELOPE, other_envelope], chains)

    assert len(rows) == 1
    assert rows[0]["source"] == "example-chain.com"
    assert unrecognized == [other_envelope]


# --- against the real pathe-translate script, not a fake one: task 8.2 ---


def test_dispatch_against_the_real_pathe_translate_script_recognized() -> None:
    envelope = MailEnvelope(
        from_address="Pathé Nederland <noreply@pathe.nl>",
        subject="Your booking confirmation",
        date=datetime(2026, 8, 29, 12, 0, tzinfo=UTC),
        body=PATHE_EMAIL_PLAIN,
    )
    chains = (
        ChainConfig(
            sender_domain="pathe.nl",
            translate=f"{sys.executable} -m movie_planner.mail_import.pathe_translate",
        ),
    )

    result = dispatch(envelope, chains)

    assert result.row is not None
    assert result.row["title"] == "The Dog Stars"
    assert result.row["source"] == "pathe.nl"


def test_dispatch_against_the_real_pathe_translate_script_unrecognized() -> None:
    envelope = MailEnvelope(
        from_address="Pathé Nederland <noreply@pathe.nl>",
        subject="Newsletter",
        date=datetime(2026, 7, 5, tzinfo=UTC),
        body="Not a booking confirmation at all.",
    )
    chains = (
        ChainConfig(
            sender_domain="pathe.nl",
            translate=f"{sys.executable} -m movie_planner.mail_import.pathe_translate",
        ),
    )

    result = dispatch(envelope, chains)

    assert result.row is None
