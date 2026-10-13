"""Spins up a real Baikal (CalDAV) server in a Docker container and
provisions it - admin account, database, one DAV user with a default
calendar - by driving its install wizard and admin panel the same way a
browser would. Used by the task 7.2/7.3 tests, which need a real CalDAV
server rather than the FakeCalendar double the rest of the suite uses,
per rules/testing.md's preference for containers over mocks at the
integration/end-to-end layer.
"""

import re
import time
from dataclasses import dataclass

import httpx
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

_IMAGE = "ckulka/baikal:0.10.1"
_ADMIN_PASSWORD = "TestAdminPass123!"
_CALENDAR_URI = "default"

_CSRF_RE = re.compile(r'name="CSRF_TOKEN" value="([^"]+)"')


@dataclass(frozen=True)
class BaikalTestServer:
    caldav_url: str
    caldav_username: str
    caldav_password: str


def _csrf_token(html: str) -> str:
    match = _CSRF_RE.search(html)
    assert match is not None, "no CSRF_TOKEN found on page"
    return match.group(1)


def _wait_until_ready(client: httpx.Client, base_url: str) -> None:
    for _ in range(60):
        try:
            response = client.get(f"{base_url}/admin/install/")
            if response.status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.5)
    raise RuntimeError("Baikal did not become ready in time")


def _provision(base_url: str, *, username: str, password: str) -> None:
    with httpx.Client() as client:
        _wait_until_ready(client, base_url)

        page = client.get(f"{base_url}/admin/install/")
        client.post(
            f"{base_url}/admin/install/",
            data={
                "Baikal_Model_Config_Standard::submitted": "1",
                "refreshed": "0",
                "CSRF_TOKEN": _csrf_token(page.text),
                "witness[timezone]": "1",
                "data[timezone]": "UTC",
                "witness[card_enabled]": "1",
                "data[card_enabled]": "1",
                "witness[cal_enabled]": "1",
                "data[cal_enabled]": "1",
                "witness[invite_from]": "1",
                "data[invite_from]": "noreply@localhost",
                "witness[dav_auth_type]": "1",
                "data[dav_auth_type]": "Basic",
                "witness[admin_passwordhash]": "1",
                "data[admin_passwordhash]": _ADMIN_PASSWORD,
                "witness[admin_passwordhash_confirm]": "1",
                "data[admin_passwordhash_confirm]": _ADMIN_PASSWORD,
            },
        )

        db_page = client.get(f"{base_url}/admin/install/?/database")
        client.post(
            f"{base_url}/admin/install/?/database",
            data={
                "Baikal_Model_Config_Database::submitted": "1",
                "refreshed": "0",
                "CSRF_TOKEN": _csrf_token(db_page.text),
                "witness[backend]": "1",
                "data[backend]": "sqlite",
                "witness[sqlite_file]": "1",
                "data[sqlite_file]": "/var/www/baikal/Specific/db/db.sqlite",
            },
        )

        client.get(f"{base_url}/admin/")
        client.post(
            f"{base_url}/admin/",
            data={"auth": "1", "login": "admin", "password": _ADMIN_PASSWORD},
        )

        new_user_page = client.get(f"{base_url}/admin/?/users/new/1/")
        client.post(
            f"{base_url}/admin/?/users/new/1/",
            data={
                "Baikal_Model_User::submitted": "1",
                "refreshed": "0",
                "CSRF_TOKEN": _csrf_token(new_user_page.text),
                "witness[username]": "1",
                "data[username]": username,
                "witness[displayname]": "1",
                "data[displayname]": username,
                "witness[email]": "1",
                "data[email]": f"{username}@example.invalid",
                "witness[password]": "1",
                "data[password]": password,
                "witness[passwordconfirm]": "1",
                "data[passwordconfirm]": password,
            },
        )
        # A default calendar is created automatically alongside the user.


def start_baikal() -> tuple[DockerContainer, BaikalTestServer]:
    """Starts a Baikal container and provisions it with one DAV user
    ("moviewatcher") and its auto-created default calendar. Returns the
    container (caller stops it) and the server's connection details.
    """
    container = DockerContainer(_IMAGE).with_exposed_ports(80)
    container.waiting_for(
        LogMessageWaitStrategy("Command line: 'apache2 -D FOREGROUND'").with_startup_timeout(30)
    )
    container.start()

    host = container.get_container_host_ip()
    port = container.get_exposed_port(80)
    base_url = f"http://{host}:{port}"

    username = "moviewatcher"
    password = "WatcherPass123!"
    _provision(base_url, username=username, password=password)

    return container, BaikalTestServer(
        caldav_url=f"{base_url}/dav.php/calendars/{username}/{_CALENDAR_URI}/",
        caldav_username=username,
        caldav_password=password,
    )
