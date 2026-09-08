from datetime import UTC, datetime

import pytest

from movie_planner.mail_import.envelope import MailFetchError
from movie_planner.mail_import.imap_client import ImapMailClient


class FakeImapConnection:
    def __init__(
        self,
        *,
        messages: dict[bytes, bytes] | None = None,
        fail_login: bool = False,
        search_result: tuple[str, list[object]] | None = None,
        fetch_results: dict[bytes, tuple[str, list[object]]] | None = None,
    ) -> None:
        self.messages = messages or {}
        self.fail_login = fail_login
        # None (the default) means "compute the normal OK response from
        # `messages`" - only set to override it with something a real
        # server could return that `messages` can't express (a non-OK
        # status, or an empty/falsy data list).
        self.search_result = search_result
        self.fetch_results = fetch_results or {}
        self.logged_out = False
        self.selected: str | None = None
        self.select_calls: list[tuple[str, bool]] = []
        self.login_calls: list[tuple[str, str]] = []
        self.fetch_calls: list[tuple[str, str]] = []
        self.search_calls: list[tuple[str | None, tuple[str, ...]]] = []

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        self.login_calls.append((user, password))
        if self.fail_login:
            raise OSError("boom")
        return "OK", [b"logged in"]

    def select(self, mailbox: str, readonly: bool) -> tuple[str, list[bytes | None]]:
        self.selected = mailbox
        self.select_calls.append((mailbox, readonly))
        return "OK", [b"1"]

    def search(self, charset: str | None, *criteria: str) -> tuple[str, list[object]]:
        self.search_calls.append((charset, criteria))
        if self.search_result is not None:
            return self.search_result
        return "OK", [b" ".join(self.messages.keys())]

    def fetch(self, message_set: str, message_parts: str) -> tuple[str, list[object]]:
        self.fetch_calls.append((message_set, message_parts))
        override = self.fetch_results.get(message_set.encode("ascii"))
        if override is not None:
            return override
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


def _client(
    conn: FakeImapConnection, *, connect_calls: list[tuple[str, int]] | None = None
) -> ImapMailClient:
    def connect(host: str, port: int) -> FakeImapConnection:
        if connect_calls is not None:
            connect_calls.append((host, port))
        return conn

    return ImapMailClient(
        host="127.0.0.1", port=1143, username="me", password="secret", connect=connect
    )


def test_fetch_returns_raw_messages_from_search_results() -> None:
    conn = FakeImapConnection(messages={b"1": _RAW})

    raw_messages = list(_client(conn).fetch(["example-chain.com"]))

    assert raw_messages == [_RAW.decode("utf-8")]


def test_fetch_connects_to_the_configured_host_and_port() -> None:
    conn = FakeImapConnection(messages={b"1": _RAW})
    connect_calls: list[tuple[str, int]] = []

    list(_client(conn, connect_calls=connect_calls).fetch(["example-chain.com"]))

    assert connect_calls == [("127.0.0.1", 1143)]


def test_fetch_logs_in_with_the_configured_credentials() -> None:
    conn = FakeImapConnection(messages={b"1": _RAW})

    list(_client(conn).fetch(["example-chain.com"]))

    assert conn.login_calls == [("me", "secret")]


def test_fetch_selects_inbox_readonly() -> None:
    conn = FakeImapConnection(messages={b"1": _RAW})

    list(_client(conn).fetch(["example-chain.com"]))

    assert conn.selected == "INBOX"
    assert conn.select_calls == [("INBOX", True)]


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
    with pytest.raises(ValueError) as exc_info:
        list(_client(FakeImapConnection()).fetch([]))

    # Exact message, not just a substring - a mutated message that still
    # happens to contain "at least one" as a substring would otherwise
    # still pass.
    assert str(exc_info.value) == "fetch needs at least one sender domain"


def test_fetch_search_failure_raises_with_the_exact_status() -> None:
    conn = FakeImapConnection(search_result=("NO", [b"search error"]))

    with pytest.raises(MailFetchError) as exc_info:
        list(_client(conn).fetch(["example-chain.com"]))

    assert str(exc_info.value) == "IMAP search failed: NO"


