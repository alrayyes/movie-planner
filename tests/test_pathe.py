from datetime import date, time
from email.message import EmailMessage

import pytest
from fixtures import (
    PATHE_BOOKING_REF,
    PATHE_EMAIL_HTML_ONLY,
    PATHE_EMAIL_LEGACY_HTML,
    PATHE_EMAIL_MIME,
    PATHE_EMAIL_MISLABELED_ATTACHMENT,
    PATHE_EMAIL_MOBIEL,
    PATHE_EMAIL_PLAIN,
    PATHE_EMAIL_RESERVERING,
    PATHE_EMAIL_TICKETBEVESTIGING,
    PATHE_HTML_BOOKING_REF,
    PATHE_LEGACY_HTML_BOOKING_REF,
    PATHE_MISLABELED_ATTACHMENT_BOOKING_REF,
    PATHE_MOBIEL_BOOKING_REF,
    PATHE_RESERVERING_BOOKING_REF,
    PATHE_TICKETBEVESTIGING_BOOKING_REF,
)

from movie_planner.mail_import.envelope import extract_envelope
from movie_planner.pathe import PatheBooking, PatheEmailParseError, parse_pathe_email

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
    with pytest.raises(PatheEmailParseError) as exc_info:
        parse_pathe_email("this is not a Pathé booking confirmation at all")

    # The full message, not just a substring - a substring check would still
    # match even if the text were wrapped in extra characters (mutmut's own
    # "XX...XX" mutation technique), since the original text stays a
    # substring of the wrapped version.
    assert str(exc_info.value) == "could not parse this as a Pathé booking confirmation email"


def test_missing_booking_number_raises() -> None:
    without_booking_ref = PATHE_EMAIL_PLAIN.replace(f"{PATHE_BOOKING_REF}\n\n", "")

    with pytest.raises(PatheEmailParseError):
        parse_pathe_email(without_booking_ref)


def test_mime_message_with_neither_plain_nor_recognizable_html_raises() -> None:
    # No text/plain part, and the html part isn't a Pathé booking shape
    # either (movie-planner#162 added the html fallback below) - still
    # raises, just for the actual reason now.
    msg = EmailMessage()
    msg["From"] = "Pathé Nederland <noreply@pathe.nl>"
    msg["To"] = "john@example.com"
    msg["Subject"] = "Your ticket(s) for The Dog Stars"
    msg.set_content("<html><body>primary</body></html>", subtype="html")
    msg.add_alternative("<html><body>secondary</body></html>", subtype="html")
    assert msg.is_multipart()

    with pytest.raises(PatheEmailParseError, match="could not parse this as a Pathé"):
        parse_pathe_email(msg.as_string())


def test_mime_message_with_no_plain_or_html_part_raises_the_original_message() -> None:
    msg = EmailMessage()
    msg["From"] = "Pathé Nederland <noreply@pathe.nl>"
    msg["To"] = "john@example.com"
    msg["Subject"] = "Your ticket(s) for The Dog Stars"
    msg.add_attachment(b"not text", maintype="application", subtype="octet-stream")
    assert msg.is_multipart()

    with pytest.raises(PatheEmailParseError) as exc_info:
        parse_pathe_email(msg.as_string())

    # Exact text, same reasoning as test_unrecognized_content_raises_a_clear_error
    # above - "text/plain" alone stays a substring of a mutated, wrapped message.
    assert str(exc_info.value) == "could not find a text/plain part in the email"


# --- HTML-derived text shape: movie-planner#158 ---
#
# This is the shape parse_pathe_email actually receives from
# mail_import: envelope.py's own HTML fallback already converted the
# email to plain text by the time it gets here. pathe.py's own MIME
# extraction (_extract_body, above) gained the same HTML fallback
# later, for `from-pathe-email` itself - see movie-planner#162, below.


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


# --- HTML-derived, old-style-worded shape: movie-planner#171 ---
#
# A third real Pathé template - structurally like the old plain-text
# template (title before date/time, "Booking number"/"N°...") but with
# no "====" title underline and a source line-wrap landing inside the
# date/time text.


def test_parses_the_legacy_html_derived_shape() -> None:
    stripped_body = extract_envelope(PATHE_EMAIL_LEGACY_HTML).body

    booking = parse_pathe_email(stripped_body)

    assert booking.title == "Insidious: Out of the Further"
    assert booking.date == date(2026, 8, 27)
    assert booking.start_time == time(13, 40)
    assert booking.end_time == time(15, 46)
    assert booking.cinema == "Pathé City"
    assert booking.booking_ref == PATHE_LEGACY_HTML_BOOKING_REF
    assert booking.screening_details == "Original Version, Auditorium 4 - Row 2 Seat 4"


