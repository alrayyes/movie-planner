"""Reads a local Maildir-format mailbox - one file per message under
`cur`/`new` (and `tmp`, never a delivered message), mutt's own default
local sync format. No network, no credentials. See movie-planner#208 -
`MboxMailClient` only ever reads mbox, and a mutt-synced account with
no separate mbox copy needs this instead.
"""

import mailbox
from collections.abc import Iterable, Sequence
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from movie_planner.mail_import.envelope import MailFetchError, sender_domain


class MaildirMailClient:
    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(
        self,
        sender_domains: Sequence[str],
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Iterable[str]:
        wanted = {d.lower() for d in sender_domains}

        if not self._path.is_dir():
            raise MailFetchError(f"Maildir directory not found: {self._path}")

        try:
            box = mailbox.Maildir(str(self._path), create=False)
        except OSError as e:
            raise MailFetchError(f"could not read Maildir directory {self._path}: {e}") from e

        for message in box:
            domain = sender_domain(str(message.get("From", "")))
            if domain not in wanted:
                continue

            date_header = message.get("Date")
            if date_header is None:
                continue
            try:
                message_date = parsedate_to_datetime(str(date_header))
            except TypeError:
                continue
            except ValueError:
                continue
            if since is not None and message_date < since:
                continue
            if until is not None and message_date >= until:
                continue

            yield message.as_string()
