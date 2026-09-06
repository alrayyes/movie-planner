"""Parses a Pathé booking confirmation email - piped raw `.eml` (MIME) or
already-extracted plain text - into the fields a movie-log entry needs.
See design.md's "Email parsing" decision.
"""

import email
import email.policy
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time

from movie_planner.mail_import.envelope import html_to_text

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

# A third real Pathé template (movie-planner#171) - structurally like
# the old plain-text template above (title before the date/time,
# "Booking number"/"N°...") but with no "====" title underline, and the
# HTML source's own line-wrapping lands a newline inside the date/time
# text where the old template had a single space. Anchored on the
# "Scan the QR code..." disclaimer sentence both templates share, since
# there's no underline to find the title with here.
_HTML_LEGACY_TITLE_RE = re.compile(r"Scan the QR code at the cinema\.[^\n]*\n+([^\n]+)")
_HTML_LEGACY_DATETIME_RE = re.compile(
    r"\b\w+day (\d{2}/\d{2}/\d{2}),\s*(\d{2}:\d{2}) Expected to end at (\d{2}:\d{2})"
)
_HTML_LEGACY_AUDITORIUM_RE = re.compile(
    r"^(Auditorium[^\n]*?)\s*[-–]\s*\n+\s*(Row[^\n]*)$", re.MULTILINE
)


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

    # A part with Content-Disposition: attachment is never the message
    # body, even one mislabeled as text/plain by the sender's own
    # template (movie-planner#193 - the same bug #191 fixed in
    # mail_import.envelope's own, independent extraction). get_body()
    # already respects this; the walk() fallback has to check it too.
    part = msg.get_body(preferencelist=("plain",))
    if part is not None:
        return part.get_content()  # type: ignore[no-any-return]
    for sub in msg.walk():
        if sub.get_content_type() == "text/plain" and sub.get_content_disposition() != "attachment":
            return sub.get_content()  # type: ignore[no-any-return]

    # A real Pathé confirmation is HTML-only, no text/plain part at all
    # (movie-planner#158) - the same fallback mail_import.envelope's
    # own extraction already uses for `pathe-mail-import fetch`,
    # reused here rather than a second, divergent implementation
    # (movie-planner#162).
    html_part = msg.get_body(preferencelist=("html",))
    if html_part is None:
        for sub in msg.walk():
            if (
                sub.get_content_type() == "text/html"
                and sub.get_content_disposition() != "attachment"
            ):
                html_part = sub
                break
    if html_part is not None:
        return html_to_text(html_part.get_content())

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


def _html_legacy_screening_details(body: str, *, after: int, before: int) -> str | None:
    language_block = body[after:before].strip()
    language = next((line.strip() for line in language_block.splitlines() if line.strip()), None)
    auditorium_match = _HTML_LEGACY_AUDITORIUM_RE.search(body)
    auditorium = (
        f"{auditorium_match.group(1).strip()} - {auditorium_match.group(2).strip()}"
        if auditorium_match
        else None
    )
    parts = [p for p in (language, auditorium) if p]
    return ", ".join(parts) if parts else None


def _parse_html_legacy_wording_shape(body: str) -> PatheBooking | None:
    booking_match = _BOOKING_REF_RE.search(body)
    title_match = _HTML_LEGACY_TITLE_RE.search(body)
    datetime_match = _HTML_LEGACY_DATETIME_RE.search(body)
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
        screening_details=_html_legacy_screening_details(
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


@dataclass(frozen=True)
class _Template:
    """One named, dated Pathé confirmation template - self-documenting
    (`name`/`era` say which real emails this is for) and independently
    testable, rather than an ever-growing `or`-chain where nothing
    records which era a given regex is even for (movie-planner#200).
    Tried in the order listed below; the first match wins.
    """

    name: str
    era: str
    parse: Callable[[str], PatheBooking | None]


_TEMPLATES: tuple[_Template, ...] = (
    _Template("plain-text", "original template", _parse_plain_text_shape),
    _Template("html-derived", "2026, HTML-only (#158)", _parse_html_derived_shape),
    _Template(
        "html-legacy-wording", "2026, third template (#171)", _parse_html_legacy_wording_shape
    ),
)


def parse_pathe_email(raw: str) -> PatheBooking:
    body = _extract_body(raw)

    for template in _TEMPLATES:
        booking = template.parse(body)
        if booking is not None:
            return booking
    raise PatheEmailParseError("could not parse this as a Pathé booking confirmation email")
