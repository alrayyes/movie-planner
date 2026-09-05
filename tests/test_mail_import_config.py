from pathlib import Path

import pytest

from movie_planner.mail_import.config import (
    ChainConfig,
    ImapSource,
    MailConfigError,
    MboxSource,
    load_config,
)

IMAP_CONFIG = """
[mail]
source = "imap"

[mail.imap]
host = "127.0.0.1"
port = 1143
username = "me@example.com"
password = "hunter2"

[[chains]]
sender_domain = "pathe.nl"
translate = "pathe-translate"
"""

MBOX_CONFIG = """
[mail]
source = "mbox"

[mail.mbox]
path = "~/Mail/INBOX"

[[chains]]
sender_domain = "pathe.nl"
translate = "pathe-translate"
"""


def test_load_config_reads_imap_source(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(IMAP_CONFIG)

    config = load_config(config_path)

    assert config.source == ImapSource(
        host="127.0.0.1", port=1143, username="me@example.com", password="hunter2"
    )
    assert config.chains == (ChainConfig(sender_domain="pathe.nl", translate="pathe-translate"),)


def test_load_config_reads_mbox_source(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(MBOX_CONFIG)

    config = load_config(config_path)

    assert config.source == MboxSource(path=Path("~/Mail/INBOX").expanduser())


def test_load_config_rejects_an_unknown_source_kind(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(IMAP_CONFIG.replace('source = "imap"', 'source = "pop3"'))

    with pytest.raises(MailConfigError, match="'imap' or 'mbox'"):
        load_config(config_path)


def test_load_config_missing_file_raises_clear_error(tmp_path: Path) -> None:
    missing_path = tmp_path / "does-not-exist.toml"

    with pytest.raises(MailConfigError, match=str(missing_path)):
        load_config(missing_path)


def test_load_config_invalid_toml_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("this is not [valid toml")

    with pytest.raises(MailConfigError, match="not valid TOML"):
        load_config(config_path)


def test_load_config_requires_at_least_one_chain(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(
        line
        for line in IMAP_CONFIG.splitlines()
        if line.strip() not in ("[[chains]]",)
        and not line.startswith(("sender_domain", "translate"))
    )
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError, match=r"\[\[chains\]\]"):
        load_config(config_path)


def test_load_config_runs_password_command(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        IMAP_CONFIG.replace('password = "hunter2"', 'password_command = "printf hunter2"')
    )

    config = load_config(config_path)

    assert isinstance(config.source, ImapSource)
    assert config.source.password == "hunter2"


def test_load_config_rejects_both_password_and_password_command(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        IMAP_CONFIG.replace(
            'password = "hunter2"', 'password = "hunter2"\npassword_command = "printf hunter2"'
        )
    )

    with pytest.raises(MailConfigError, match="password.*password_command"):
        load_config(config_path)


def test_load_config_missing_password_names_both_options(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(
        line for line in IMAP_CONFIG.splitlines() if not line.startswith("password = ")
    )
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError, match="password.*password_command"):
        load_config(config_path)


def test_load_config_default_path_uses_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xdg_config_home = tmp_path / "xdg-config"
    config_dir = xdg_config_home / "pathe-mail-import"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(IMAP_CONFIG)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_home))

    config = load_config()

    assert isinstance(config.source, ImapSource)
