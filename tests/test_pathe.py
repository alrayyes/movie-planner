from datetime import date, time
from email.message import EmailMessage

import pytest
from fixtures import (
    PATHE_BOOKING_REF,
    PATHE_EMAIL_HTML_ONLY,
    PATHE_EMAIL_MIME,
    PATHE_EMAIL_PLAIN,
    PATHE_HTML_BOOKING_REF,
)

from movie_planner.mail_import.envelope import extract_envelope
from movie_planner.pathe import PatheEmailParseError, parse_pathe_email

# --- parse_pathe_email: tasks 4.1, 4.2 ---


def test_parses_plain_text_body() -> None:
    booking = parse_pathe_email(PATHE_EMAIL_PLAIN)

    assert booking.title == "The Dog Stars"
    assert booking.date == date(2026, 8, 29)
    assert booking.start_time == time(12, 40)
    assert booking.end_time == time(14, 58)
    assert booking.cinema == "Pathé De Munt"
    assert booking.booking_ref == PATHE_BOOKING_REF


def test_parses_raw_mime_message_extracting_text_plain_part() -> None:
    booking = parse_pathe_email(PATHE_EMAIL_MIME)

    assert booking.title == "The Dog Stars"
    assert booking.booking_ref == PATHE_BOOKING_REF


def test_screening_details_includes_language_and_seat() -> None:
    booking = parse_pathe_email(PATHE_EMAIL_PLAIN)

    assert booking.screening_details == "Original Version, Auditorium 1 DOLBY - Row 5 Seat 17"


def test_screening_details_with_no_language_line_still_finds_the_seat() -> None:
    # Not every booking type carries an "Original Version"/dubbing line -
    # the language block between the title and the date/time can be empty.
    without_language = PATHE_EMAIL_PLAIN.replace("Original Version\n\n", "")

    booking = parse_pathe_email(without_language)

    assert booking.screening_details == "Auditorium 1 DOLBY - Row 5 Seat 17"


def test_header_detection_only_looks_at_the_first_paragraph() -> None:
    # A plain-text body with no real headers can still coincidentally
    # contain a line like "Subject: ..." further down (e.g. in a
    # disclaimer). Only the text up to the first blank line decides
    # whether this looks like raw MIME - not the whole body.
    with_a_decoy_line = PATHE_EMAIL_PLAIN.replace(
        "This cinema is pin only.", "This cinema is pin only.\nSubject: not a real header"
    )

    booking = parse_pathe_email(with_a_decoy_line)

    assert booking.title == "The Dog Stars"
    assert booking.booking_ref == PATHE_BOOKING_REF


def test_parses_raw_mime_single_part_message() -> None:
    msg = EmailMessage()
    msg["From"] = "Pathé Nederland <noreply@pathe.nl>"
    msg["To"] = "john@example.com"
    msg["Subject"] = "Your ticket(s) for The Dog Stars"
    msg.set_content(PATHE_EMAIL_PLAIN)

    booking = parse_pathe_email(msg.as_string())

    assert booking.title == "The Dog Stars"
    assert booking.booking_ref == PATHE_BOOKING_REF


# --- parse failure: task 4.3 ---


def test_unrecognized_content_raises_a_clear_error() -> None:
    with pytest.raises(PatheEmailParseError, match="could not parse this as a Pathé"):
        parse_pathe_email("this is not a Pathé booking confirmation at all")


def test_missing_booking_number_raises() -> None:
    without_booking_ref = PATHE_EMAIL_PLAIN.replace(f"{PATHE_BOOKING_REF}\n\n", "")

    with pytest.raises(PatheEmailParseError):
        parse_pathe_email(without_booking_ref)


def test_mime_message_with_no_text_plain_part_raises() -> None:
    msg = EmailMessage()
    msg["From"] = "Pathé Nederland <noreply@pathe.nl>"
    msg["To"] = "john@example.com"
    msg["Subject"] = "Your ticket(s) for The Dog Stars"
    msg.set_content("<html><body>primary</body></html>", subtype="html")
    msg.add_alternative("<html><body>secondary</body></html>", subtype="html")
    assert msg.is_multipart()

    with pytest.raises(PatheEmailParseError, match="text/plain"):
        parse_pathe_email(msg.as_string())


# --- HTML-derived text shape: movie-planner#158 ---
#
# pathe.py's own MIME extraction (_extract_body, above) is untouched -
# a raw HTML-only .eml piped straight into `from-pathe-email` still
# raises the same as before. This is the shape parse_pathe_email
# actually receives from mail_import: envelope.py's own HTML fallback
# already converted the email to plain text by the time it gets here.


def test_parses_the_html_derived_plain_text_shape() -> None:
    stripped_body = extract_envelope(PATHE_EMAIL_HTML_ONLY).body

    booking = parse_pathe_email(stripped_body)

    assert booking.title == "Spider-Man: Brand New Day"
    assert booking.date == date(2026, 8, 9)
    assert booking.start_time == time(13, 45)
    assert booking.end_time == time(16, 30)
    assert booking.cinema == "Pathé De Munt"
    assert booking.booking_ref == PATHE_HTML_BOOKING_REF
    assert booking.screening_details == "Original Version, Auditorium 1 dolby"


def test_html_derived_shape_still_raises_when_reservation_number_is_missing() -> None:
    stripped_body = extract_envelope(PATHE_EMAIL_HTML_ONLY).body
    without_ref = stripped_body.replace(f"reservation no.{PATHE_HTML_BOOKING_REF}.", "")

    with pytest.raises(PatheEmailParseError):
        parse_pathe_email(without_ref)
