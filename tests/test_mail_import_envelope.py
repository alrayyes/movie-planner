from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import pytest
from fixtures import (
    PATHE_EMAIL_HTML_ONLY,
    PATHE_EMAIL_LEGACY_HTML,
    PATHE_EMAIL_MISLABELED_ATTACHMENT,
    PATHE_HTML_BOOKING_REF,
    PATHE_MISLABELED_ATTACHMENT_BOOKING_REF,
)

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


# --- HTML-only fallback: movie-planner#158 ---


def test_extract_envelope_falls_back_to_html_when_no_plain_part() -> None:
    envelope = extract_envelope(PATHE_EMAIL_HTML_ONLY)

    assert envelope.from_address == "Pathé <no-reply@service.pathe.nl>"
    assert "Spider-Man: Brand New Day" in envelope.body
    assert PATHE_HTML_BOOKING_REF in envelope.body
    # Tags themselves shouldn't leak into the plain-text body a
    # translation script parses.
    assert "<h2" not in envelope.body
    assert "<p>" not in envelope.body


def test_extract_envelope_html_fallback_collapses_nbsp_and_tags_to_plain_lines() -> None:
    envelope = extract_envelope(PATHE_EMAIL_HTML_ONLY)

    assert "Expected end time: 16:30" in envelope.body


# --- non-informative text/plain alongside a real HTML part: movie-planner#171 ---


def test_extract_envelope_falls_back_to_html_when_the_plain_part_has_no_digits() -> None:
    # A real Pathé confirmation of this template carries a generated,
    # non-informative text/plain alternative ("view this in an HTML-
    # capable client") alongside the real content in HTML - it has no
    # digits at all, unlike every genuine booking confirmation.
    envelope = extract_envelope(PATHE_EMAIL_LEGACY_HTML)

    assert "Insidious: Out of the Further" in envelope.body
    assert "Booking number" in envelope.body


def test_extract_envelope_falls_back_to_html_when_the_placeholder_has_a_url_with_digits() -> None:
    # movie-planner#200: a "view this in your browser" placeholder whose
    # tracking URL happens to contain a digit defeats the plain digit
    # check above - the placeholder itself has no *real* digit (a date,
    # a time, a seat), just one buried in a URL. Found on real, much
    # older Pathé confirmations (2013-2019) that use this exact shape.
    msg = EmailMessage()
    msg["From"] = "Cinema Chain <noreply@example-chain.com>"
    msg["Subject"] = "Booking confirmation"
    msg["Date"] = "Sat, 04 Jul 2026 19:00:00 +0200"
    msg.set_content(
        "Probably your email client doesn't support HTML.\n"
        "Visit the following page to read this message in your browser:\n"
        "http://chain.example/x/?S7Y1NPqfa2tsbvy.yNbM3NzcxPx.gW1xclFmQUl8cWkSiJWUCgAA12\n"
    )
    msg.add_alternative(
        "<html><body><h1>Good Boy</h1><p>Saturday 4 July 2026, 19:00</p></body></html>",
        subtype="html",
    )

    envelope = extract_envelope(msg.as_string())

    assert "Good Boy" in envelope.body
    assert "chain.example" not in envelope.body


# --- mislabeled text/plain attachment: movie-planner#191 ---


def test_extract_envelope_skips_a_text_plain_part_marked_as_an_attachment() -> None:
    # Pathé's own mail template mislabels the PDF ticket attachment as
    # Content-Type: text/plain - Content-Disposition: attachment is
    # still correct, and is what should exclude it from ever being
    # picked as the message body, mislabeled type or not.
    envelope = extract_envelope(PATHE_EMAIL_MISLABELED_ATTACHMENT)

    assert "Spider-Man: Brand New Day" in envelope.body
    assert PATHE_MISLABELED_ATTACHMENT_BOOKING_REF in envelope.body
    assert "fake ticket attachment content" not in envelope.body


def test_extract_envelope_with_neither_plain_nor_html_returns_empty_body() -> None:
    msg = EmailMessage()
    msg["From"] = "Cinema Chain <noreply@example-chain.com>"
    msg["Subject"] = "Your booking confirmation"
    msg["Date"] = "Sat, 04 Jul 2026 19:00:00 +0200"
    msg.add_attachment(b"not text", maintype="application", subtype="octet-stream")

    envelope = extract_envelope(msg.as_string())

    assert envelope.body == ""