def test_legacy_html_derived_shape_with_no_language_line_still_finds_the_auditorium() -> None:
    # Same edge case as test_screening_details_with_no_language_line_still_finds_the_seat
    # above, for the html-legacy-wording shape's own screening-details helper -
    # the language block between the title and the date/time can be empty.
    stripped_body = extract_envelope(PATHE_EMAIL_LEGACY_HTML).body
    without_language = stripped_body.replace("Original Version\n", "")

    booking = parse_pathe_email(without_language)

    assert booking.screening_details == "Auditorium 4 - Row 2 Seat 4"


# --- three more real historical templates: movie-planner#200 ---
#
# All three are Dutch and print no year in their own date text - unlike
# every template above, they need the email's own Date header
# (received_date) to know which year the booking was for.


def test_parses_the_mobiel_shape() -> None:
    envelope = extract_envelope(PATHE_EMAIL_MOBIEL)

    booking = parse_pathe_email(envelope.body, received_date=envelope.date.date())

    assert booking.title == "World War Z 3D O3D"
    assert booking.date == date(2013, 6, 28)
    assert booking.start_time == time(20, 30)
    assert booking.end_time is None
    assert booking.cinema == "Pathe Arena"
    assert booking.booking_ref == PATHE_MOBIEL_BOOKING_REF
    assert booking.screening_details == "Zaal 4, Row 1 Seat 1"


def test_mobiel_shape_without_received_date_raises() -> None:
    # No year in the date text and nothing to infer one from - a clear
    # error, not a wrong guess.
    envelope = extract_envelope(PATHE_EMAIL_MOBIEL)

    with pytest.raises(PatheEmailParseError) as exc_info:
        parse_pathe_email(envelope.body)

    # Exact text, same reasoning as test_unrecognized_content_raises_a_clear_error
    # above - "received_date" alone stays a substring of a mutated message,
    # whichever half of the two concatenated string literals gets wrapped.
    assert str(exc_info.value) == (
        "this template's date has no year of its own - pass the email's "
        "own Date header as received_date to infer one"
    )


def test_parses_the_ticketbevestiging_shape() -> None:
    envelope = extract_envelope(PATHE_EMAIL_TICKETBEVESTIGING)

    booking = parse_pathe_email(envelope.body, received_date=envelope.date.date())

    assert booking.title == "The Imitation Game"
    assert booking.date == date(2014, 12, 26)
    assert booking.start_time == time(21, 5)
    assert booking.end_time is None
    # Not "Pathé Tuschinski, Amsterdam" - the trailing city is stripped
    # (movie-planner#227), same "cinema, never the city too" behaviour
    # every other template already has.
    assert booking.cinema == "Pathé Tuschinski"
    assert booking.booking_ref == PATHE_TICKETBEVESTIGING_BOOKING_REF
    assert booking.screening_details == "Zaal 1, Rij: 1 Stoel: 1"


def test_parses_the_reservering_shape() -> None:
    envelope = extract_envelope(PATHE_EMAIL_RESERVERING)

    booking = parse_pathe_email(envelope.body, received_date=envelope.date.date())

    assert booking.title == "Long Shot"
    assert booking.date == date(2019, 6, 13)
    assert booking.start_time == time(15, 20)
    assert booking.end_time == time(17, 39)
    # Not "Pathé De Munt, Amsterdam" - same city-stripping fix as
    # ticketbevestiging above (movie-planner#227).
    assert booking.cinema == "Pathé De Munt"
    assert booking.booking_ref == PATHE_RESERVERING_BOOKING_REF
    assert booking.screening_details == "Zaal 1, Rij: 1 stoel: 1"


# --- from-pathe-email's own MIME extraction falls back to HTML too: movie-planner#162 ---


def test_parses_a_real_html_only_email_piped_directly() -> None:
    # Unlike the tests above, this pipes the raw HTML-only .eml straight
    # into parse_pathe_email - no mail_import.envelope involved - the
    # shape `from-pathe-email` itself receives.
    booking = parse_pathe_email(PATHE_EMAIL_HTML_ONLY)

    assert isinstance(booking, PatheBooking)
    assert booking.title == "Spider-Man: Brand New Day"
    assert booking.booking_ref == PATHE_HTML_BOOKING_REF


# --- mislabeled text/plain attachment: movie-planner#193 ---


