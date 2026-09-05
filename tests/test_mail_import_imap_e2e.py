"""Real IMAP protocol conversation against a GreenMail container - see
greenmail_container.py. Complements test_mail_import_imap_client.py's
fake-connection unit tests, which cover branching/error handling far
more cheaply than a container spin-up per case can.

Connects with plain (non-SSL) `imaplib.IMAP4` against GreenMail's
plaintext port, not `ImapMailClient`'s own default `IMAP4_SSL` - a
self-signed cert would need its own verification dance unrelated to
what this test is actually for (the real search/fetch/parse
conversation). **This surfaced a real gap while writing it**: real
Proton Bridge listens with STARTTLS on a local plaintext connection,
not implicit TLS - ImapMailClient's IMAP4_SSL-only default may not
actually work against it. Flagged in tasks.md as a follow-up, not
fixed here (out of scope for this PR).
"""

from collections.abc import Iterator
from imaplib import IMAP4

import pytest
from greenmail_container import GreenmailTestServer, deliver_test_email, start_greenmail

from movie_planner.mail_import.envelope import extract_envelope
from movie_planner.mail_import.imap_client import ImapMailClient


@pytest.fixture(scope="module")
def greenmail() -> Iterator[GreenmailTestServer]:
    container, server = start_greenmail()
    try:
        yield server
    finally:
        container.stop()


def test_fetch_retrieves_a_real_delivered_email(greenmail: GreenmailTestServer) -> None:
    deliver_test_email(
        greenmail,
        sender="noreply@example-chain.com",
        recipient="moviewatcher@example-chain.com",
        subject="Your booking confirmation",
        body="Good Boy\n=========\n\nBooking number\nAB1CD23\n",
    )

    client = ImapMailClient(
        host=greenmail.imap_host,
        port=greenmail.imap_port,
        username="moviewatcher@example-chain.com",
        password="anything-auth-is-disabled",
        connect=lambda host, port: IMAP4(host, port),
    )

    raw_messages = list(client.fetch(["example-chain.com"]))

    assert len(raw_messages) == 1
    envelope = extract_envelope(raw_messages[0])
    assert envelope.subject == "Your booking confirmation"
    assert "AB1CD23" in envelope.body


def test_fetch_with_no_matching_domain_returns_nothing(greenmail: GreenmailTestServer) -> None:
    client = ImapMailClient(
        host=greenmail.imap_host,
        port=greenmail.imap_port,
        username="moviewatcher@example-chain.com",
        password="anything-auth-is-disabled",
        connect=lambda host, port: IMAP4(host, port),
    )

    raw_messages = list(client.fetch(["nobody-sends-from-here.example"]))

    assert raw_messages == []
