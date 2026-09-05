"""Dispatches each fetched envelope to whichever chain's external
translation script owns its sender domain. No chain-specific parsing
logic lives here or anywhere else in this tool - see design.md's
"Chain-specific parsing lives entirely outside the tool" decision.
"""

import json
import shlex
import subprocess  # nosec B404 - translate command is user-configured, not untrusted input
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from movie_planner.mail_import.config import ChainConfig
from movie_planner.mail_import.envelope import MailEnvelope, envelope_to_json, sender_domain


@dataclass(frozen=True)
class DispatchResult:
    """Either `row` is populated and `envelope` is the one it came from,
    for a recognized email, or `row` is None, for one no configured
    chain's script recognized (including no chain configured for its
    sender domain at all).
    """

    envelope: MailEnvelope
    row: dict[str, Any] | None


def dispatch(envelope: MailEnvelope, chains: tuple[ChainConfig, ...]) -> DispatchResult:
    domain = sender_domain(envelope.from_address)
    chain = next((c for c in chains if c.sender_domain.lower() == domain), None)
    if chain is None:
        return DispatchResult(envelope=envelope, row=None)

    try:
        result = subprocess.run(  # nosec B603
            shlex.split(chain.translate),
            input=json.dumps(envelope_to_json(envelope)),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return DispatchResult(envelope=envelope, row=None)

    if result.returncode != 0 or not result.stdout.strip():
        return DispatchResult(envelope=envelope, row=None)

    try:
        row = json.loads(result.stdout)
    except json.JSONDecodeError:
        return DispatchResult(envelope=envelope, row=None)
    if not isinstance(row, dict):
        return DispatchResult(envelope=envelope, row=None)

    # The core tool stamps `source`, not the translation script - see
    # design.md's "The core tool stamps source" decision.
    row = {**row, "source": domain}
    return DispatchResult(envelope=envelope, row=row)


def dispatch_all(
    envelopes: Iterable[MailEnvelope], chains: tuple[ChainConfig, ...]
) -> tuple[list[dict[str, Any]], list[MailEnvelope]]:
    """Splits fetched envelopes into recognized rows and unrecognized
    envelopes (for the review table), preserving order within each.
    """
    rows: list[dict[str, Any]] = []
    unrecognized: list[MailEnvelope] = []
    for envelope in envelopes:
        result = dispatch(envelope, chains)
        if result.row is not None:
            rows.append(result.row)
        else:
            unrecognized.append(result.envelope)
    return rows, unrecognized
