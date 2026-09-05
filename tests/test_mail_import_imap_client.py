from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from movie_planner.mail_import.envelope import MailFetchError
from movie_planner.mail_import.imap_client import ImapMailClient


class FakeImapConnection:
    def __init__(self, *, messages: dict[bytes, bytes] | None = None, fail_login: bool = False):
        self.messages = messages or {}
        self.fail_login = fail_login
        self.logged_out = False
        self.selected: str | None = None
        self.search_calls: list[tuple[str | None, tuple[str, ...]]] = []

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        if self.fail_login:
            raise OSError("boom")
        return "OK", [b"logged in"]

    def select(self, mailbox: str, readonly: bool) -> tuple[str, list[bytes | None]]:
        self.selected = mailbox
        return "OK", [b"1"]

    def search(self, charset: str | None, *criteria: str) -> tuple[str, list[bytes]]:
        self.search_calls.append((charset, criteria))
        return "OK", [b" ".join(self.messages.keys())]

    def fetch(self, message_set: str, message_parts: str) -> tuple[str, list[object]]:
        raw = self.messages[message_set.encode("ascii")]
        return "OK", [(b"1 (RFC822 {123}", raw), b")"]

    def logout(self) -> tuple[str, list[bytes]]:
        self.logged_out = True
        return "BYE", [b"logging out"]


_RAW = (
    b"From: Cinema Chain <noreply@example-chain.com>\n"
    b"Subject: A booking\n"
    b"Date: Sat, 04 Jul 2026 19:00:00 +0200\n"
    b"\n"
    b"body\n"
)


def _client(conn: FakeImapConnection) -> ImapMailClient:
    connect: Callable[[str, int], FakeImapConnection] = lambda host, port: conn  # noqa: E731
    return ImapMailClient(
        host="127.0.0.1", port=1143, username="me", password="secret", connect=connect
    )


def test_fetch_returns_raw_messages_from_search_results() -> None:
    conn = FakeImapConnection(messages={b"1": _RAW})

    raw_messages = list(_client(conn).fetch(["example-chain.com"]))

    assert raw_messages == [_RAW.decode("utf-8")]


def test_fetch_selects_inbox_readonly() -> None:
    conn = FakeImapConnection(messages={b"1": _RAW})

    list(_client(conn).fetch(["example-chain.com"]))

    assert conn.selected == "INBOX"


def test_fetch_always_logs_out() -> None:
    conn = FakeImapConnection(messages={b"1": _RAW})

    list(_client(conn).fetch(["example-chain.com"]))

    assert conn.logged_out is True


def test_fetch_with_no_results_yields_nothing() -> None:
    conn = FakeImapConnection(messages={})

    assert list(_client(conn).fetch(["example-chain.com"])) == []


def test_fetch_connection_failure_raises_mail_fetch_error() -> None:
    conn = FakeImapConnection(fail_login=True)

    with pytest.raises(MailFetchError, match="could not connect"):
        list(_client(conn).fetch(["example-chain.com"]))


def test_fetch_requires_at_least_one_sender_domain() -> None:
    with pytest.raises(ValueError, match="at least one"):
        list(_client(FakeImapConnection()).fetch([]))


def test_search_criteria_single_domain() -> None:
    conn = FakeImapConnection()

    list(_client(conn).fetch(["pathe.nl"]))

    assert conn.search_calls == [(None, ('HEADER FROM "pathe.nl"',))]


def test_search_criteria_multiple_domains_are_ored() -> None:
    conn = FakeImapConnection()

    list(_client(conn).fetch(["pathe.nl", "example.com"]))

    assert conn.search_calls == [(None, ('OR HEADER FROM "pathe.nl" HEADER FROM "example.com"',))]


def test_search_criteria_includes_since_and_until() -> None:
    conn = FakeImapConnection()
    since = datetime(2026, 7, 1, tzinfo=UTC)
    until = datetime(2026, 7, 31, tzinfo=UTC)

    list(_client(conn).fetch(["pathe.nl"], since=since, until=until))

    assert conn.search_calls == [
        (None, ('HEADER FROM "pathe.nl" SINCE "01-Jul-2026" BEFORE "31-Jul-2026"',))
    ]
