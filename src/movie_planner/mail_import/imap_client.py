"""IMAP adapter - the same client works against a local Proton Mail
Bridge instance or a Gmail account with no chain-specific logic, config-
only difference (host/port/username/password). See design.md's "One
MailClient port, two adapters" decision.
"""

import imaplib
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from typing import Any, Protocol

from movie_planner.mail_import.envelope import MailFetchError


class _ImapConnection(Protocol):
    def login(self, user: str, password: str) -> tuple[str, Any]: ...
    def select(self, mailbox: str, readonly: bool) -> tuple[str, Any]: ...
    def search(self, charset: str | None, *criteria: str) -> tuple[str, Any]: ...
    def fetch(self, message_set: str, message_parts: str) -> tuple[str, Any]: ...
    def logout(self) -> tuple[str, Any]: ...


def _default_connect(host: str, port: int) -> _ImapConnection:
    return imaplib.IMAP4_SSL(host, port)


class ImapMailClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        connect: Callable[[str, int], _ImapConnection] = _default_connect,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._connect = connect

    def fetch(
        self,
        sender_domains: Sequence[str],
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Iterable[str]:
        if not sender_domains:
            raise ValueError("fetch needs at least one sender domain")

        try:
            conn = self._connect(self._host, self._port)
            conn.login(self._username, self._password)
            conn.select("INBOX", readonly=True)
        except (OSError, imaplib.IMAP4.error) as e:
            raise MailFetchError(f"could not connect to {self._host}: {e}") from e

        try:
            criteria = _search_criteria(sender_domains, since=since, until=until)
            status, data = conn.search(None, criteria)
            if status != "OK":
                raise MailFetchError(f"IMAP search failed: {status}")
            message_ids = data[0].split() if data and data[0] else []

            for message_id in message_ids:
                fetch_status, msg_data = conn.fetch(message_id.decode("ascii"), "(RFC822)")
                if fetch_status != "OK" or not msg_data:
                    continue
                first = msg_data[0]
                if not isinstance(first, tuple) or len(first) < 2:
                    continue
                raw_bytes = first[1]
                if not isinstance(raw_bytes, bytes | bytearray):
                    continue
                yield bytes(raw_bytes).decode("utf-8", errors="replace")
        finally:
            conn.logout()


def _search_criteria(
    sender_domains: Sequence[str], *, since: datetime | None, until: datetime | None
) -> str:
    clauses = [f'FROM "{domain}"' for domain in sender_domains]
    from_clause = clauses[0]
    for clause in clauses[1:]:
        from_clause = f"OR {from_clause} {clause}"

    parts = [from_clause]
    if since is not None:
        parts.append(f'SINCE "{since.strftime("%d-%b-%Y")}"')
    if until is not None:
        parts.append(f'BEFORE "{until.strftime("%d-%b-%Y")}"')
    return " ".join(parts)
