"""Spins up a real IMAP server (GreenMail) in a Docker container for the
mail-fetch tool's e2e test - a genuine IMAP4 conversation over the wire,
not the fake connection `test_mail_import_imap_client.py`'s unit tests
use. Same "container over mock at the integration layer" preference
`baikal_container.py` already follows for CalDAV.
"""

import email.utils
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage

import httpx
from testcontainers.core.container import DockerContainer

_IMAGE = "greenmail/standalone:2.1.7"
# Auth disabled: any username/password is accepted on IMAP, and SMTP
# needs none either - the point here is a real IMAP wire conversation,
# not exercising GreenMail's own user-provisioning API.
_GREENMAIL_OPTS = (
    "-Dgreenmail.setup.test.all -Dgreenmail.hostname=0.0.0.0 -Dgreenmail.auth.disabled"
)


@dataclass(frozen=True)
class GreenmailTestServer:
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int


def _wait_until_ready(api_host: str, api_port: int) -> None:
    with httpx.Client() as client:
        for _ in range(60):
            try:
                # Any response at all means the JVM/HTTP listener is up;
                # GreenMail's other ports come up in the same startup pass.
                client.get(f"http://{api_host}:{api_port}/", timeout=1)
                return
            except httpx.TransportError:
                time.sleep(0.5)
    raise RuntimeError("GreenMail did not become ready in time")


def start_greenmail() -> tuple[DockerContainer, GreenmailTestServer]:
    """Starts a GreenMail container with auth disabled. Returns the
    container (caller stops it) and its connection details.
    """
    container = DockerContainer(_IMAGE).with_exposed_ports(3025, 3143, 8080)
    container.with_env("GREENMAIL_OPTS", _GREENMAIL_OPTS)
    container.start()

    host = container.get_container_host_ip()
    api_port = int(container.get_exposed_port(8080))
    _wait_until_ready(host, api_port)

    return container, GreenmailTestServer(
        smtp_host=host,
        smtp_port=int(container.get_exposed_port(3025)),
        imap_host=host,
        imap_port=int(container.get_exposed_port(3143)),
    )


def deliver_test_email(
    server: GreenmailTestServer,
    *,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """Sends one email through the container's real SMTP server, so it
    ends up in `recipient`'s mailbox to be fetched back over real IMAP.
    """
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    # GreenMail's minimal SMTP implementation doesn't stamp a Date
    # header on receipt the way a real MTA would - set one explicitly
    # so the delivered message stays a well-formed RFC 5322 email.
    message["Date"] = email.utils.formatdate(localtime=True)
    message.set_content(body)

    last_error: OSError | None = None
    for _ in range(30):
        try:
            with smtplib.SMTP(server.smtp_host, server.smtp_port, timeout=5) as smtp:
                smtp.send_message(message)
            return
        except OSError as e:
            last_error = e
            time.sleep(0.5)
    raise RuntimeError(f"could not deliver test email via GreenMail SMTP: {last_error}")
