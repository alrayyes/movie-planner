import stat
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from movie_planner.mail_import.envelope import MailFetchError, extract_envelope
from movie_planner.mail_import.mbox_client import MboxMailClient

FIXTURE = Path(__file__).parent / "fixtures" / "sample.mbox"
ARCHIVE_FIXTURE = Path(__file__).parent / "fixtures" / "sample_archive.mbox"


def _message(
    *,
    sender: str = "noreply@example-chain.com",
    date: str | None,
    message_id: str,
    subject: str,
) -> str:
    # The mbox envelope's own "From ..." line is just a message
    # delimiter to `mailbox.mbox` - its content is never read by this
    # module, so a fixed placeholder is fine regardless of what (if
    # anything) the real Date: header below says.
    date_header = f"Date: {date}\n" if date is not None else ""
    return (
        "From MAILER-DAEMON Mon Jan 01 00:00:00 2024\n"
        f"From: Cinema Chain <{sender}>\n"
        "To: someone@example.com\n"
        f"Subject: {subject}\n"
        f"{date_header}"
        f"Message-ID: <{message_id}@example-chain.com>\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        f"{subject} body\n"
    )


def _write_mbox(tmp_path: Path, *messages: str) -> Path:
    path = tmp_path / "test.mbox"
    path.write_text("\n".join(messages))
    return path


def test_fetch_returns_only_matching_sender_domain_messages() -> None:
    client = MboxMailClient(FIXTURE)

    raw_messages = list(client.fetch(["example-chain.com"]))

    assert len(raw_messages) == 2
    subjects = {extract_envelope(raw).subject for raw in raw_messages}
    assert subjects == {"Your booking confirmation", "A second booking confirmation"}


def test_fetch_with_no_matching_domain_returns_nothing() -> None:
    client = MboxMailClient(FIXTURE)

    assert list(client.fetch(["nobody-sends-from-here.example"])) == []


def test_fetch_is_case_insensitive_on_domain() -> None:
    client = MboxMailClient(FIXTURE)

    assert len(list(client.fetch(["Example-Chain.COM"]))) == 2


def test_fetch_scoped_to_a_since_date_excludes_earlier_messages() -> None:
    client = MboxMailClient(FIXTURE)
    since = datetime(2026, 7, 6, 0, 0, tzinfo=UTC)

    raw_messages = list(client.fetch(["example-chain.com"], since=since))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "A second booking confirmation"


def test_fetch_scoped_to_an_until_date_excludes_later_messages() -> None:
    client = MboxMailClient(FIXTURE)
    until = datetime(2026, 7, 5, 0, 0, tzinfo=UTC)

    raw_messages = list(client.fetch(["example-chain.com"], until=until))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "Your booking confirmation"


def test_fetch_with_no_range_returns_everything_matching() -> None:
    client = MboxMailClient(FIXTURE)

    assert len(list(client.fetch(["example-chain.com"]))) == 2


def test_fetch_missing_file_raises() -> None:
    client = MboxMailClient(Path("/nonexistent/path/to.mbox"))

    with pytest.raises(MailFetchError, match="not found"):
        list(client.fetch(["example-chain.com"]))


# --- extra_paths: issue #188 ---


def test_fetch_merges_messages_from_extra_paths() -> None:
    client = MboxMailClient(FIXTURE, extra_paths=[ARCHIVE_FIXTURE])

    raw_messages = list(client.fetch(["example-chain.com"]))
    subjects = {extract_envelope(raw).subject for raw in raw_messages}

    assert "An archived booking confirmation" in subjects
    assert "Your booking confirmation" in subjects
    assert "A second booking confirmation" in subjects


def test_fetch_deduplicates_the_same_message_id_across_paths() -> None:
    # sample_archive.mbox includes a copy of sample.mbox's first message
    # (same Message-ID) - real Thunderbird archiving shouldn't produce
    # this, but a stray copy anywhere shouldn't surface as two rows.
    client = MboxMailClient(FIXTURE, extra_paths=[ARCHIVE_FIXTURE])

    raw_messages = list(client.fetch(["example-chain.com"]))
    subjects = [extract_envelope(raw).subject for raw in raw_messages]

    assert subjects.count("Your booking confirmation") == 1