def test_parses_a_real_email_with_a_mislabeled_attachment_piped_directly() -> None:
    # Same bug mail_import.envelope had (movie-planner#191) in pathe.py's
    # own, independent MIME extraction: a PDF ticket mislabeled
    # Content-Type: text/plain by Pathé's own template shouldn't be
    # picked as the body just because Content-Disposition says
    # attachment.
    booking = parse_pathe_email(PATHE_EMAIL_MISLABELED_ATTACHMENT)

    assert isinstance(booking, PatheBooking)
    assert booking.title == "Spider-Man: Brand New Day"
    assert booking.booking_ref == PATHE_MISLABELED_ATTACHMENT_BOOKING_REF


# --- row/seat as structured fields: issue #218 ---


def test_plain_text_shape_extracts_row_and_seat() -> None:
    booking = parse_pathe_email(PATHE_EMAIL_PLAIN)

    assert booking.row == "5"
    assert booking.seat == "17"


def test_html_derived_shape_extracts_row_and_seat() -> None:
    booking = parse_pathe_email(PATHE_EMAIL_HTML_ONLY)

    assert booking.row == "4"
    assert booking.seat == "1"


def test_legacy_html_derived_shape_extracts_row_and_seat() -> None:
    stripped_body = extract_envelope(PATHE_EMAIL_LEGACY_HTML).body

    booking = parse_pathe_email(stripped_body)

    assert booking.row == "2"
    assert booking.seat == "4"


def test_mobiel_shape_extracts_row_and_seat() -> None:
    envelope = extract_envelope(PATHE_EMAIL_MOBIEL)

    booking = parse_pathe_email(envelope.body, received_date=envelope.date.date())

    assert booking.row == "1"
    assert booking.seat == "1"


def test_ticketbevestiging_shape_extracts_row_and_seat() -> None:
    envelope = extract_envelope(PATHE_EMAIL_TICKETBEVESTIGING)

    booking = parse_pathe_email(envelope.body, received_date=envelope.date.date())

    assert booking.row == "1"
    assert booking.seat == "1"


def test_reservering_shape_extracts_row_and_seat() -> None:
    envelope = extract_envelope(PATHE_EMAIL_RESERVERING)

    booking = parse_pathe_email(envelope.body, received_date=envelope.date.date())

    assert booking.row == "1"
    assert booking.seat == "1"


def test_row_and_seat_are_none_when_not_present() -> None:
    without_seat = PATHE_EMAIL_PLAIN.replace("Auditorium 1 DOLBY - Row 5 Seat 17", "")

    booking = parse_pathe_email(without_seat)

    assert booking.row is None
    assert booking.seat is None


# --- remaining mutmut gaps: movie-planner#298 ---
#
# _extract_body's own header-detection and MIME-fallback branches, below,
# aren't reachable through any of the real templates above the same way -
# every real fixture's plain or html part is a direct, top-level part
# get_body() finds on its own, so a test built only from real Pathé
# shapes can't tell the "found the right part" line apart from a mutant
# that skips it. These import _extract_body directly and build the
# specific MIME shapes needed to pin each branch, the same way
# movie-planner#323 tested mail_import.cli's own private helpers
# directly for the same reason.


def test_extract_body_header_detection_uses_the_blank_line_not_any_whitespace() -> None:
    # The header block is "text up to the first blank line" - split on
    # "\n\n", not split on the first run of whitespace (which would stop
    # at the first space or newline instead, cutting the header block off
    # after a single word).
    from movie_planner.pathe import _extract_body

    raw = "X-Test:garbage\nFrom: a@a.com\n\nBody text here."

    assert _extract_body(raw) == "Body text here."


def test_extract_body_header_detection_only_considers_the_first_paragraph() -> None:
    # Same "first paragraph only" rule as
    # test_header_detection_only_looks_at_the_first_paragraph above, but
    # with the decoy header in a *middle* paragraph rather than the last
    # one - splitting from the wrong end (the last blank line rather than
    # the first) would still exclude a decoy in the very last paragraph,
    # so that test alone can't tell "first" from "last" apart.
    from movie_planner.pathe import _extract_body

    raw = (
        "Booking number\n\nN°REF123\n\nHi John,\nSubject: decoy\n\n"
        "More paragraph\n\nFinal paragraph."
    )

    assert _extract_body(raw) == raw


def test_extract_body_plain_part_is_the_one_get_body_picks_not_the_first_walk_match() -> None:
    # get_body(preferencelist=("plain",)) is expected to skip a part
    # nested inside a container marked Content-Disposition: attachment,
    # even though that part's own disposition is inline - the
    # walk()-based fallback below it only checks each leaf's own
    # disposition, so it would wrongly pick the attachment-nested part if
    # it ran instead. Building a message where the real inline part isn't
    # the first thing walk() would see is what actually exercises the
    # get_body() call, rather than the fallback that follows it.
    from movie_planner.pathe import _extract_body

    outer = EmailMessage()
    outer["From"] = "a@a.com"
    outer["To"] = "b@b.com"
    outer["Subject"] = "test"
    outer.make_mixed()

    attachment_container = EmailMessage()
    attachment_container.make_mixed()
    attachment_container["Content-Disposition"] = "attachment"
    nested_plain = EmailMessage()
    nested_plain.set_content("nested plain part, wrongly inside an attachment container")
    attachment_container.attach(nested_plain)
    outer.attach(attachment_container)

    real_plain = EmailMessage()
    real_plain.set_content("the real, top-level inline plain part")
    outer.attach(real_plain)

    assert _extract_body(outer.as_string()) == "the real, top-level inline plain part\n"


