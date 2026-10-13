import mailbox
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from movie_planner.mail_import.envelope import MailFetchError, extract_envelope
from movie_planner.mail_import.maildir_client import MaildirMailClient

FIXTURE = Path(__file__).parent / "fixtures" / "sample_maildir"


def _message(*, date: str | None, subject: str) -> str:
    date_header = f"Date: {date}\n" if date is not None else ""
    return (
        "From: Cinema Chain <noreply@example-chain.com>\n"
        "To: someone@example.com\n"
        f"Subject: {subject}\n"
        f"{date_header}"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        f"{subject} body\n"
    )


def _write_maildir(tmp_path: Path, *messages: str) -> Path:
    """Writes each message to its own file under a fresh Maildir - a
    freshly re-opened mailbox.Maildir iterates them in the *reverse* of
    the order they were added here (verified empirically, consistent
    across repeated runs on this filesystem - mailbox.Maildir's own
    iteration order is otherwise unspecified). Callers relying on
    iteration order (the continue-vs-break tests below) pass the
    message that should be reached *last* first, so it's written (and
    therefore iterated) after the one a bug would wrongly cut off.
    """
    path = tmp_path / "maildir"
    box = mailbox.Maildir(str(path), create=True)
    for message in messages:
        box.add(message)
    box.close()
    return path


def test_fetch_returns_only_matching_sender_domain_messages() -> None:
    client = MaildirMailClient(FIXTURE)

    raw_messages = list(client.fetch(["example-chain.com"]))

    assert len(raw_messages) == 2
    subjects = {extract_envelope(raw).subject for raw in raw_messages}
    assert subjects == {
        "Your Maildir booking confirmation",
        "A second Maildir booking confirmation",
    }


def test_fetch_with_no_matching_domain_returns_nothing() -> None:
    client = MaildirMailClient(FIXTURE)

    assert list(client.fetch(["nobody-sends-from-here.example"])) == []


def test_fetch_is_case_insensitive_on_domain() -> None:
    client = MaildirMailClient(FIXTURE)

    assert len(list(client.fetch(["Example-Chain.COM"]))) == 2


def test_fetch_scoped_to_a_since_date_excludes_earlier_messages() -> None:
    client = MaildirMailClient(FIXTURE)
    since = datetime(2026, 7, 6, 0, 0, tzinfo=UTC)

    raw_messages = list(client.fetch(["example-chain.com"], since=since))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "A second Maildir booking confirmation"


def test_fetch_scoped_to_an_until_date_excludes_later_messages() -> None:
    client = MaildirMailClient(FIXTURE)
    until = datetime(2026, 7, 5, 0, 0, tzinfo=UTC)

    raw_messages = list(client.fetch(["example-chain.com"], until=until))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "Your Maildir booking confirmation"


def test_fetch_with_no_range_returns_everything_matching() -> None:
    client = MaildirMailClient(FIXTURE)

    assert len(list(client.fetch(["example-chain.com"]))) == 2


def test_fetch_missing_directory_raises() -> None:
    client = MaildirMailClient(Path("/nonexistent/path/to/maildir"))

    with pytest.raises(MailFetchError, match="not found"):
        list(client.fetch(["example-chain.com"]))


# --- Date header handling: a skip must never abort the rest of the maildir ---


def test_fetch_skips_a_message_with_no_date_header_but_still_yields_later_ones(
    tmp_path: Path,
) -> None:
    path = _write_maildir(
        tmp_path,
        _message(date="Mon, 06 Jul 2026 08:00:00 +0200", subject="Has a date"),
        _message(date=None, subject="No date at all"),
    )
    client = MaildirMailClient(path)

    raw_messages = list(client.fetch(["example-chain.com"]))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "Has a date"


def test_fetch_skips_a_message_with_an_unparseable_date_but_still_yields_later_ones(
    tmp_path: Path,
) -> None:
    path = _write_maildir(
        tmp_path,
        _message(date="Mon, 06 Jul 2026 08:00:00 +0200", subject="Has a date"),
        _message(date="not a real date", subject="Bad date"),
    )
    client = MaildirMailClient(path)

    raw_messages = list(client.fetch(["example-chain.com"]))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "Has a date"


def test_fetch_a_message_dated_exactly_at_since_is_included() -> None:
    # since is an inclusive lower bound - a message at exactly that
    # instant belongs to it, not before it.
    client = MaildirMailClient(FIXTURE)
    since = datetime(2026, 7, 4, 19, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    raw_messages = list(client.fetch(["example-chain.com"], since=since))

    subjects = {extract_envelope(raw).subject for raw in raw_messages}
    assert "Your Maildir booking confirmation" in subjects


def test_fetch_a_message_dated_exactly_at_until_is_excluded() -> None:
    # until is an exclusive upper bound - a message at exactly that
    # instant belongs to the next window, not this one.
    client = MaildirMailClient(FIXTURE)
    until = datetime(2026, 7, 4, 19, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    raw_messages = list(client.fetch(["example-chain.com"], until=until))

    subjects = {extract_envelope(raw).subject for raw in raw_messages}
    assert "Your Maildir booking confirmation" not in subjects


def test_fetch_skips_a_message_before_since_but_still_yields_later_ones(
    tmp_path: Path,
) -> None:
    path = _write_maildir(
        tmp_path,
        _message(date="Mon, 06 Jul 2026 08:00:00 +0200", subject="In range"),
        _message(date="Sat, 04 Jul 2026 19:00:00 +0200", subject="Too early"),
    )
    client = MaildirMailClient(path)
    since = datetime(2026, 7, 5, tzinfo=UTC)

    raw_messages = list(client.fetch(["example-chain.com"], since=since))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "In range"