def test_fetch_with_extra_paths_still_applies_the_since_until_range() -> None:
    client = MboxMailClient(FIXTURE, extra_paths=[ARCHIVE_FIXTURE])
    since = datetime(2026, 1, 1, tzinfo=UTC)

    raw_messages = list(client.fetch(["example-chain.com"], since=since))
    subjects = {extract_envelope(raw).subject for raw in raw_messages}

    # The archive-only booking predates `since` and is excluded, same as
    # any other out-of-range message.
    assert "An archived booking confirmation" not in subjects


def test_fetch_missing_extra_path_raises() -> None:
    client = MboxMailClient(FIXTURE, extra_paths=[Path("/nonexistent/archive.mbox")])

    with pytest.raises(MailFetchError, match="not found"):
        list(client.fetch(["example-chain.com"]))


def test_fetch_unreadable_file_raises_with_the_underlying_error(tmp_path: Path) -> None:
    # A path that passes the earlier is_file() check but that
    # mailbox.mbox() itself can't open (permissions, here) - a
    # different failure from "not found", with its own message.
    path = _write_mbox(
        tmp_path, _message(date="Sat, 04 Jul 2026 19:00:00 +0200", message_id="1", subject="x")
    )
    path.chmod(0)
    client = MboxMailClient(path)

    try:
        with pytest.raises(MailFetchError) as exc_info:
            list(client.fetch(["example-chain.com"]))
        assert str(path) in str(exc_info.value)
        assert "could not read mbox file" in str(exc_info.value)
    finally:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # restore so tmp_path cleanup can delete it


# --- Date header handling: a skip must never abort the rest of the mbox ---


def test_fetch_skips_a_message_with_no_date_header_but_still_yields_later_ones(
    tmp_path: Path,
) -> None:
    path = _write_mbox(
        tmp_path,
        _message(date=None, message_id="1", subject="No date at all"),
        _message(date="Mon, 06 Jul 2026 08:00:00 +0200", message_id="2", subject="Has a date"),
    )
    client = MboxMailClient(path)

    raw_messages = list(client.fetch(["example-chain.com"]))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "Has a date"


def test_fetch_skips_a_message_with_an_unparseable_date_but_still_yields_later_ones(
    tmp_path: Path,
) -> None:
    path = _write_mbox(
        tmp_path,
        _message(date="not a real date", message_id="1", subject="Bad date"),
        _message(date="Mon, 06 Jul 2026 08:00:00 +0200", message_id="2", subject="Has a date"),
    )
    client = MboxMailClient(path)

    raw_messages = list(client.fetch(["example-chain.com"]))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "Has a date"


def test_fetch_a_message_dated_exactly_at_since_is_included() -> None:
    # since is an inclusive lower bound - a message at exactly that
    # instant belongs to it, not before it.
    client = MboxMailClient(FIXTURE)
    since = datetime(2026, 7, 4, 19, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    raw_messages = list(client.fetch(["example-chain.com"], since=since))

    assert extract_envelope(raw_messages[0]).subject == "Your booking confirmation"


def test_fetch_a_message_dated_exactly_at_until_is_excluded() -> None:
    # until is an exclusive upper bound - a message at exactly that
    # instant belongs to the next window, not this one.
    client = MboxMailClient(FIXTURE)
    until = datetime(2026, 7, 4, 19, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    raw_messages = list(client.fetch(["example-chain.com"], until=until))

    assert "Your booking confirmation" not in {
        extract_envelope(raw).subject for raw in raw_messages
    }


def test_fetch_skips_a_message_past_until_but_still_yields_earlier_ones(tmp_path: Path) -> None:
    path = _write_mbox(
        tmp_path,
        _message(date="Mon, 06 Jul 2026 08:00:00 +0200", message_id="1", subject="Too late"),
        _message(date="Sat, 04 Jul 2026 19:00:00 +0200", message_id="2", subject="In range"),
    )
    client = MboxMailClient(path)
    until = datetime(2026, 7, 5, tzinfo=UTC)

    raw_messages = list(client.fetch(["example-chain.com"], until=until))

    assert len(raw_messages) == 1
    assert extract_envelope(raw_messages[0]).subject == "In range"