def test_fetch_with_empty_search_data_yields_nothing_rather_than_crashing() -> None:
    # A real server can return ("OK", []) - no data element at all, not
    # just an empty message list inside one. `data and data[0]` has to
    # short-circuit on `data` itself here, or indexing data[0] crashes.
    conn = FakeImapConnection(search_result=("OK", []))

    assert list(_client(conn).fetch(["example-chain.com"])) == []


def test_fetch_passes_the_exact_message_set_and_parts_to_fetch() -> None:
    conn = FakeImapConnection(messages={b"1": _RAW})

    list(_client(conn).fetch(["example-chain.com"]))

    assert conn.fetch_calls == [("1", "(RFC822)")]


def test_fetch_skips_a_non_ok_fetch_status_but_keeps_checking_later_ids() -> None:
    conn = FakeImapConnection(
        messages={b"1": _RAW, b"2": _RAW},
        fetch_results={b"1": ("NO", [(b"1 (RFC822 {123}", _RAW), b")"])},
    )

    raw_messages = list(_client(conn).fetch(["example-chain.com"]))

    # Message 1's bad status is skipped (continue), not fatal to the
    # whole fetch (break) - message 2 still comes through.
    assert raw_messages == [_RAW.decode("utf-8")]


def test_fetch_skips_empty_msg_data_even_with_an_ok_status() -> None:
    # fetch_status == "OK" and msg_data == [] both need to matter
    # independently - `or`, not `and`, between the two checks.
    conn = FakeImapConnection(
        messages={b"1": _RAW, b"2": _RAW},
        fetch_results={b"1": ("OK", [])},
    )

    raw_messages = list(_client(conn).fetch(["example-chain.com"]))

    assert raw_messages == [_RAW.decode("utf-8")]


def test_fetch_skips_a_non_tuple_first_element_but_keeps_checking_later_ids() -> None:
    # A first element that isn't a tuple (a list, here) has to be
    # rejected regardless of its length - `or`, not `and`, between the
    # isinstance and length checks. A length-2+ list whose [1] happens
    # to be bytes would otherwise slip through and get wrongly yielded.
    conn = FakeImapConnection(
        messages={b"1": _RAW, b"2": _RAW},
        fetch_results={b"1": ("OK", [[b"1 (RFC822 {123}", _RAW, b")"]])},
    )

    raw_messages = list(_client(conn).fetch(["example-chain.com"]))

    assert raw_messages == [_RAW.decode("utf-8")]


def test_fetch_skips_a_short_tuple_but_keeps_checking_later_ids() -> None:
    conn = FakeImapConnection(
        messages={b"1": _RAW, b"2": _RAW},
        fetch_results={b"1": ("OK", [(b"1 (RFC822 {123}",)])},
    )

    raw_messages = list(_client(conn).fetch(["example-chain.com"]))

    assert raw_messages == [_RAW.decode("utf-8")]


def test_fetch_skips_a_non_bytes_payload_but_keeps_checking_later_ids() -> None:
    conn = FakeImapConnection(
        messages={b"1": _RAW, b"2": _RAW},
        fetch_results={b"1": ("OK", [(b"1 (RFC822 {123}", "not bytes"), b")"])},
    )

    raw_messages = list(_client(conn).fetch(["example-chain.com"]))

    assert raw_messages == [_RAW.decode("utf-8")]


def test_fetch_decodes_invalid_utf8_with_replacement_rather_than_raising() -> None:
    # errors="replace" (not the "strict" default, and not any other
    # handler name) is what makes a malformed raw message survive as a
    # replacement-character string instead of blowing up the whole
    # fetch.
    invalid = b"From: a@b.com\nSubject: bad \xff\xfe bytes\n\nbody\n"
    conn = FakeImapConnection(messages={b"1": invalid})

    (raw,) = list(_client(conn).fetch(["example-chain.com"]))

    assert "�" in raw


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
