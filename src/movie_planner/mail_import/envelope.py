"""Turns a raw RFC822 email into a plain, chain-agnostic envelope - the
shape every translation script receives. This generalizes the same
MIME-vs-plain-text handling pathe.py's own _extract_body uses, kept as
an independent implementation here so pathe.py stays untouched (see
design.md's "Same repo, new module" decision).
"""

import email
import email.policy
import email.utils
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Protocol


class MailFetchError(Exception):
    """Raised when connecting to or reading a configured mail source
    fails, or a fetched message can't be turned into an envelope. The
    message is shown to the user as-is.
    """


@dataclass(frozen=True)
class MailEnvelope:
    from_address: str
    subject: str
    date: datetime
    body: str


def envelope_to_json(envelope: MailEnvelope) -> dict[str, str]:
    """The wire shape every translation script receives on stdin, and
    what --envelopes-only prints one of per line - the one envelope
    representation used everywhere this tool serializes one.
    """
    return {
        "from": envelope.from_address,
        "subject": envelope.subject,
        "date": envelope.date.isoformat(),
        "body": envelope.body,
    }


class MailClient(Protocol):
    def fetch(
        self,
        sender_domains: Sequence[str],
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Iterable[str]:
        """Yields raw RFC822 message text for each message from one of
        the given sender domains, optionally scoped to a date range.
        """
        ...


_HEADER_RE = re.compile(
    r"^(From|To|Subject|Date|MIME-Version|Content-Type|Message-ID):", re.MULTILINE
)


def sender_domain(from_address: str) -> str | None:
    """The lowercased domain of an RFC822 From header's address, or
    None when it doesn't look like one - e.g. "Pathé Nederland
    <noreply@pathe.nl>" -> "pathe.nl".
    """
    _, addr = email.utils.parseaddr(from_address)
    if "@" not in addr:
        return None
    return addr.rsplit("@", 1)[1].lower()


def extract_envelope(raw: str) -> MailEnvelope:
    head = raw.split("\n\n", 1)[0]
    if not _HEADER_RE.search(head):
        raise MailFetchError("not a recognizable email (no RFC822 headers found)")

    msg = email.message_from_string(raw, policy=email.policy.default)
    date_header = msg.get("Date")
    if date_header is None:
        raise MailFetchError("email has no Date header")
    try:
        parsed_date = email.utils.parsedate_to_datetime(str(date_header))
    except (TypeError, ValueError) as e:
        raise MailFetchError(f"email has an unparseable Date header: {e}") from e

    body = _extract_body(msg)
    return MailEnvelope(
        from_address=str(msg.get("From", "")),
        subject=str(msg.get("Subject", "")),
        date=parsed_date,
        body=body,
    )


_BLOCK_BREAK_RE = re.compile(r"(?i)<(?:br|/p|/h[1-6]|/tr|/li|/div)\s*/?>")
_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_text(html: str) -> str:
    """A deliberately simple HTML-to-plain-text conversion - enough for
    a chain's own regex-based translation script to work against, not a
    faithful rendering. Real Pathé confirmations are HTML-only (movie-
    planner#158), and this is chain-agnostic so any future chain's own
    translation script benefits the same way, not just Pathé's.
    """
    text = _BLOCK_BREAK_RE.sub("\n", html)
    text = _TAG_RE.sub("", text)
    text = unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _extract_body(msg: email.message.EmailMessage) -> str:
    if not msg.is_multipart():
        return msg.get_content()  # type: ignore[no-any-return]
    part = msg.get_body(preferencelist=("plain",))
    if part is not None:
        return part.get_content()  # type: ignore[no-any-return]
    for sub in msg.walk():
        if sub.get_content_type() == "text/plain":
            return sub.get_content()  # type: ignore[no-any-return]

    html_part = msg.get_body(preferencelist=("html",))
    if html_part is None:
        for sub in msg.walk():
            if sub.get_content_type() == "text/html":
                html_part = sub
                break
    if html_part is not None:
        return _html_to_text(html_part.get_content())

    # Genuinely no readable text anywhere (e.g. an attachment-only
    # message) - an empty body simply won't match any chain's
    # translation script, so it surfaces in the "not recognized"
    # review table like any other unrecognized email, rather than
    # vanishing via a caught-and-dropped MailFetchError.
    return ""
