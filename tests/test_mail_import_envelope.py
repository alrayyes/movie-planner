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
    with pytest.raises(MailFetchError) as exc_info:
        extract_envelope("just some plain text\n\nwith a blank line\n")

    # Exact message, not just a substring - a mutated message that still
    # happens to contain "no RFC822 headers" as a substring (e.g. with
    # junk appended either side) would otherwise still pass.
    assert str(exc_info.value) == "not a recognizable email (no RFC822 headers found)"


def test_extract_envelope_finds_a_header_before_the_first_blank_line_even_with_junk_ahead() -> None:
    # A real header line earlier than the split point still counts, even
    # with an unrecognized header (Return-Path, here) ahead of it in the
    # same header block - this only distinguishes from a bug that
    # truncates the header block at the first whitespace of any kind,
    # rather than the first blank *line*.
    raw = "Return-Path: <bounce@example.com>\nFrom: a@b.com\nSubject: hi\nDate: Mon, 1 Jan 2026 12:00:00 +0000\n\nbody\n"

    extract_envelope(raw)  # does not raise


def test_extract_envelope_does_not_treat_body_text_as_a_header() -> None:
    # A forwarded message's own quoted "From:"/"Subject:" lines living in
    # the *body* must never count as this email's own headers - only
    # text before the first blank line does.
    raw = "Weird-Header: x\n\nForwarded message:\nFrom: someone@example.com\nSubject: fwd\n"

    with pytest.raises(MailFetchError, match="no RFC822 headers"):
        extract_envelope(raw)


def test_extract_envelope_rejects_a_missing_date_header() -> None:
    raw = "From: a@example.com\nSubject: hi\n\nbody\n"

    with pytest.raises(MailFetchError) as exc_info:
        extract_envelope(raw)

    assert str(exc_info.value) == "email has no Date header"


def test_extract_envelope_rejects_an_unparseable_date_header() -> None:
    raw = "From: a@example.com\nSubject: hi\nDate: not a real date\n\nbody\n"

    with pytest.raises(MailFetchError, match="unparseable Date header"):
        extract_envelope(raw)


def test_extract_envelope_with_no_from_header_is_an_empty_string() -> None:
    raw = "Subject: hi\nDate: Mon, 1 Jan 2026 12:00:00 +0000\n\nbody\n"

    envelope = extract_envelope(raw)

    assert envelope.from_address == ""


def test_extract_envelope_with_no_subject_header_is_an_empty_string() -> None:
    raw = "From: a@example.com\nDate: Mon, 1 Jan 2026 12:00:00 +0000\n\nbody\n"

    envelope = extract_envelope(raw)

    assert envelope.subject == ""


def test_sender_domain_extracts_and_lowercases_the_domain() -> None:
    assert sender_domain("Pathé Nederland <noreply@Pathe.NL>") == "pathe.nl"


def test_sender_domain_with_no_address_is_none() -> None:
    assert sender_domain("not an email address") is None


def test_sender_domain_with_an_extra_at_sign_takes_the_last_split() -> None:
    # A quoted local-part can itself legally contain "@" (RFC 5322), so
    # the parsed address can have more than one - rsplit(..., 1) takes
    # everything after the *last* one, not split() (which would take
    # the first) and not a wider maxsplit (which would take a middle
    # segment instead of the real domain).
    assert sender_domain('"a@b"@example.com') == "example.com"


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


def test_extract_envelope_ignores_an_html_attachment_with_no_real_html_body() -> None:
    # get_body() correctly refuses to treat an attachment as the html
    # body, leaving _extract_body's own walk() fallback to run - which
    # has to make the same "not an attachment" check itself, not just
    # match on content type (issue tracked under the mutation-testing
    # coverage gaps milestone: a flipped/weakened disposition check
    # here would silently start treating the attachment as real body
    # content).
    msg = EmailMessage()
    msg["From"] = "Cinema Chain <noreply@example-chain.com>"
    msg["Subject"] = "Your booking confirmation"
    msg["Date"] = "Sat, 04 Jul 2026 19:00:00 +0200"
    msg.set_content("Good Boy plain body, no digits here")
    msg.add_attachment(
        b"<p>this is an attachment, not the real body</p>",
        maintype="text",
        subtype="html",
        filename="e-ticket.html",
    )

    envelope = extract_envelope(msg.as_string())

    assert "Good Boy plain body" in envelope.body
    assert "this is an attachment" not in envelope.body


def test_extract_envelope_prefers_plain_with_a_digit_even_when_html_exists() -> None:
    # Both a real plain and a real html alternative exist, with
    # deliberately *different* text, and the plain one has a digit -
    # that's the "keep the plain part" branch of an OR, not an AND:
    # this only distinguishes the two once the alternatives' content
    # actually differs (matching text either way would pass regardless
    # of which branch is taken).
    msg = EmailMessage()
    msg["From"] = "Cinema Chain <noreply@example-chain.com>"
    msg["Subject"] = "Your booking confirmation"
    msg["Date"] = "Sat, 04 Jul 2026 19:00:00 +0200"
    msg.set_content("Good Boy, booking AB1CD23")
    msg.add_alternative("<p>Please view this email in an HTML-capable client</p>", subtype="html")

    envelope = extract_envelope(msg.as_string())

    assert "Good Boy, booking AB1CD23" in envelope.body
    assert "HTML-capable client" not in envelope.body
