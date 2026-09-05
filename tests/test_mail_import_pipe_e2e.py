"""End-to-end proof of the piped-composition mode: three real,
separately-spawned processes chained by real OS pipes -
`fetch --envelopes-only | pathe-translate | movie-planner import` -
producing the same entry a single self-contained `fetch` + `import`
would. Task 8.4 (add-imap-pathe-mail-import).
"""

import mailbox
import subprocess  # nosec B404
import sys
from email.message import EmailMessage
from pathlib import Path

from fixtures import PATHE_EMAIL_PLAIN

from movie_planner.store import Store

_BIN_DIR = Path(sys.executable).parent


def _bin(name: str) -> str:
    path = _BIN_DIR / name
    assert path.is_file(), f"{path} not found - is the project installed (uv sync)?"
    return str(path)


def _pathe_mbox(path: Path) -> None:
    box = mailbox.mbox(str(path))
    try:
        message = EmailMessage()
        message["From"] = "Pathé Nederland <noreply@pathe.nl>"
        message["To"] = "moviewatcher@example.com"
        message["Subject"] = "Your booking confirmation"
        message["Date"] = "Sat, 29 Aug 2026 12:00:00 +0200"
        message.set_content(PATHE_EMAIL_PLAIN)
        box.add(message)
    finally:
        box.close()


def _mail_import_config(tmp_path: Path, mbox_path: Path) -> Path:
    config_path = tmp_path / "mail-import-config.toml"
    config_path.write_text(
        f"""\
[mail]
source = "mbox"

[mail.mbox]
path = "{mbox_path}"

[[chains]]
sender_domain = "pathe.nl"
translate = "{_bin("pathe-translate")}"
"""
    )
    return config_path


def _movie_planner_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "movie-planner-config.toml"
    db_path = tmp_path / "movies.db"
    config_path.write_text(
        f"""\
[caldav]
url = "https://baikal.example.com/calendars/movies/"
username = "moviewatcher"
password = "secret"

[omdb]
api_key = "test-key"

[storage]
db_path = "{db_path}"
"""
    )
    return config_path


def test_fetch_translate_import_pipe_produces_the_expected_entry(tmp_path: Path) -> None:
    mbox_path = tmp_path / "INBOX"
    _pathe_mbox(mbox_path)
    mail_config = _mail_import_config(tmp_path, mbox_path)
    mp_config = _movie_planner_config(tmp_path)

    fetch = subprocess.Popen(  # nosec B603
        [_bin("pathe-mail-import"), "fetch", "--config", str(mail_config), "--envelopes-only"],
        stdout=subprocess.PIPE,
    )
    translate = subprocess.Popen(  # nosec B603
        [_bin("pathe-translate")],
        stdin=fetch.stdout,
        stdout=subprocess.PIPE,
    )
    assert fetch.stdout is not None
    fetch.stdout.close()  # let `translate` receive SIGPIPE if it exits early
    import_result = subprocess.run(  # nosec B603
        [_bin("movie-planner"), "--config", str(mp_config), "import"],
        stdin=translate.stdout,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert translate.stdout is not None
    translate.stdout.close()

    fetch.wait(timeout=10)
    translate.wait(timeout=10)

    assert fetch.returncode == 0
    assert translate.returncode == 0
    assert import_result.returncode == 0, import_result.stdout + import_result.stderr
    assert "1 imported" in import_result.stdout

    store = Store(tmp_path / "movies.db")
    try:
        (entry,) = store.list_entries()
        assert entry.title == "The Dog Stars"
    finally:
        store.close()
