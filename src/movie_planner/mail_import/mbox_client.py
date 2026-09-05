"""Reads a local mbox-format mailbox - mutt's own storage, or
Thunderbird's default local-folder format, which is also plain mbox
(see design.md's mbox-adapter decision; task 2.8 verifies that claim
against a real Thunderbird file). No network, no credentials.
"""

import mailbox
from collections.abc import Iterable, Sequence
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from movie_planner.mail_import.envelope import MailFetchError, sender_domain


class MboxMailClient:
    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(
        self,
        sender_domains: Sequence[str],
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Iterable[str]:
        if not self._path.is_file():
            raise MailFetchError(f"mbox file not found: {self._path}")

        wanted = {d.lower() for d in sender_domains}
        try:
            box = mailbox.mbox(str(self._path), create=False)
        except OSError as e:
            raise MailFetchError(f"could not read mbox file {self._path}: {e}") from e

        try:
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
        finally:
            box.close()
