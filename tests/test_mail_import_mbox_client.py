from datetime import UTC, datetime
from pathlib import Path

import pytest

from movie_planner.mail_import.envelope import MailFetchError, extract_envelope
from movie_planner.mail_import.mbox_client import MboxMailClient

FIXTURE = Path(__file__).parent / "fixtures" / "sample.mbox"


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
