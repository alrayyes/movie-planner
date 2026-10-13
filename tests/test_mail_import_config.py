from pathlib import Path

import pytest

from movie_planner.mail_import.config import (
    ChainConfig,
    ImapSource,
    MailConfigError,
    MaildirSource,
    MboxSource,
    default_config_path,
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
    assert config.source.extra_paths == ()


def test_load_config_reads_mbox_extra_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[mail]
source = "mbox"

[mail.mbox]
path = "~/Mail/INBOX"
extra_paths = ["~/Mail/Archive", "~/Mail/Sent"]

[[chains]]
sender_domain = "pathe.nl"
translate = "pathe-translate"
"""
    )

    config = load_config(config_path)

    assert isinstance(config.source, MboxSource)
    assert config.source.extra_paths == (
        Path("~/Mail/Archive").expanduser(),
        Path("~/Mail/Sent").expanduser(),
    )


def test_load_config_reads_maildir_source(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[mail]
source = "maildir"

[mail.maildir]
path = "~/.local/share/mail/gmail/Archive"

[[chains]]
sender_domain = "pathe.nl"
translate = "pathe-translate"
"""
    )

    config = load_config(config_path)

    assert config.source == MaildirSource(
        path=Path("~/.local/share/mail/gmail/Archive").expanduser()
    )


NAMESPACED_CONFIG = """
[mail_import.mail]
source = "mbox"

[mail_import.mail.mbox]
path = "~/Mail/INBOX"

[[mail_import.chains]]
sender_domain = "pathe.nl"
translate = "pathe-translate"
"""


def test_load_config_reads_the_namespaced_shared_config_shape(tmp_path: Path) -> None:
    # issue #157: pathe-mail-import and movie-planner can share one
    # config file, each under its own top-level section.
    config_path = tmp_path / "config.toml"
    config_path.write_text(NAMESPACED_CONFIG)

    config = load_config(config_path)

    assert config.source == MboxSource(path=Path("~/Mail/INBOX").expanduser())
    assert config.chains == (ChainConfig(sender_domain="pathe.nl", translate="pathe-translate"),)


def test_load_config_prefers_the_namespaced_section_when_both_are_present(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        IMAP_CONFIG + "\n" + NAMESPACED_CONFIG.replace("~/Mail/INBOX", "~/Mail/Other")
    )

    config = load_config(config_path)

    assert config.source == MboxSource(path=Path("~/Mail/Other").expanduser())


def test_load_config_rejects_a_non_list_extra_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        MBOX_CONFIG.replace("[mail.mbox]", '[mail.mbox]\nextra_paths = "not-a-list"')
    )

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config's 'mail.mbox.extra_paths' must be a list"


def test_load_config_rejects_an_unknown_source_kind(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(IMAP_CONFIG.replace('source = "imap"', 'source = "pop3"'))

    with pytest.raises(MailConfigError, match="'imap', 'mbox' or 'maildir'"):
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

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config needs at least one [[chains]] entry"


def test_load_config_rejects_a_non_table_chain(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
chains = ["not-a-table"]

[mail]
source = "imap"

[mail.imap]
host = "127.0.0.1"
port = 1143
username = "me@example.com"
password = "hunter2"
"""
    )

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "chains[0] must be a table"


def test_load_config_missing_chain_sender_domain_names_the_index(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(
        line for line in IMAP_CONFIG.splitlines() if not line.startswith("sender_domain")
    )
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'chains[0].sender_domain'"


def test_load_config_missing_chain_translate_names_the_index(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(
        line for line in IMAP_CONFIG.splitlines() if not line.startswith("translate")
    )
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'chains[0].translate'"


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

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == (
        "config sets both 'imap.password' and 'imap.password_command' - use only one"
    )


def test_load_config_missing_password_names_both_options(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(
        line for line in IMAP_CONFIG.splitlines() if not line.startswith("password = ")
    )
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == (
        "config is missing required key 'imap.password' (or 'imap.password_command')"
    )


def test_load_config_password_command_failure_raises(tmp_path: Path) -> None:
    # check=True is what turns a failing password_command into a clear
    # error - check=False (or omitting it, subprocess.run's own default)
    # would silently let a nonzero exit through, using whatever partial
    # stdout it produced instead of failing loudly.
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        IMAP_CONFIG.replace(
            'password = "hunter2"',
            "password_command = \"sh -c 'echo partial; exit 1'\"",
        )
    )

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value).startswith("imap.password_command failed: ")


def test_load_config_password_command_with_no_output_is_an_empty_password(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(IMAP_CONFIG.replace('password = "hunter2"', 'password_command = "true"'))

    config = load_config(config_path)

    assert isinstance(config.source, ImapSource)
    assert config.source.password == ""


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


def test_default_config_path_falls_back_to_dot_config_when_xdg_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    path = default_config_path()

    assert path == Path("~/.config").expanduser() / "pathe-mail-import" / "config.toml"


# --- exact "missing required key" messages, one per required field ---


def test_load_config_missing_mail_table_names_the_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[[chains]]
sender_domain = "pathe.nl"
translate = "pathe-translate"
"""
    )

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'mail'"


def test_load_config_mail_not_a_table_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
mail = "not-a-table"

[[chains]]
sender_domain = "pathe.nl"
translate = "pathe-translate"
"""
    )

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config's 'mail' section must be a table"


def test_load_config_missing_mail_source_names_the_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(
        line for line in IMAP_CONFIG.splitlines() if not line.startswith("source =")
    )
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'mail.source'"


def test_load_config_missing_imap_host_names_the_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(line for line in IMAP_CONFIG.splitlines() if not line.startswith("host ="))
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'mail.imap.host'"


def test_load_config_missing_imap_port_names_the_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(line for line in IMAP_CONFIG.splitlines() if not line.startswith("port ="))
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'mail.imap.port'"


def test_load_config_missing_imap_username_names_the_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(
        line for line in IMAP_CONFIG.splitlines() if not line.startswith("username =")
    )
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'mail.imap.username'"


def test_load_config_missing_mbox_path_names_the_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    filtered = "\n".join(line for line in MBOX_CONFIG.splitlines() if not line.startswith("path ="))
    config_path.write_text(filtered)

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'mail.mbox.path'"


def test_load_config_missing_maildir_path_names_the_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[mail]
source = "maildir"

[mail.maildir]

[[chains]]
sender_domain = "pathe.nl"
translate = "pathe-translate"
"""
    )

    with pytest.raises(MailConfigError) as exc_info:
        load_config(config_path)

    assert str(exc_info.value) == "config is missing required key 'mail.maildir.path'"