def test_extract_body_walk_fallback_matches_text_plain_content_type_exactly() -> None:
    # Only reachable once get_body(plain) has already returned None (here,
    # because the sole plain part sits inside an attachment-marked
    # container) - pins the walk loop's own "text/plain" comparison,
    # which a typo'd or wrongly-cased constant would never match.
    from movie_planner.pathe import _extract_body

    outer = EmailMessage()
    outer["From"] = "a@a.com"
    outer["To"] = "b@b.com"
    outer["Subject"] = "test"
    outer.make_mixed()

    attachment_container = EmailMessage()
    attachment_container.make_mixed()
    attachment_container["Content-Disposition"] = "attachment"
    nested_plain = EmailMessage()
    nested_plain.set_content("only reachable via the walk() fallback")
    attachment_container.attach(nested_plain)
    outer.attach(attachment_container)

    assert _extract_body(outer.as_string()) == "only reachable via the walk() fallback\n"


def test_extract_body_html_fallback_prefers_get_body_over_the_first_walk_match() -> None:
    # Same "get_body(), not the first walk() match" case as
    # test_extract_body_plain_part_is_the_one_get_body_picks_not_the_first_walk_match
    # above, for the html fallback path.
    from movie_planner.pathe import _extract_body

    outer = EmailMessage()
    outer["From"] = "a@a.com"
    outer["To"] = "b@b.com"
    outer["Subject"] = "test"
    outer.make_mixed()

    attachment_container = EmailMessage()
    attachment_container.make_mixed()
    attachment_container["Content-Disposition"] = "attachment"
    decoy_html = EmailMessage()
    decoy_html.set_content("<p>decoy - inside an attachment container</p>", subtype="html")
    attachment_container.attach(decoy_html)
    outer.attach(attachment_container)

    real_html = EmailMessage()
    real_html.set_content("<p>Real one</p>", subtype="html")
    outer.attach(real_html)

    assert _extract_body(outer.as_string()) == "Real one"


def test_extract_body_html_walk_fallback_skips_actual_attachment_disposition_parts() -> None:
    # Only reachable once get_body(html) has already returned None (here,
    # because both html parts sit inside an attachment-marked container) -
    # pins the walk loop's own "text/html" content-type match and its
    # "not actually an attachment" disposition check, in the order a real
    # attachment (first) then a real inline part (second) would meet them.
    from movie_planner.pathe import _extract_body

    outer = EmailMessage()
    outer["From"] = "a@a.com"
    outer["To"] = "b@b.com"
    outer["Subject"] = "test"
    outer.make_mixed()

    attachment_container = EmailMessage()
    attachment_container.make_mixed()
    attachment_container["Content-Disposition"] = "attachment"

    attached_html = EmailMessage()
    attached_html.set_content("<p>attached - should be skipped</p>", subtype="html")
    attached_html["Content-Disposition"] = "attachment"
    attachment_container.attach(attached_html)

    real_html = EmailMessage()
    real_html.set_content("<p>Real inline html</p>", subtype="html")
    attachment_container.attach(real_html)

    outer.attach(attachment_container)

    assert _extract_body(outer.as_string()) == "Real inline html"


def test_cinema_without_city_strips_only_the_trailing_city_after_the_last_comma() -> None:
    # rpartition, not partition - a cinema string with more than one comma
    # (an address written out further than "<venue>, <city>") should still
    # only lose the last, city-shaped segment.
    from movie_planner.pathe import _cinema_without_city

    assert (
        _cinema_without_city("Pathé De Munt, Amsterdam, Netherlands") == "Pathé De Munt, Amsterdam"
    )


def test_parse_reservering_shape_returns_none_unless_both_header_and_reference_match() -> None:
    # "Referentie: ..." alone (no matching header line) shouldn't be
    # enough to proceed - it needs to return None so parse_pathe_email
    # can fall through to the next template, not crash trying to read
    # fields off a header_match that's actually None.
    from movie_planner.pathe import _parse_reservering_shape

    assert _parse_reservering_shape("Referentie: ABC123", None) is None
