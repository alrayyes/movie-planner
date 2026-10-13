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

        # The try/except OSError here, and create= within it, are both
        # provably unreachable/equivalent (issue #289) - verified against
        # mailbox.Maildir's and its Mailbox base's actual __init__ source:
        # neither does any filesystem I/O beyond the `os.path.exists`
        # check `create` only affects, and self._path.is_dir() above
        # already guarantees that check passes. mailbox.Maildir's real
        # I/O (and any OSError it could raise) only happens lazily, on
        # the `for message in box` iteration below - by which point this
        # except clause is no longer in scope.
        try:
            box = mailbox.Maildir(str(self._path), create=False)
        except OSError as e:
            raise MailFetchError(f"could not read Maildir directory {self._path}: {e}") from e

        for message in box:
            # message is a mailbox.MaildirMessage, an email.message.Message
            # subclass - `.get(name)` is case-insensitive (RFC 2822 header
            # names are), so mutating "From"/"Date"'s case below is
            # equivalent, not a gap (same reasoning as envelope.py's own
            # header lookups). The "" default on `.get("From", "")` is
            # similarly equivalent to any other default without an "@" in
            # it - sender_domain() only cares whether "@" is present.
            domain = sender_domain(str(message.get("From", "")))
            if domain not in wanted:
                continue

            date_header = message.get("Date")
            if date_header is None:
                continue
            try:
                message_date = parsedate_to_datetime(str(date_header))
            # TypeError is unreachable here (issue #289), same reasoning
            # as mbox_client.py's identical except clause: `str(...)`
            # above guarantees a str argument, and parsedate_to_datetime
            # only ever raises ValueError for a str it can't parse.
            except TypeError:
                continue
            except ValueError:
                continue
            if since is not None and message_date < since:
                continue
            if until is not None and message_date >= until:
                continue

            yield message.as_string()
