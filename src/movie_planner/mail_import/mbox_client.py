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

        # `create` is provably a no-op here (issue #289) - `path.is_file()`
        # already guarantees the file exists by this point, and
        # mailbox.mbox's `create` only ever affects behavior when the
        # path is missing. Mutating it (False/True/None/omitted) can't
        # be observed.
        try:
            box = mailbox.mbox(str(path), create=False)
        except OSError as e:
            raise MailFetchError(f"could not read mbox file {path}: {e}") from e

        try:
            for message in box:
                # message is a mailbox.mboxMessage, an email.message.Message
                # subclass - `.get(name)` is case-insensitive (RFC 2822
                # header names are), so mutating "From"/"Date"/"Message-ID"'s
                # case below is equivalent, not a gap (same reasoning as
                # envelope.py's own header lookups). The "" default on
                # `.get("From", "")` is similarly equivalent to any other
                # default without an "@" in it (including the case-mutated
                # "None"/omitted defaults) - sender_domain() only cares
                # whether "@" is present, so a missing From header always
                # resolves to no domain regardless of which no-"@" default
                # is used.
                domain = sender_domain(str(message.get("From", "")))
                if domain not in wanted:
                    continue

                date_header = message.get("Date")
                if date_header is None:
                    continue
                try:
                    message_date = parsedate_to_datetime(str(date_header))
                # TypeError is unreachable here (issue #289): `str(...)`
                # above guarantees a str argument, and email.utils.
                # parsedate_to_datetime only ever raises ValueError for a
                # str it can't parse - verified against this module's own
                # implementation, not assumed. Kept defensively regardless
                # (a stdlib behavior change is a much smaller risk than a
                # loop-ending `break` slipping in unnoticed), but no test
                # can ever exercise this branch's own continue-vs-break
                # choice.
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
