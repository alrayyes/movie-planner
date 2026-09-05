"""Parses a Pathé booking confirmation email - piped raw `.eml` (MIME) or
already-extracted plain text - into the fields a movie-log entry needs.
See design.md's "Email parsing" decision.
"""

import email
import email.policy
import re
from dataclasses import dataclass
from datetime import date, datetime, time

# A raw piped `.eml` has real RFC 822 headers before the first blank line;
# already-extracted plain text doesn't. This is how the two are told apart.
_HEADER_RE = re.compile(
    r"^(From|To|Subject|Date|MIME-Version|Content-Type|Message-ID):", re.MULTILINE
)
_TITLE_RE = re.compile(r"\n([^\n]+)\n=+\n")
_DATETIME_RE = re.compile(
    r"\b\w+day (\d{2}/\d{2}/\d{2}), (\d{2}:\d{2}) Expected to end at (\d{2}:\d{2})"
)
_CINEMA_RE = re.compile(r"^(Pathé [^\n]+)$", re.MULTILINE)
_AUDITORIUM_RE = re.compile(r"^(Auditorium[^\n]*)$", re.MULTILINE)
_BOOKING_REF_RE = re.compile(r"Booking number\s*\n+\s*(N°\S+)")

# The shape movie_planner.mail_import.envelope's own HTML-to-text
# fallback produces for a real, HTML-only Pathé confirmation
# (movie-planner#158) - a completely different template from the
# plain-text one above, tried only when that one doesn't match.
_HTML_BOOKING_RE = re.compile(
    r"\w+day\s+(?P<date>\d{1,2}\s+\w+\s+\d{4})\s+at\s+(?P<start>\d{2}:\d{2})\s+"
    r"Expected end time:\s*(?P<end>\d{2}:\d{2})\n"
    r"(?P<title>[^\n]+)\n"
    r"(?P<cinema>[^\n]+)"
)
_HTML_BOOKING_REF_RE = re.compile(r"reservation no\.([^\s.]+)\.")
_HTML_LANGUAGE_AUDITORIUM_RE = re.compile(r"([^\n]*)\n[–-]\s*(Auditorium[^\n]+)")


class PatheEmailParseError(Exception):
    """Raised when the given content doesn't match the expected Pathé
    booking confirmation format. The message is shown to the user as-is.
    """


@dataclass(frozen=True)
class PatheBooking:
    title: str
    date: date
    start_time: time
    end_time: time
    cinema: str
    booking_ref: str
    # Auditorium/format/seat text - description-only, never persisted as
    # its own column. See design.md's "Description content" decision.
    screening_details: str | None


def _extract_body(raw: str) -> str:
    head = raw.split("\n\n", 1)[0]
    if not _HEADER_RE.search(head):
        return raw

    msg = email.message_from_string(raw, policy=email.policy.default)
    if not msg.is_multipart():
        return msg.get_content()  # type: ignore[no-any-return]

    part = msg.get_body(preferencelist=("plain",))
    if part is not None:
        return part.get_content()  # type: ignore[no-any-return]
    for sub in msg.walk():
        if sub.get_content_type() == "text/plain":
            return sub.get_content()  # type: ignore[no-any-return]
    raise PatheEmailParseError("could not find a text/plain part in the email")


def _screening_details(body: str, *, after: int, before: int) -> str | None:
    language_block = body[after:before].strip()
    language = next((line.strip() for line in language_block.splitlines() if line.strip()), None)
    auditorium_match = _AUDITORIUM_RE.search(body)
    auditorium = auditorium_match.group(1).strip() if auditorium_match else None
    parts = [p for p in (language, auditorium) if p]
    return ", ".join(parts) if parts else None


def _html_screening_details(body: str) -> str | None:
    match = _HTML_LANGUAGE_AUDITORIUM_RE.search(body)
    if not match:
        return None
    parts = [p.strip() for p in match.groups() if p.strip()]
    return ", ".join(parts) if parts else None


def _parse_plain_text_shape(body: str) -> PatheBooking | None:
    booking_match = _BOOKING_REF_RE.search(body)
    title_match = _TITLE_RE.search(body)
    datetime_match = _DATETIME_RE.search(body)
    cinema_match = _CINEMA_RE.search(body)
    if not (booking_match and title_match and datetime_match and cinema_match):
        return None

    return PatheBooking(
        title=title_match.group(1).strip(),
        date=datetime.strptime(datetime_match.group(1), "%d/%m/%y").date(),
        start_time=time.fromisoformat(datetime_match.group(2)),
        end_time=time.fromisoformat(datetime_match.group(3)),
        cinema=cinema_match.group(1).strip(),
        booking_ref=booking_match.group(1).strip(),
        screening_details=_screening_details(
            body, after=title_match.end(), before=datetime_match.start()
        ),
    )


def _parse_html_derived_shape(body: str) -> PatheBooking | None:
    booking_match = _HTML_BOOKING_RE.search(body)
    ref_match = _HTML_BOOKING_REF_RE.search(body)
    if not (booking_match and ref_match):
        return None

    return PatheBooking(
        title=booking_match["title"].strip(),
        date=datetime.strptime(booking_match["date"], "%d %B %Y").date(),
        start_time=time.fromisoformat(booking_match["start"]),
        end_time=time.fromisoformat(booking_match["end"]),
        cinema=booking_match["cinema"].strip(),
        booking_ref=ref_match.group(1).strip(),
        screening_details=_html_screening_details(body),
    )


def parse_pathe_email(raw: str) -> PatheBooking:
    body = _extract_body(raw)

    booking = _parse_plain_text_shape(body) or _parse_html_derived_shape(body)
    if booking is None:
        raise PatheEmailParseError("could not parse this as a Pathé booking confirmation email")
    return booking
