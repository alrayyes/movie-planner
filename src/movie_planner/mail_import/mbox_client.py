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
    def __init__(self, path: Path, *, extra_paths: Sequence[Path] = ()) -> None:
        self._path = path
        self._extra_paths = tuple(extra_paths)

    def fetch(
        self,
        sender_domains: Sequence[str],
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Iterable[str]:
        wanted = {d.lower() for d in sender_domains}
        seen_message_ids: set[str] = set()
        for path in (self._path, *self._extra_paths):
            yield from self._fetch_one(
                path, wanted=wanted, since=since, until=until, seen_message_ids=seen_message_ids
            )

    def _fetch_one(
        self,
        path: Path,
        *,
        wanted: set[str],
        since: datetime | None,
        until: datetime | None,
        seen_message_ids: set[str],
    ) -> Iterable[str]:
        if not path.is_file():
            raise MailFetchError(f"mbox file not found: {path}")

        try:
            box = mailbox.mbox(str(path), create=False)
        except OSError as e:
            raise MailFetchError(f"could not read mbox file {path}: {e}") from e

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

                # Only a real, present Message-ID is a reliable enough
                # identity to de-duplicate on (issue #188, for a message
                # that ends up in more than one configured mbox file) -
                # a message with none is never skipped for "already seen".
                message_id = message.get("Message-ID")
                if message_id is not None:
                    if message_id in seen_message_ids:
                        continue
                    seen_message_ids.add(str(message_id))

                yield message.as_string()
        finally:
            box.close()
