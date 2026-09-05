import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from movie_planner.mail_import.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0


def test_init_non_interactive_with_all_flags_writes_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--source",
            "imap",
            "--imap-host",
            "127.0.0.1",
            "--imap-port",
            "1143",
            "--imap-username",
            "me@example.com",
            "--imap-password-command",
            "printf hunter2",
        ],
    )

    assert result.exit_code == 0, result.output
    data = tomllib.loads(config_path.read_text())
    assert data["mail"]["source"] == "imap"
    assert data["mail"]["imap"]["host"] == "127.0.0.1"
    assert data["mail"]["imap"]["port"] == 1143
    assert data["mail"]["imap"]["password_command"] == "printf hunter2"
    assert "password" not in data["mail"]["imap"]
    assert data["chains"][0]["sender_domain"] == "pathe.nl"
    assert data["chains"][0]["translate"] == "pathe-translate"


def test_init_non_interactive_mbox_source(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    mbox_path = tmp_path / "INBOX"

    result = runner.invoke(
        app,
        ["--config", str(config_path), "--source", "mbox", "--mbox-path", str(mbox_path)],
    )

    assert result.exit_code == 0, result.output
    data = tomllib.loads(config_path.read_text())
    assert data["mail"]["source"] == "mbox"
    assert data["mail"]["mbox"]["path"] == str(mbox_path)


def test_init_non_interactive_missing_required_value_fails_clearly(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["--config", str(config_path), "--source", "imap"])

    assert result.exit_code != 0
    assert "--imap-host" in result.output
    assert not config_path.exists()


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--source",
            "mbox",
            "--mbox-path",
            str(tmp_path / "INBOX"),
        ],
    )

    assert result.exit_code != 0
    assert config_path.read_text() == "existing content"


def test_init_force_overwrites(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--force",
            "--source",
            "mbox",
            "--mbox-path",
            str(tmp_path / "INBOX"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "existing content" not in config_path.read_text()


def test_init_interactive_prompts_for_missing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("movie_planner.mail_import.cli._is_interactive", lambda: True)
    monkeypatch.setattr("movie_planner.mail_import.cli.getpass.getpass", lambda prompt: "hunter2")

    result = runner.invoke(
        app,
        ["--config", str(config_path)],
        # source, host, port(default), username, use-password-command?(no), sender_domain(default), translate(default)
        input="imap\n127.0.0.1\n\nme@example.com\nn\n\n\n",
    )

    assert result.exit_code == 0, result.output
    data = tomllib.loads(config_path.read_text())
    assert data["mail"]["source"] == "imap"
    assert data["mail"]["imap"]["host"] == "127.0.0.1"
    assert data["mail"]["imap"]["port"] == 993
    assert data["mail"]["imap"]["password"] == "hunter2"
    assert data["chains"][0]["sender_domain"] == "pathe.nl"


def test_init_interactive_password_command_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("movie_planner.mail_import.cli._is_interactive", lambda: True)

    result = runner.invoke(
        app,
        ["--config", str(config_path)],
        input="imap\n127.0.0.1\n\nme@example.com\ny\npass show imap\n\n\n",
    )

    assert result.exit_code == 0, result.output
    data = tomllib.loads(config_path.read_text())
    assert data["mail"]["imap"]["password_command"] == "pass show imap"
    assert "password" not in data["mail"]["imap"]
