from datetime import datetime, timedelta, timezone

import pytest

from movie_planner.mail_import.envelope import (
    MailFetchError,
    extract_envelope,
    sender_domain,
)

_RAW_EMAIL = (
    "From: Cinema Chain <noreply@example-chain.com>\n"
    "To: someone@example.com\n"
    "Subject: Your booking confirmation\n"
    "Date: Sat, 04 Jul 2026 19:00:00 +0200\n"
    "Content-Type: text/plain; charset=utf-8\n"
    "\n"
    "Good Boy\n"
    "=========\n"
    "\n"
    "Booking number\n"
    "AB1CD23\n"
)


def test_extract_envelope_reads_from_subject_date_and_body() -> None:
    envelope = extract_envelope(_RAW_EMAIL)

    assert envelope.from_address == "Cinema Chain <noreply@example-chain.com>"
    assert envelope.subject == "Your booking confirmation"
    assert envelope.date == datetime(2026, 7, 4, 19, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    assert "Good Boy" in envelope.body
    assert "AB1CD23" in envelope.body


def test_extract_envelope_rejects_content_with_no_headers() -> None:
    with pytest.raises(MailFetchError, match="no RFC822 headers"):
        extract_envelope("just some plain text\n\nwith a blank line\n")


def test_extract_envelope_rejects_a_missing_date_header() -> None:
    raw = "From: a@example.com\nSubject: hi\n\nbody\n"

    with pytest.raises(MailFetchError, match="no Date header"):
        extract_envelope(raw)


def test_sender_domain_extracts_and_lowercases_the_domain() -> None:
    assert sender_domain("Pathé Nederland <noreply@Pathe.NL>") == "pathe.nl"


def test_sender_domain_with_no_address_is_none() -> None:
    assert sender_domain("not an email address") is None
